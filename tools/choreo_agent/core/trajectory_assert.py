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


def check_drone_in_box(
    data,
    fps: int,
    drone_index: int,
    t_s: float,
    box: tuple[tuple[float, float], tuple[float, float], tuple[float, float]],
) -> tuple[bool, dict]:
    """模糊方位指令确认：drone k 在 t_s 时刻落在 (x0,x1)/(y0,y1)/(z0,z1) 区域内。"""
    actual = drone_position_at(data, fps, drone_index, t_s)
    ok = all(lo - 1e-9 <= v <= hi + 1e-9 for v, (lo, hi) in zip(actual, box))
    return ok, {
        "drone": drone_index,
        "t_s": round(t_s, 2),
        "box": [[round(float(lo), 1), round(float(hi), 1)] for lo, hi in box],
        "actual": [round(v, 1) for v in actual],
    }


def check_relative_shift(
    before_xyz: tuple[float, float, float],
    after_xyz: tuple[float, float, float],
    axis: int,
    sign: int,
    min_cm: float = 20.0,
    max_other_drift_cm: float = 120.0,
) -> tuple[bool, dict]:
    """相对方位指令确认（"再往左一点"）：目标轴按指定方向位移 ≥min_cm，
    其余轴漂移 ≤max_other_drift_cm（挪了但没乱跑）。"""
    delta = [float(a) - float(b) for a, b in zip(after_xyz, before_xyz)]
    moved = delta[axis] * sign
    others = [abs(d) for i, d in enumerate(delta) if i != axis]
    ok = moved >= min_cm and all(d <= max_other_drift_cm for d in others)
    return ok, {
        "axis": "xyz"[axis],
        "direction": "+" if sign > 0 else "-",
        "before": [round(float(v), 1) for v in before_xyz],
        "after": [round(float(v), 1) for v in after_xyz],
        "moved_cm": round(moved, 1),
        "min_cm": min_cm,
        "other_drift_cm": [round(d, 1) for d in others],
    }


# ---- 灯光时序原语（"从左到右依次彩虹并明暗渐变"这类复杂灯效的客观确认）----


def hue_deg(rgb: tuple[int, int, int]) -> float | None:
    """RGB → HSV 色相角（0-360）；灰/黑（饱和度过低）返回 None。"""
    r, g, b = (v / 255.0 for v in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    if mx <= 0.05 or (mx - mn) / mx < 0.25:
        return None
    d = mx - mn
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h * 60.0


def brightness(rgb: tuple[int, int, int]) -> int:
    return max(int(v) for v in rgb)


def color_onset_times(data, fps: int, t0: float, t1: float, predicate) -> dict[int, float | None]:
    """各机在窗口内首次满足颜色谓词的时刻（未出现 = None）。"""
    onsets: dict[int, float | None] = {}
    step = 1.0 / min(fps, 20)
    for k in range(len(data)):
        onset = None
        t = t0
        while t <= t1 + 1e-9:
            rgb = drone_color_at(data, fps, k, t)
            if rgb is not None and predicate(rgb):
                onset = round(t, 2)
                break
            t += step
        onsets[k] = onset
    return onsets


def check_spatial_temporal_order(
    data,
    fps: int,
    t0: float,
    t1: float,
    predicate,
    axis: int = 0,
    ascending: bool = True,
    min_span_s: float = 0.6,
    max_inversions: int = 1,
) -> tuple[bool, dict]:
    """"从左到右依次…"确认：颜色 onset 顺序跟随空间轴排序。

    以窗口起点的各机 axis 坐标排序为基准，onset 时刻应随之递增；
    允许 max_inversions 个逆序对，且首尾 onset 时差 ≥min_span_s（否则是同步不是依次）。
    """
    onsets = color_onset_times(data, fps, t0, t1, predicate)
    missing = [k for k, v in onsets.items() if v is None]
    if missing:
        return False, {"onsets": onsets, "missing": missing}
    order = sorted(
        range(len(data)),
        key=lambda k: drone_position_at(data, fps, k, t0)[axis],
        reverse=not ascending,
    )
    sequence = [onsets[k] for k in order]
    inversions = sum(
        1
        for i in range(len(sequence))
        for j in range(i + 1, len(sequence))
        if sequence[i] > sequence[j] + 1e-9
    )
    span = max(sequence) - min(sequence)
    ok = inversions <= max_inversions and span >= min_span_s
    return ok, {
        "spatial_order": order,
        "onsets_in_spatial_order": sequence,
        "inversions": inversions,
        "max_inversions": max_inversions,
        "span_s": round(span, 2),
        "min_span_s": min_span_s,
    }


def check_hue_diversity(
    data, fps: int, t_s: float, min_hue_buckets: int = 5, bucket_deg: float = 60.0
) -> tuple[bool, dict]:
    """彩虹/多彩确认：同一时刻全队色相覆盖 ≥min_hue_buckets 个色相桶。"""
    hues = {}
    buckets = set()
    for k in range(len(data)):
        rgb = drone_color_at(data, fps, k, t_s)
        h = hue_deg(rgb) if rgb is not None else None
        hues[k] = None if h is None else round(h, 0)
        if h is not None:
            buckets.add(int(h // bucket_deg))
    return len(buckets) >= min_hue_buckets, {
        "t_s": round(t_s, 2),
        "hues_deg": hues,
        "hue_buckets": sorted(buckets),
        "min_hue_buckets": min_hue_buckets,
    }


def check_brightness_modulation(
    data,
    fps: int,
    t0: float,
    t1: float,
    min_amplitude: int = 60,
    min_fraction: float = 0.7,
) -> tuple[bool, dict]:
    """明暗渐变/呼吸确认：窗口内各机亮度摆幅 ≥min_amplitude 的机占比达标。"""
    step = 1.0 / min(fps, 20)
    amplitudes: dict[int, int] = {}
    qualified = 0
    for k in range(len(data)):
        values = []
        t = t0
        while t <= t1 + 1e-9:
            rgb = drone_color_at(data, fps, k, t)
            if rgb is not None:
                values.append(brightness(rgb))
            t += step
        amp = (max(values) - min(values)) if values else 0
        amplitudes[k] = amp
        if amp >= min_amplitude:
            qualified += 1
    fraction = qualified / max(1, len(data))
    return fraction >= min_fraction, {
        "window": [round(t0, 2), round(t1, 2)],
        "amplitudes": amplitudes,
        "qualified_fraction": round(fraction, 3),
        "min_amplitude": min_amplitude,
        "min_fraction": min_fraction,
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
        # 占比指标在低位区间是两次生成间的正常噪声（validator 的退化判定在
        # 0.75/0.85 量级）；只有升幅明显且逼近退化区间才算新增塌缩。
        if a > b + 0.15 and a > 0.5:
            problems.append(f"{key}: {b:.2f} -> {a:.2f}")
    z_before = float(before.get("window_z_range_cm", 0.0) or 0.0)
    z_after = float(after.get("window_z_range_cm", 0.0) or 0.0)
    detail["window_z_range_cm"] = {"before": round(z_before, 1), "after": round(z_after, 1)}
    if z_before >= 35.0 and z_after < max(35.0, z_before * 0.6):
        problems.append(f"window_z_range_cm collapsed: {z_before:.0f} -> {z_after:.0f}")
    return not problems, {"problems": problems, "metrics": detail}
