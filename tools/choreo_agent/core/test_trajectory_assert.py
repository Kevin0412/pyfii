"""trajectory_assert 原语的离线验证（合成帧数据，帧结构同 read.py dots2line）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.trajectory_assert import (
    blue_dominant,
    check_brightness_modulation,
    check_color_window,
    check_drone_at,
    check_drone_in_box,
    check_hue_diversity,
    check_no_new_degradation,
    check_relative_shift,
    check_spatial_temporal_order,
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
    print("PASSED: rainbow wave primitives")


if __name__ == "__main__":
    test_check_drone_at_tolerance()
    test_color_conversion_and_window()
    test_no_new_degradation_tolerances()
    test_box_and_relative_shift()
    test_rainbow_wave_primitives()
    print("\nALL TRAJECTORY ASSERT TESTS PASSED")
