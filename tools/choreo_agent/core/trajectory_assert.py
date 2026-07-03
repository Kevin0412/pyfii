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


def final_hue_onset_predicate(data, fps: int, drone_index: int, t1: float, tol_deg: float = 30.0):
    """"依次点亮各自颜色"的正确谓词：到达该机段尾最终色相才算 onset。

    直接用"任意有色"当谓词会被前半段既有彩灯误触发（onset 全等于窗口起点）。
    """
    target = None
    rgb = drone_color_at(data, fps, drone_index, t1)
    if rgb is not None:
        target = hue_deg(rgb)

    def predicate(rgb_value):
        if target is None:
            return False
        h = hue_deg(rgb_value)
        if h is None:
            return False
        diff = abs(h - target) % 360.0
        return min(diff, 360.0 - diff) <= tol_deg

    return predicate


def check_spatial_temporal_order(
    data,
    fps: int,
    t0: float,
    t1: float,
    predicate=None,
    axis: int = 0,
    ascending: bool = True,
    min_span_s: float = 0.6,
    max_inversions: int = 1,
) -> tuple[bool, dict]:
    """"从左到右依次…"确认：颜色 onset 顺序跟随空间轴排序。

    以窗口起点的各机 axis 坐标排序为基准，onset 时刻应随之递增；
    允许 max_inversions 个逆序对，且首尾 onset 时差 ≥min_span_s（否则是同步不是依次）。
    predicate=None 时按各机"到达段尾最终色相"检测（final_hue_onset_predicate）。
    """
    if predicate is None:
        onsets = {}
        for k in range(len(data)):
            per_drone = final_hue_onset_predicate(data, fps, k, t1)
            onsets.update(
                {k: color_onset_times([data[k]], fps, t0, t1, per_drone)[0]}
            )
    else:
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


def check_max_speed(
    data,
    fps: int,
    t0: float,
    t1: float,
    max_cm_s: float = 140.0,
    min_fraction: float = 0.98,
) -> tuple[bool, dict]:
    """"整段放慢"确认：窗口内瞬时速度超限的采样占比 ≤ (1-min_fraction)。"""
    step = 1.0 / min(fps, 20)
    peak = 0.0
    total = 0
    over = 0
    for k in range(len(data)):
        prev = None
        t = t0
        while t <= t1 + 1e-9:
            pos = drone_position_at(data, fps, k, t)
            if prev is not None:
                speed = math.dist(pos, prev) / step
                peak = max(peak, speed)
                total += 1
                if speed > max_cm_s:
                    over += 1
            prev = pos
            t += step
    ok = total > 0 and (total - over) / total >= min_fraction
    return ok, {
        "window": [round(t0, 2), round(t1, 2)],
        "peak_speed_cm_s": round(peak, 1),
        "over_limit_fraction": round(over / max(1, total), 4),
        "max_cm_s": max_cm_s,
    }


def check_max_altitude(
    data,
    fps: int,
    t0: float,
    t1: float,
    max_z_cm: float = 210.0,
) -> tuple[bool, dict]:
    """否定约束确认（"别飞太高"）：窗口内所有机 Z 不超过上限。"""
    step = 1.0 / min(fps, 20)
    peak = 0.0
    offender = None
    for k in range(len(data)):
        t = t0
        while t <= t1 + 1e-9:
            z = drone_position_at(data, fps, k, t)[2]
            if z > peak:
                peak = z
                offender = k
            t += step
    ok = peak <= max_z_cm
    return ok, {
        "window": [round(t0, 2), round(t1, 2)],
        "peak_z_cm": round(peak, 1),
        "offender": offender,
        "max_z_cm": max_z_cm,
    }


def check_collinear(
    data,
    fps: int,
    t_s: float,
    max_residual_cm: float = 35.0,
    min_span_cm: float = 250.0,
) -> tuple[bool, dict]:
    """队形级指令确认（"排成一条斜线"）：t 时刻全队 XY 共线且铺开。

    对 XY 做主方向拟合（质心+主轴），残差=各机到主轴距离。
    """
    pts = [drone_position_at(data, fps, k, t_s)[:2] for k in range(len(data))]
    n = len(pts)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - cx) ** 2 for p in pts)
    syy = sum((p[1] - cy) ** 2 for p in pts)
    sxy = sum((p[0] - cx) * (p[1] - cy) for p in pts)
    # 主轴方向（2x2 协方差最大特征向量）
    angle = 0.5 * math.atan2(2 * sxy, sxx - syy)
    ux, uy = math.cos(angle), math.sin(angle)
    residuals = [abs(-(p[0] - cx) * uy + (p[1] - cy) * ux) for p in pts]
    projections = [(p[0] - cx) * ux + (p[1] - cy) * uy for p in pts]
    span = max(projections) - min(projections)
    ok = max(residuals) <= max_residual_cm and span >= min_span_cm
    return ok, {
        "t_s": round(t_s, 2),
        "max_residual_cm": round(max(residuals), 1),
        "span_cm": round(span, 1),
        "limits": {"max_residual_cm": max_residual_cm, "min_span_cm": min_span_cm},
    }


