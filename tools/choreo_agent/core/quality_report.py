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
    }


if __name__ == "__main__":
    import sys

    paths = sys.argv[1:] if len(sys.argv) > 1 else ["."]
    for p in paths:
        report = score_project(p)
        print(json.dumps(report, ensure_ascii=False, indent=1))
