"""trajectory_assert 原语的离线验证（合成帧数据，帧结构同 read.py dots2line）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.trajectory_assert import (
    blue_dominant,
    check_brightness_modulation,
    check_collinear,
    check_color_window,
    check_dark_multicolor,
    check_drone_at,
    check_drone_in_box,
    check_group_hold,
    check_hue_diversity,
    check_no_new_degradation,
    check_relative_shift,
    check_spatial_temporal_order,
    check_sync_pulses,
    drone_color_at,
    hue_deg,
)

FPS = 60


def _drone_frames(xyz, bgr, seconds=2.0):
    frames = []
    for i in range(int(seconds * FPS)):
        frames.append((i / FPS, xyz[0], xyz[1], xyz[2], 0.0, bgr, 0))
    return frames


def _data():
    return [
        _drone_frames((140, 140, 180), (200, 50, 10)),   # 蓝灯（BGR），定点
        _drone_frames((300, 300, 150), (10, 50, 200)),   # 红灯（BGR）
        _drone_frames((420, 200, 200), (-1, -1, -1)),    # 灯未设置
    ]


def test_check_drone_at_tolerance():
    data = _data()
    ok, detail = check_drone_at(data, FPS, 0, 1.5, (140, 140, 180), tol_cm=25)
    assert ok and detail["distance_cm"] == 0.0
    ok, detail = check_drone_at(data, FPS, 0, 1.5, (200, 140, 180), tol_cm=25)
    assert not ok and detail["distance_cm"] == 60.0
    print("PASSED: check_drone_at tolerance")


def test_color_conversion_and_window():
    data = _data()
    assert drone_color_at(data, FPS, 0, 1.0) == (10, 50, 200)  # BGR→RGB
    assert drone_color_at(data, FPS, 2, 1.0) is None  # 未设置
    assert blue_dominant((10, 50, 200)) and not blue_dominant((200, 50, 10))

    ok, detail = check_color_window(data, FPS, 0.5, 1.8, blue_dominant, drones=[0])
    assert ok and detail["worst_fraction"] == 1.0
    ok, detail = check_color_window(data, FPS, 0.5, 1.8, blue_dominant, drones=[0, 1])
    assert not ok, "红灯机不该通过蓝色谓词"
    print("PASSED: color conversion and window fraction")


def test_no_new_degradation_tolerances():
    before = {
        "lane_x_locked_drones": 1, "lane_y_locked_drones": 0, "fixed_height_drones": 1,
        "circle_like_fraction": 0.2, "flat_height_fraction": 0.1,
        "order_stable_fraction": 0.5, "window_z_range_cm": 120.0,
    }
    ok, _ = check_no_new_degradation(before, dict(before))
    assert ok
    worse = dict(before, lane_x_locked_drones=2)  # +1 在容差内
    ok, _ = check_no_new_degradation(before, worse)
    assert ok
    collapsed = dict(before, lane_x_locked_drones=5, circle_like_fraction=0.9)
    ok, detail = check_no_new_degradation(before, collapsed)
    assert not ok and len(detail["problems"]) == 2
    # 低位占比抖动是代际噪声，不算新增塌缩（真实案例：order_stable 0.14→0.31）
    noisy = dict(before, order_stable_fraction=0.31)
    ok, _ = check_no_new_degradation(dict(before, order_stable_fraction=0.14), noisy)
    assert ok
    flat = dict(before, window_z_range_cm=40.0)
    ok, detail = check_no_new_degradation(before, flat)
    assert not ok and any("collapsed" in p for p in detail["problems"])
    ok, detail = check_no_new_degradation({}, dict(before))
    assert ok and "skipped" in detail.get("note", "")
    print("PASSED: no_new_degradation tolerances")


def test_box_and_relative_shift():
    data = _data()
    ok, _ = check_drone_in_box(data, FPS, 0, 1.0, ((100, 200), (100, 200), (150, 220)))
    assert ok
    ok, detail = check_drone_in_box(data, FPS, 0, 1.0, ((200, 300), (100, 200), (150, 220)))
    assert not ok and detail["actual"][0] == 140.0

    # "再往左一点"：x 减 60，其他轴基本不动
    ok, detail = check_relative_shift((280, 280, 165), (220, 290, 160), axis=0, sign=-1)
    assert ok and detail["moved_cm"] == 60.0
    # 反方向 / 位移不足 / 其他轴乱跑 都要拒绝
    assert not check_relative_shift((280, 280, 165), (320, 280, 165), axis=0, sign=-1)[0]
    assert not check_relative_shift((280, 280, 165), (270, 280, 165), axis=0, sign=-1)[0]
    assert not check_relative_shift((280, 280, 165), (200, 480, 165), axis=0, sign=-1)[0]
    print("PASSED: box and relative shift predicates")


def _rainbow_data():
    """5 机：按 x 从左到右，颜色 onset 依次延后 0.3s；色相红→蓝紫；带亮度呼吸。"""
    hues_bgr = [(0, 0, 230), (0, 200, 230), (0, 210, 0), (230, 190, 0), (230, 0, 80)]
    data = []
    for i in range(5):
        frames = []
        onset_s = 0.5 + i * 0.3
        for f in range(int(4.0 * FPS)):
            t = f / FPS
            if t < onset_s:
                led = (-1, -1, -1)
            else:
                b, g, r = hues_bgr[i]
                # 呼吸：亮度在 40%-100% 摆动
                phase = 0.7 + 0.3 * ((f // 12) % 2)  # 简单方波摆动
                scale = 0.4 + 0.6 * (phase - 0.7) / 0.3 if phase > 0.7 else 0.4
                led = (int(b * scale), int(g * scale), int(r * scale))
            x = 80 + i * 100
            frames.append((t, x, 200, 150, 0.0, led, 0))
        data.append(frames)
    return data


def test_rainbow_wave_primitives():
    data = _rainbow_data()
    assert hue_deg((255, 0, 0)) == 0.0
    assert hue_deg((30, 30, 30)) is None  # 灰黑无色相

    ok, detail = check_spatial_temporal_order(
        data, FPS, 0.0, 3.5, lambda rgb: hue_deg(rgb) is not None,
        axis=0, ascending=True, min_span_s=0.6, max_inversions=1,
    )
    assert ok, detail

    ok, detail = check_hue_diversity(data, FPS, 3.0, min_hue_buckets=4)
    assert ok, detail

    ok, detail = check_brightness_modulation(data, FPS, 2.0, 3.8, min_amplitude=60, min_fraction=0.7)
    assert ok, detail

    # 同步点亮（onset 无先后）应被"依次"检查拒绝
    sync = [[(t / FPS, 80 + i * 100, 200, 150, 0.0, (0, 0, 230), 0) for t in range(int(2 * FPS))] for i in range(5)]
    ok, detail = check_spatial_temporal_order(
        sync, FPS, 0.0, 1.8, lambda rgb: rgb is not None and rgb[0] > 100,
        axis=0, min_span_s=0.6,
    )
    assert not ok, detail

    # 默认谓词（到达段尾最终色相）：前半段已有别的彩灯也不该误判 onset
    data2 = _rainbow_data()
    for frames in data2:  # 前半段统一预置黄绿干扰灯（色相 ~86°，与全部最终色相差 >30°）
        for f in range(len(frames)):
            t, x, y, z, a, led, acc = frames[f]
            if led == (-1, -1, -1):
                frames[f] = (t, x, y, z, a, (0, 255, 145), acc)
    ok, detail = check_spatial_temporal_order(
        data2, FPS, 0.0, 3.5, None, axis=0, min_span_s=0.6,
    )
    assert ok, detail  # 各机到达"自己段尾色相"的时刻仍是依次的
    print("PASSED: rainbow wave primitives")


def test_speed_and_altitude_limits():
    from core.trajectory_assert import check_max_altitude, check_max_speed

    slow = [
        [(f / FPS, 100 + i * 60 + f * 1.5, 200, 150, 0.0, (0, 120, 120), 0)
         for f in range(int(3 * FPS))]
        for i in range(3)
    ]  # 90cm/s
    ok, detail = check_max_speed(slow, FPS, 0.2, 2.6, max_cm_s=140.0)
    assert ok, detail
    fast = [
        [(f / FPS, 100 + i * 60 + f * 4, 200, 150, 0.0, (0, 120, 120), 0)
         for f in range(int(3 * FPS))]
        for i in range(3)
    ]  # 240cm/s
    ok, detail = check_max_speed(fast, FPS, 0.2, 2.6, max_cm_s=140.0)
    assert not ok and detail["peak_speed_cm_s"] > 200, detail

    low = [_drone_frames((100 + i * 80, 200, 180), (0, 120, 120)) for i in range(3)]
    ok, _ = check_max_altitude(low, FPS, 0.2, 1.8, max_z_cm=210.0)
    assert ok
    high = low + [_drone_frames((450, 200, 240), (0, 120, 120))]
    ok, detail = check_max_altitude(high, FPS, 0.2, 1.8, max_z_cm=210.0)
    assert not ok and detail["offender"] == 3 and detail["peak_z_cm"] == 240.0
    print("PASSED: speed and altitude limits")


def test_collinear_formation():
    # 斜线：y = x，7 机均匀铺开
    line = [
        _drone_frames((80 + i * 65, 80 + i * 65, 150), (0, 0, 200))
        for i in range(7)
    ]
    ok, detail = check_collinear(line, FPS, 1.0)
    assert ok, detail
    # 打散一机出线 80cm → 拒绝
    broken = [list(f) for f in line]
    broken[3] = _drone_frames((275, 195, 150), (0, 0, 200))
    ok, detail = check_collinear(broken, FPS, 1.0)
    assert not ok and detail["max_residual_cm"] > 35
    # 挤成一团（跨度不足）→ 拒绝
    cluster = [_drone_frames((280 + i * 10, 280, 150), (0, 0, 200)) for i in range(7)]
    ok, detail = check_collinear(cluster, FPS, 1.0)
    assert not ok and detail["span_cm"] < 250
    print("PASSED: collinear formation check")


def test_group_hold_detection():
    def moving_then_hold(i):
        frames = []
        for f in range(int(4.0 * FPS)):
            t = f / FPS
            x = 100 + i * 60 + (t * 50 if t < 1.0 else 50)  # 1s 后静止
            frames.append((t, x, 200, 150, 0.0, (0, 120, 120), 0))
        return frames

    data = [moving_then_hold(i) for i in range(5)]
    ok, detail = check_group_hold(data, FPS, 0.0, 3.8, min_hold_s=1.6)
    assert ok and detail["longest_hold_s"] >= 2.0, detail
    # 全程运动 → 无定格
    always_moving = [
        [(f / FPS, 100 + i * 60 + f, 200, 150, 0.0, (0, 120, 120), 0) for f in range(int(3 * FPS))]
        for i in range(5)
    ]
    ok, detail = check_group_hold(always_moving, FPS, 0.0, 2.8, min_hold_s=1.6)
    assert not ok, detail
    print("PASSED: group hold detection")


def test_sync_pulses():
    def flasher(offset_s):
        frames = []
        for f in range(int(6.0 * FPS)):
            t = f / FPS
            on = any(start + offset_s <= t < start + offset_s + 0.4 for start in (1.0, 2.0, 3.0))
            led = (200, 200, 200) if on else (10, 10, 10)
            frames.append((t, 100, 200, 150, 0.0, led, 0))
        return frames

    synced = [flasher(0.0) for _ in range(5)]
    ok, detail = check_sync_pulses(synced, FPS, 0.0, 5.5, expected_pulses=3)
    assert ok, detail
    # 一机错开 0.6s → 不同步
    ragged = [flasher(0.0) for _ in range(4)] + [flasher(0.6)]
    ok, detail = check_sync_pulses(ragged, FPS, 0.0, 5.5, expected_pulses=3, sync_tol_s=0.3)
    assert not ok, detail
    print("PASSED: sync pulses check")


def test_dark_multicolor():
    dark_hues_bgr = [(90, 20, 20), (20, 90, 20), (20, 20, 90), (80, 80, 10), (10, 80, 80)]
    data = [_drone_frames((100 + i * 80, 200, 150), dark_hues_bgr[i]) for i in range(5)]
    ok, detail = check_dark_multicolor(data, FPS, 0.2, 1.8)
    assert ok, detail
    # 亮场版本 → 拒绝（不是"黑"）
    bright = [_drone_frames((100 + i * 80, 200, 150), tuple(v * 2 + 40 for v in dark_hues_bgr[i])) for i in range(5)]
    ok, detail = check_dark_multicolor(bright, FPS, 0.2, 1.8)
    assert not ok, detail
    # 单色暗光 → 拒绝（不是"五彩斑斓"）
    mono = [_drone_frames((100 + i * 80, 200, 150), (90, 20, 20)) for i in range(5)]
    ok, detail = check_dark_multicolor(mono, FPS, 0.2, 1.8)
    assert not ok, detail
    print("PASSED: dark multicolor check")


if __name__ == "__main__":
    test_check_drone_at_tolerance()
    test_color_conversion_and_window()
    test_no_new_degradation_tolerances()
    test_box_and_relative_shift()
    test_rainbow_wave_primitives()
    test_collinear_formation()
    test_group_hold_detection()
    test_sync_pulses()
    test_dark_multicolor()
    print("\nALL TRAJECTORY ASSERT TESTS PASSED")
