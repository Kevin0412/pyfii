"""轨迹级断言 — 导演细节指令的客观确认层。

读回 .fii 的密集轨迹（帧结构 (time, x, y, z, angle, led, acc)，led 为 BGR 元组，
见 read.py dots2line），对"某机停在某点/某段灯色"这类细节指令做数值验证，
并对比修改前后的退化指标（防"满足指令但整体塌缩"）。
所有检查返回 (ok, detail) 而不抛异常，便于 runner 聚合成逐 case 验收 JSON。
"""

from __future__ import annotations

import math
from pathlib import Path

from .validator import _find_fii_dir


def load_trajectory(output_dir: Path, fps: int = 60):
    """读回密采样轨迹：返回 (data, fps)。data[drone][frame] = (t,x,y,z,angle,led,acc)。"""
    import pyfii as pf

    fii_dir = _find_fii_dir(Path(output_dir))
    data, _t0, *_ = pf.read_fii(str(fii_dir), fps=fps, ignore_acc=True)
    return data, fps


def _frame_at(data, fps: int, drone_index: int, t_s: float):
    frames = data[drone_index]
    frame = min(len(frames) - 1, max(0, int(round(t_s * fps))))
    return frames[frame]


def drone_position_at(data, fps: int, drone_index: int, t_s: float) -> tuple[float, float, float]:
    frame = _frame_at(data, fps, drone_index, t_s)
    return float(frame[1]), float(frame[2]), float(frame[3])


def drone_color_at(data, fps: int, drone_index: int, t_s: float) -> tuple[int, int, int] | None:
    """返回 RGB（读回帧存的是 BGR）；灯未设置 (-1,-1,-1) 返回 None。"""
    frame = _frame_at(data, fps, drone_index, t_s)
    if len(frame) < 6 or not isinstance(frame[5], (tuple, list)):
        return None
    b, g, r = (int(v) for v in frame[5][:3])
    if b < 0 or g < 0 or r < 0:
        return None
    return (r, g, b)


def check_drone_at(
    data,
    fps: int,
    drone_index: int,
    t_s: float,
    target_xyz: tuple[float, float, float],
    tol_cm: float = 25.0,
) -> tuple[bool, dict]:
    """指令确认：drone k 在 t_s 时刻位于目标点 ±tol_cm（3D 距离）。"""
    actual = drone_position_at(data, fps, drone_index, t_s)
    dist = math.dist(actual, tuple(float(v) for v in target_xyz))
    return dist <= tol_cm, {
        "drone": drone_index,
        "t_s": round(t_s, 2),
        "target": [round(float(v), 1) for v in target_xyz],
        "actual": [round(v, 1) for v in actual],
        "distance_cm": round(dist, 1),
        "tol_cm": tol_cm,
    }


def blue_dominant(rgb: tuple[int, int, int]) -> bool:
    r, g, b = rgb
    return b >= 90 and b > r and b >= g


def check_color_window(
    data,
    fps: int,
    t0: float,
    t1: float,
    predicate,
    drones: list[int] | None = None,
    min_fraction: float = 0.6,
    sample_hz: float = 4.0,
) -> tuple[bool, dict]:
    """指令确认：时间窗内各机灯色满足谓词的采样占比 ≥ min_fraction。

    未设置灯色的帧不计入分母（起飞前/降落后灯灭是正常状态）。
    """
    indices = drones if drones is not None else list(range(len(data)))
    step = max(1.0 / max(sample_hz, 0.5), 1.0 / fps)
    per_drone: dict[int, float] = {}
    worst = 1.0
    for k in indices:
        hits = 0
        total = 0
        t = t0
        while t <= t1 + 1e-9:
            rgb = drone_color_at(data, fps, k, t)
            if rgb is not None:
                total += 1
                if predicate(rgb):
                    hits += 1
            t += step
        fraction = (hits / total) if total else 0.0
        per_drone[k] = round(fraction, 3)
        worst = min(worst, fraction)
    return worst >= min_fraction, {
        "window": [round(t0, 2), round(t1, 2)],
        "min_fraction": min_fraction,
        "worst_fraction": round(worst, 3),
        "per_drone_fraction": per_drone,
    }


# 退化对比容差：整数指标（车道/固定高度机数）允许 +1，占比指标允许 +0.15。
_INT_KEYS = ("lane_x_locked_drones", "lane_y_locked_drones", "fixed_height_drones")
_FRACTION_KEYS = ("circle_like_fraction", "flat_height_fraction", "order_stable_fraction")


def check_no_new_degradation(before: dict, after: dict) -> tuple[bool, dict]:
    """细节修改不得引发结构性塌缩：directed 段的退化指标不明显劣于 baseline。"""
    if not before or not after:
        return True, {"note": "baseline or directed degradation metrics missing; skipped"}
    problems: list[str] = []
    detail: dict = {}
    for key in _INT_KEYS:
        b, a = int(before.get(key, 0) or 0), int(after.get(key, 0) or 0)
        detail[key] = {"before": b, "after": a}
        if a > b + 1:
            problems.append(f"{key}: {b} -> {a}")
    for key in _FRACTION_KEYS:
        b, a = float(before.get(key, 0.0) or 0.0), float(after.get(key, 0.0) or 0.0)
        detail[key] = {"before": round(b, 3), "after": round(a, 3)}
        if a > b + 0.15:
            problems.append(f"{key}: {b:.2f} -> {a:.2f}")
    z_before = float(before.get("window_z_range_cm", 0.0) or 0.0)
    z_after = float(after.get("window_z_range_cm", 0.0) or 0.0)
    detail["window_z_range_cm"] = {"before": round(z_before, 1), "after": round(z_after, 1)}
    if z_before >= 35.0 and z_after < max(35.0, z_before * 0.6):
        problems.append(f"window_z_range_cm collapsed: {z_before:.0f} -> {z_after:.0f}")
    return not problems, {"problems": problems, "metrics": detail}
