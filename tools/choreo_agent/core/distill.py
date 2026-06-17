"""Human-work distillation → choreography skill extraction (Stage 3).

Reads a finished work's trajectory (a .fii directory or any project's output)
and extracts a *choreography signature* — measurable facts about how the piece
moves and lights — then maps that signature to **technique labels** (principles
like "light-clock lighting", "settled-with-lit-holds", "center-migration arc",
"within-frame mirror symmetry").

The output is a distilled *profile*: principles and parameters, NOT coordinates.
A human reviews a profile and curates reusable principle-skills from it — we
never replay a human work's point tables (that would be the hardcode the project
forbids). This is the automated form of the hand-distillation in
doc/human_choreography_distillation.md.

`distill_trajectory(data)` is pure (operates on read_fii's data array) and unit-
tested on synthetic trajectories; `distill_fii(dir)` wraps pyfii.read_fii.
"""

from __future__ import annotations

import math

try:  # reuse the readability metric the quality report already defines
    from .quality_report import mirror_symmetry_error
except ImportError:  # direct script run
    from quality_report import mirror_symmetry_error


# Per-frame movement (cm) below which a drone counts as "still" that frame.
_STILL_CM_PER_FRAME = 0.25
# Fraction of drones that must be moving for a frame to count as "transit".
_TRANSIT_MOVING_FRACTION = 0.34
_Z_LAYER_BAND_CM = 25.0


