"""Intent-assign family tests: 转场即编舞，分配不再只有一个答案。"""

import importlib.util
import sys
from math import cos, pi, sin
from pathlib import Path

# 加载 project_template 的 function.py（独立模块，非包）
_FUNC_PATH = Path(__file__).resolve().parents[1] / "project_template" / "scripts" / "function.py"
_spec = importlib.util.spec_from_file_location("template_function", _FUNC_PATH)
_func = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_func)

from core.planning_pass import evaluate_plan_safety

RING_PREV = [(280 + 200 * cos(2 * pi * k / 8), 280 + 200 * sin(2 * pi * k / 8), 150) for k in range(8)]
RING_TARGETS = [(280 + 200 * cos(2 * pi * k / 8), 280 + 200 * sin(2 * pi * k / 8), 150) for k in range(8)]


def test_keep_assign_preserves_order():
    targets = [(100, 100, 120), (300, 100, 180), (500, 100, 240)]
    out = _func.keep_assign([(0, 0, 100)] * 3, targets)
    assert [t[:2] for t in out] == [(100, 100), (300, 100), (500, 100)]


def test_rotate_assign_shifts_one_ring_position():
    out = _func.rotate_assign(RING_PREV, RING_TARGETS, steps=1)
    # 每架机的新目标应是环上相邻位（距离 ≈ 2*200*sin(pi/8) ≈ 153cm，而非 0 或对径 400）
    for prev, target in zip(RING_PREV, out):
        d = ((prev[0] - target[0]) ** 2 + (prev[1] - target[1]) ** 2) ** 0.5
        assert 120 < d < 190, d
    # 旋转保持队形：目标集合不变
    assert sorted(t[:2] for t in out) == sorted((round(t[0]), round(t[1])) for t in RING_TARGETS)


def test_mirror_assign_maps_to_reflection():
    prev = [(100, 280, 150), (460, 280, 150)]
    targets = [(120, 280, 150), (440, 280, 150)]  # centroid x=280
    out = _func.mirror_assign(prev, targets)
    # 左机(100)的反射点在 460 → 应得右目标(440)；右机得左目标
    assert out[0][0] == 440 and out[1][0] == 120


def test_swap_assign_exchanges_halves():
    prev = [(100, 100, 150), (150, 200, 150), (450, 100, 150), (500, 200, 150)]
    targets = [(110, 150, 150), (160, 250, 150), (460, 150, 150), (510, 250, 150)]
    out = _func.swap_assign(prev, targets, axis="x")
    # 左半机(100/150)应得右半目标(460/510)，右半机得左半目标
    assert all(t[0] >= 460 for t in out[:2])
    assert all(t[0] <= 160 for t in out[2:])


def _kf(targets, **kw):
    base = {
        "start_s": 13.0, "duration_s": 3.2, "feel": "x", "targets": targets,
        "speed_cm_s": 170, "accel_cm_s2": 320, "light_color": "#fff", "light_ticks": 4,
    }
    base.update(kw)
    return base


def test_checker_mirror_skips_path_check_with_stagger_note():
    prev = [[100, 280, 150], [460, 280, 150]]
    targets = [[120, 280, 150], [440, 280, 150]]  # 对穿：同步直线间距趋零
    ok, report = evaluate_plan_safety(
        {"keyframes": [_kf(targets, assign="mirror")]}, prev, drone_count=2
    )
    assert ok, report  # mirror 不因同步路径判违规
    assert "错峰" in report
    # 同样的 targets 用默认 best 检查也 OK（best 会选不交叉的映射）
    ok2, _ = evaluate_plan_safety({"keyframes": [_kf(targets)]}, prev, drone_count=2)
    assert ok2


def test_checker_keep_flags_real_crossing():
    prev = [[100, 280, 150], [460, 280, 150]]
    targets = [[440, 280, 150], [120, 280, 150]]  # keep 强制对穿
    ok, report = evaluate_plan_safety(
        {"keyframes": [_kf(targets, assign="keep")]}, prev, drone_count=2
    )
    assert not ok
    assert "keep_assign" in report


def test_checker_rotate_on_ring_passes():
    prev = [[round(p[0]), round(p[1]), 150] for p in RING_PREV]
    targets = [[round(p[0]), round(p[1]), 150] for p in RING_TARGETS]
    ok, report = evaluate_plan_safety(
        {"keyframes": [_kf(targets, assign="rotate", rotate_steps=1, duration_s=2.5)]},
        prev,
        drone_count=8,
    )
    assert ok, report
    assert "rotate_assign" in report


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASSED: {name}")
    print("\nALL ASSIGN FAMILY TESTS PASSED")
