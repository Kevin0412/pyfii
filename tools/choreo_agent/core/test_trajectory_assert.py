"""trajectory_assert 原语的离线验证（合成帧数据，帧结构同 read.py dots2line）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.trajectory_assert import (
    blue_dominant,
    check_color_window,
    check_drone_at,
    check_no_new_degradation,
    drone_color_at,
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
    flat = dict(before, window_z_range_cm=40.0)
    ok, detail = check_no_new_degradation(before, flat)
    assert not ok and any("collapsed" in p for p in detail["problems"])
    ok, detail = check_no_new_degradation({}, dict(before))
    assert ok and "skipped" in detail.get("note", "")
    print("PASSED: no_new_degradation tolerances")


if __name__ == "__main__":
    test_check_drone_at_tolerance()
    test_color_conversion_and_window()
    test_no_new_degradation_tolerances()
    print("\nALL TRAJECTORY ASSERT TESTS PASSED")