def distill_trajectory(data, fps: int = 60, skip_takeoff_s: float = 1.0) -> dict:
    """Measure a choreography signature from a read_fii `data` array.

    `data`: list of drones; each drone is a list of frames; frame = [idx, x, y,
    z, ?, light?] where light is an (r,g,b) tuple or -1 (off). Pure function.
    """
    n = len(data)
    if n == 0:
        return {"error": "empty"}
    min_len = min(len(d) for d in data)
    start_frame = max(1, int(skip_takeoff_s * fps))
    if min_len <= start_frame + 1:
        return {"error": "too short"}

    duration_s = round(min_len / fps, 1)

    # ---- per-drone path length + per-drone net excursion ----
    path_len = [0.0] * n
    onset_frame = [None] * n
    for i, d in enumerate(data):
        for f in range(start_frame + 1, min_len):
            step = _move_cm(d[f], d[f - 1])
            path_len[i] += step
            if onset_frame[i] is None and step >= _STILL_CM_PER_FRAME * 3:
                onset_frame[i] = f
    start_pos = [(_g(data[i][start_frame], 1), _g(data[i][start_frame], 2)) for i in range(n)]
    end_pos = [(_g(data[i][min_len - 1], 1), _g(data[i][min_len - 1], 2)) for i in range(n)]
    excursion = [math.dist(start_pos[i], end_pos[i]) for i in range(n)]
    median_path = sorted(path_len)[n // 2]

    # ---- settled vs transit ratio (pacing) ----
    transit_frames = 0
    counted = 0
    for f in range(start_frame + 1, min_len):
        moving = sum(1 for d in data if _move_cm(d[f], d[f - 1]) >= _STILL_CM_PER_FRAME)
        counted += 1
        if moving >= max(1, math.ceil(n * _TRANSIT_MOVING_FRACTION)):
            transit_frames += 1
    transit_ratio = round(transit_frames / max(1, counted), 2)
    settled_ratio = round(1.0 - transit_ratio, 2)

    # ---- centroid arc ----
    cx0 = cy0 = cx = cy = 0.0
    max_drift = 0.0
    started = False
    for f in range(start_frame, min_len, max(1, fps // 2)):
        cx = sum(_g(d[f], 1) for d in data) / n
        cy = sum(_g(d[f], 2) for d in data) / n
        if not started:
            cx0, cy0 = cx, cy
            started = True
        max_drift = max(max_drift, math.dist((cx, cy), (cx0, cy0)))
    net_drift = math.dist((cx, cy), (cx0, cy0))

    # ---- height usage ----
    mid = (start_frame + min_len) // 2
    zs = [_g(data[i][mid], 3) for i in range(n)]
    z_range = round(max(zs) - min(zs), 0)
    z_layers = len({round(z / _Z_LAYER_BAND_CM) for z in zs})

    # ---- lighting register ----
    light = _light_signature(data, start_frame, min_len)

    # ---- readability (within-frame mirror symmetry) ----
    sym_errs = []
    for f in range(start_frame, min_len, fps):  # 1s sampling
        pts = [(_g(d[f], 1), _g(d[f], 2)) for d in data]
        if any(p[0] > 0 or p[1] > 0 for p in pts):
            sym_errs.append(mirror_symmetry_error(pts))
    mean_sym = round(sum(sym_errs) / len(sym_errs)) if sym_errs else None
    readable_ratio = (
        round(sum(1 for e in sym_errs if e < 40) / len(sym_errs), 2) if sym_errs else None
    )

    # ---- stagger (onset spread) ----
    onsets = [f for f in onset_frame if f is not None]
    onset_spread_s = round((max(onsets) - min(onsets)) / fps, 2) if len(onsets) >= 2 else 0.0

    return {
        "duration_s": duration_s,
        "drones": n,
        "median_path_cm": round(median_path),
        "median_excursion_cm": round(sorted(excursion)[n // 2]),
        "max_excursion_cm": round(max(excursion)),
        "settled_ratio": settled_ratio,
        "transit_ratio": transit_ratio,
        "centroid_max_drift_cm": round(max_drift),
        "centroid_net_drift_cm": round(net_drift),
        "z_range_cm": z_range,
        "z_layers": z_layers,
        "onset_spread_s": onset_spread_s,
        "mean_symmetry_err_cm": mean_sym,
        "readable_ratio": readable_ratio,
        **light,
    }


def _light_signature(data, start_frame: int, min_len: int) -> dict:
    """Distinct colors, lit ratio, and per-drone color-change rate."""
    colors = set()
    changes = 0
    lit = 0
    total = 0
    for d in data:
        prev = None
        for f in range(start_frame, min_len):
            c = d[f][5] if len(d[f]) > 5 else None
            if c is None:
                continue
            total += 1
            if isinstance(c, (int, float)) and c == -1:
                prev = None
                continue
            lit += 1
            key = tuple(c) if hasattr(c, "__len__") else c
            colors.add(key)
            if prev is not None and key != prev:
                changes += 1
            prev = key
    span_frames = max(1, (min_len - start_frame))
    return {
        "distinct_colors": len(colors),
        "lit_ratio": round(lit / max(1, total), 2),
        # color changes per drone per second (proxy for lighting "clock" density)
        "color_change_rate": round(changes / span_frames, 2),
    }


def signature_to_profile(sig: dict, name: str, source: str) -> dict:
    """Map a measured signature to human-readable technique labels (principles).

    These labels are the distilled *skills* — reusable principles a human can
    curate into the registry. No coordinates, no replayable trajectory.
    """
    if sig.get("error"):
        return {"name": name, "source": source, "error": sig["error"]}
    techniques: list[str] = []

    # lighting register
    if sig["color_change_rate"] >= 0.6 and sig["distinct_colors"] >= 20:
        techniques.append("light-clock 灯光时钟（100ms 级持续变色，灯光占满时间轴）")
    elif sig["distinct_colors"] >= max(8, sig["drones"]):
        techniques.append("identity-palette 个体色彩身份（每机/每对独立色相）")
    else:
        techniques.append("motion-driven 运动驱动（灯光稀疏短提示，动作主导）")

    # pacing
    if sig["settled_ratio"] >= 0.45 and sig["lit_ratio"] >= 0.5:
        techniques.append(
            f"settled-with-lit-holds 亮灯定格主导（{int(sig['settled_ratio']*100)}% 时间定格展示图形，dntg 式）"
        )
    elif sig["transit_ratio"] >= 0.6:
        techniques.append("motion-dominant 运动主导（少定格、连续位移）")

    # centroid arc
    net, mx = sig["centroid_net_drift_cm"], sig["centroid_max_drift_cm"]
    if mx >= 120 and net >= 80:
        techniques.append("center-migration 质心迁移（方向性空间叙事：启程→抵达）")
    elif mx >= 70 and net < 40:
        techniques.append("excursion-return 出走-回归（质心远行后回到原点）")
    elif mx < 45:
        techniques.append("pinned-centroid 质心钉守（主题钉死中心，靠队形/灯光变化）")

    # readability
    if sig.get("readable_ratio") is not None and sig["readable_ratio"] >= 0.5:
        techniques.append("within-frame mirror-symmetry 帧内镜像对称（高可读构图）")

    # height
    if sig["z_layers"] >= 3 and sig["z_range_cm"] >= 90:
        techniques.append(f"layered-height 真实高度分层（{sig['z_layers']} 层 / {int(sig['z_range_cm'])}cm 跨度）")

    # stagger
    if sig["onset_spread_s"] >= 0.4:
        techniques.append(f"staggered-onset 错峰启动（入场时间散布 {sig['onset_spread_s']}s）")

    return {
        "name": name,
        "source": source,
        "signature": sig,
        "techniques": techniques,
        "note": "原则级蒸馏：参照其技法/纹理，不复制坐标。人工评审后可挑选纳入 registry 作 principle-skill。",
    }


def distill_fii(fii_dir, name: str = "", source: str = "", fps: int = 60) -> dict:
    """Read a .fii directory (or project output dir) and distill a profile."""
    import sys
    import warnings
    from pathlib import Path

    repo_src = str(Path(__file__).resolve().parents[3] / "src")
    if repo_src not in sys.path:
        sys.path.insert(0, repo_src)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import pyfii as pf

        data, _t0, *_ = pf.read_fii(str(fii_dir), fps=fps, ignore_acc=True)
    sig = distill_trajectory(data, fps=fps)
    return signature_to_profile(sig, name or str(fii_dir), source or str(fii_dir))


def render_profile_markdown(profile: dict) -> str:
    """Render a distilled profile as a reference card for human review / curation."""
    if profile.get("error"):
        return f"### {profile['name']}\n\n- **error**: {profile['error']}\n"
    sig = profile["signature"]
    lines = [
        f"### Distilled reference — {profile['name']}",
        "",
        f"- **source**: {profile['source']}",
        f"- **techniques**: {'; '.join(profile['techniques'])}",
        "- **signature**: "
        + ", ".join(f"{k}={v}" for k, v in sig.items() if v is not None),
        f"- **note**: {profile['note']}",
        "",
    ]
    return "\n".join(lines)


def _move_cm(frame_a, frame_b) -> float:
    return math.sqrt(
        (_g(frame_a, 1) - _g(frame_b, 1)) ** 2
        + (_g(frame_a, 2) - _g(frame_b, 2)) ** 2
        + (_g(frame_a, 3) - _g(frame_b, 3)) ** 2
    )


def _g(frame, idx) -> float:
    return float(frame[idx]) if len(frame) > idx else 0.0


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys

    if len(sys.argv) < 2:
        print("usage: python -m core.distill <fii_or_output_dir> [name]")
        raise SystemExit(2)
    prof = distill_fii(sys.argv[1], name=sys.argv[2] if len(sys.argv) > 2 else "")
    print(json.dumps(prof, ensure_ascii=False, indent=2))
    print("\n" + render_profile_markdown(prof))
