"""Quality scoring report for choreo agent projects.

Measures how many of the dntg-class patterns each segment uses:
math geometry, per-drone individuality, lighting depth, stagger, focal drones.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# deepseek_cannon_choreo.py baselines (7 drones, 8 segments, ~170 lines)
BASELINE = {
    "math_sin_cos_calls": 66,
    "per_drone_geo_comprehensions": 17,  # for i in range(N) comprehensions
    "staggered_starts": 5,  # delay(i*ms)
    "per_drone_z_offsets": 10,  # target[i][2] + sin(i)
    "per_drone_vel": 14,  # per-drone VelXY calls
    "distinct_colors": 14,
    "math_geometry_segments": 7,  # segments using math in geo
    "staggered_segments": 3,
}


def score_project(project_root: str | Path) -> dict:
    """Score a completed choreo agent project against dntg/deepseek_cannon baselines."""
    root = Path(project_root)
    design_path = root / "scripts" / "design.py"
    stability_path = root / "stability_result.json"

    if not design_path.exists():
        return {"error": f"design.py not found in {root}"}

    code = design_path.read_text(encoding="utf-8")

    # Extract segment bodies between markers
    try:
        from .composition import extract_code_features
    except ImportError:  # direct script run: python3 core/quality_report.py
        from composition import extract_code_features

    segments: dict[str, str] = {}
    for match in re.finditer(
        r"PYFII_AGENT_SEGMENT_START id=(\w+).*?\n(.*?)PYFII_AGENT_SEGMENT_END",
        code,
        re.DOTALL,
    ):
        segments[match.group(1)] = match.group(2).strip()

    per_segment: dict[str, dict] = {}
    all_colors: set[str] = set()
    rgb_tuple_color_total = 0
    totals = {
        "math_sin_cos_calls": 0,
        "per_drone_geo_comprehensions": 0,
        "staggered_starts": 0,
        "per_drone_z_offsets": 0,
        "per_drone_vel": 0,
        "distinct_colors": 0,
        "math_geometry_segments": 0,
        "circle_formula_segments": 0,
        "staggered_segments": 0,
        "per_drone_individuality_segments": 0,
        "lighting_tick_estimate": 0,
        "keyframe_count": 0,
    }

    for seg_id, body in sorted(segments.items()):
        feat = extract_code_features(body)
        seg = {
            "lines": len(body.splitlines()),
            "has_math": feat["has_math_geometry"],
            "has_stagger": feat["has_indexed_stagger"],
            "sin_cos_calls": len(
                re.findall(r"\bsin\s*\(|\bcos\s*\(", body)
            ),
            "geo_comprehensions": len(
                re.findall(r"for\s+\w+\s+in\s+range\s*\([^)]*\)\s*\]", body)
            ),
            "stagger_start": 1
            if re.search(r"delay\s*\(\s*i\s*\*", body)
            else 0,
            "z_offsets": len(
                re.findall(r"sin\s*\(\s*i\s*\)\s*|cos\s*\(\s*i\s*\)\s*", body)
            ),
            "per_drone_vel": len(re.findall(r"VelXY\s*\(", body)),
            # reflection 文档预言的退化：全程绕圈（每段都是 2*pi*i/N 同心圆）
            "uses_circle_formula": bool(
                re.search(r"cos\s*\(\s*2\s*\*\s*pi", body)
                and re.search(r"sin\s*\(\s*2\s*\*\s*pi", body)
            ),
            "colors": len(feat["color_literals"]),
            "estimated_keyframes": feat["estimated_keyframe_count"],
            "lighting_ticks": feat["lighting_tick_estimate"],
        }
        per_segment[seg_id] = seg

        totals["math_sin_cos_calls"] += seg["sin_cos_calls"]
        totals["per_drone_geo_comprehensions"] += seg["geo_comprehensions"]
        totals["staggered_starts"] += seg["stagger_start"]
        totals["per_drone_z_offsets"] += seg["z_offsets"]
        totals["per_drone_vel"] += seg["per_drone_vel"]
        totals["lighting_tick_estimate"] += seg["lighting_ticks"]
        totals["keyframe_count"] += seg["estimated_keyframes"]
        all_colors |= set(feat["color_literals"])
        rgb_tuple_color_total += feat.get("rgb_tuple_color_count", 0)

        if seg["has_math"]:
            totals["math_geometry_segments"] += 1
        if seg["uses_circle_formula"]:
            totals["circle_formula_segments"] += 1
        if seg["has_stagger"]:
            totals["staggered_segments"] += 1
        if seg["stagger_start"] or seg["z_offsets"] or seg["has_stagger"]:
            totals["per_drone_individuality_segments"] += 1

    totals["distinct_colors"] = len(all_colors) + rgb_tuple_color_total

    # Compare against baseline
    comparison = {}
    for key in BASELINE:
        actual = totals.get(key, 0)
        baseline = BASELINE[key]
        pct = round(actual / max(1, baseline) * 100)
        comparison[key] = {"actual": actual, "baseline": baseline, "pct_of_baseline": pct}

    # Layer in stability result
    stability = {}
    if stability_path.exists():
        try:
            s = json.loads(stability_path.read_text(encoding="utf-8"))["summary"]
            stability = {
                "completed": s.get("completed", False),
                "locked_segments": len(s.get("locked_segment_ids", [])),
                "total_segments": len(s.get("locked_segment_ids", []))
                + (1 if s.get("current_segment") else 0),
                "cost_yuan": s.get("token_usage", {})
                .get("pricing_cny", {})
                .get("total_with_actual_cache_mix"),
                "elapsed_s": s.get("elapsed_s"),
            }
        except (json.JSONDecodeError, KeyError, TypeError):
            stability = {"error": "cannot parse stability_result.json"}

    return {
        "project": str(root),
        "totals": totals,
        "per_segment": per_segment,
        "comparison_vs_deepseek_cannon": comparison,
        "stability": stability,
        "centroid": centroid_drift(root / "output"),
    }


def centroid_drift(output_dir: str | Path) -> dict:
    """质心轨迹叙事指纹（PLAN 11.9）：最大/净漂移。

    语料库参照：开启新征程 max 153 / net 74（左→右启程）、
    无人区 max 96 / net 0（出走-回归）、太空电梯 max 37（垂直主题钉死）。
    """
    try:
        import sys as _sys
        repo_src = str(Path(__file__).resolve().parents[3] / "src")
        if repo_src not in _sys.path:
            _sys.path.insert(0, repo_src)
        import warnings as _warnings

        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            import pyfii as pf

            data, _t0, *_ = pf.read_fii(str(output_dir), fps=30, ignore_acc=True)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}"}
    if not data:
        return {"error": "empty"}
    min_len = min(len(d) for d in data)
    if min_len < 2:
        return {"error": "too short"}
    n = len(data)
    start = None
    max_drift = 0.0
    cx0 = cy0 = cx = cy = 0.0
    for frame in range(0, min_len, 15):  # 0.5s 采样
        cx = sum(d[frame][1] for d in data) / n
        cy = sum(d[frame][2] for d in data) / n
        if start is None:
            start = (cx, cy)
            cx0, cy0 = cx, cy
        drift = ((cx - cx0) ** 2 + (cy - cy0) ** 2) ** 0.5
        max_drift = max(max_drift, drift)
    net = ((cx - cx0) ** 2 + (cy - cy0) ** 2) ** 0.5
    return {
        "start": (round(cx0), round(cy0)),
        "max_drift_cm": round(max_drift),
        "net_drift_cm": round(net),
    }


if __name__ == "__main__":
    import sys

    paths = sys.argv[1:] if len(sys.argv) > 1 else ["."]
    for p in paths:
        report = score_project(p)
        print(json.dumps(report, ensure_ascii=False, indent=1))