def check_group_hold(
    data,
    fps: int,
    t0: float,
    t1: float,
    min_hold_s: float = 1.6,
    max_drift_cm: float = 12.0,
    require_lit: bool = True,
) -> tuple[bool, dict]:
    """"到位后全体定住 N 秒"确认：窗口内存在 ≥min_hold_s 的区间，
    所有机位移 <max_drift_cm 且（可选）灯亮。"""
    step = 1.0 / min(fps, 20)
    times = []
    t = t0
    while t <= t1 + 1e-9:
        times.append(t)
        t += step
    best = 0.0
    best_start = None
    anchor = None
    anchor_t = None
    for t in times:
        pos = [drone_position_at(data, fps, k, t) for k in range(len(data))]
        lit = all(drone_color_at(data, fps, k, t) is not None for k in range(len(data)))
        # 相对定格起点（锚点）的累计位移——逐点比较会放过慢速持续漂移
        still = (
            anchor is not None
            and all(math.dist(a, b) <= max_drift_cm for a, b in zip(pos, anchor))
            and (lit or not require_lit)
        )
        if still:
            duration = t - anchor_t
            if duration > best:
                best = duration
                best_start = anchor_t
        else:
            anchor = pos
            anchor_t = t
    ok = best >= min_hold_s
    return ok, {
        "window": [round(t0, 2), round(t1, 2)],
        "longest_hold_s": round(best, 2),
        "hold_start_s": round(best_start, 2) if best_start is not None else None,
        "min_hold_s": min_hold_s,
    }


def check_sync_pulses(
    data,
    fps: int,
    t0: float,
    t1: float,
    expected_pulses: int = 3,
    sync_tol_s: float = 0.3,
    on_threshold: int = 150,
    off_threshold: int = 60,
) -> tuple[bool, dict]:
    """"全体同步爆闪 N 下"确认：各机亮度脉冲数 ≥N，且各次脉冲起点跨机对齐。"""
    step = 1.0 / min(fps, 30)
    pulse_starts: dict[int, list[float]] = {}
    for k in range(len(data)):
        starts = []
        on = False
        t = t0
        while t <= t1 + 1e-9:
            rgb = drone_color_at(data, fps, k, t)
            level = brightness(rgb) if rgb is not None else 0
            if not on and level >= on_threshold:
                on = True
                starts.append(round(t, 2))
            elif on and level <= off_threshold:
                on = False
            t += step
        pulse_starts[k] = starts
    counts = {k: len(v) for k, v in pulse_starts.items()}
    enough = all(c >= expected_pulses for c in counts.values())
    synced = True
    spreads = []
    if enough:
        for i in range(expected_pulses):
            onsets = [pulse_starts[k][i] for k in pulse_starts]
            spread = max(onsets) - min(onsets)
            spreads.append(round(spread, 2))
            if spread > sync_tol_s:
                synced = False
    ok = enough and synced
    return ok, {
        "pulse_counts": counts,
        "expected_pulses": expected_pulses,
        "pulse_spreads_s": spreads,
        "sync_tol_s": sync_tol_s,
    }


def check_dark_multicolor(
    data,
    fps: int,
    t0: float,
    t1: float,
    min_hue_buckets: int = 4,
    max_brightness: int = 130,
    min_brightness: int = 15,
    min_fraction: float = 0.7,
) -> tuple[bool, dict]:
    """"五彩斑斓的黑"确认：多色相 + 低亮度微光（不灭灯、不亮场）。"""
    mid = (t0 + t1) / 2.0
    hue_ok, hue_detail = check_hue_diversity(data, fps, mid, min_hue_buckets=min_hue_buckets)
    step = 1.0 / min(fps, 20)
    qualified = 0
    peaks: dict[int, int] = {}
    for k in range(len(data)):
        levels = []
        t = t0
        while t <= t1 + 1e-9:
            rgb = drone_color_at(data, fps, k, t)
            if rgb is not None:
                levels.append(brightness(rgb))
            t += step
        peak = max(levels) if levels else 0
        floor = min(levels) if levels else 0
        peaks[k] = peak
        if levels and peak <= max_brightness and peak >= min_brightness and floor >= 0:
            qualified += 1
    frac = qualified / max(1, len(data))
    ok = hue_ok and frac >= min_fraction
    return ok, {
        "hues": hue_detail,
        "brightness_peaks": peaks,
        "dark_qualified_fraction": round(frac, 3),
        "limits": {"max_brightness": max_brightness, "min_hue_buckets": min_hue_buckets},
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
