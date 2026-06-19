"""Deterministic plan-checker (calculator) tests for choreo_agent."""

from core.planning_pass import (
    build_plan_revision_prompt,
    build_planning_prompt,
    evaluate_plan_safety,
)


def _kf(targets, start_s=13.0, duration_s=3.2, speed=170, accel=320):
    return {
        "start_s": start_s,
        "duration_s": duration_s,
        "feel": "crisp_expand",
        "targets": targets,
        "speed_cm_s": speed,
        "accel_cm_s2": accel,
        "light_color": "#44aaff",
        "light_ticks": 4,
    }


_PREV_9 = [
    [80, 80, 110], [280, 80, 110], [480, 80, 110],
    [80, 280, 110], [280, 280, 110], [480, 280, 110],
    [80, 480, 110], [280, 480, 110], [480, 480, 110],
]

_SPREAD_9 = [
    [60, 60, 120], [280, 60, 210], [500, 60, 120],
    [60, 280, 180], [280, 280, 240], [500, 280, 180],
    [60, 500, 120], [280, 500, 210], [500, 500, 120],
]


def test_clean_plan_passes():
    ok, report = evaluate_plan_safety(
        {"keyframes": [_kf(_SPREAD_9)]}, _PREV_9, drone_count=9
    )
    assert ok, report
    assert "PASS" in report
    assert "最小 XY 间距" in report


def test_spacing_below_floor_violates():
    targets = [list(p) for p in _SPREAD_9]
    targets[1] = [100, 60, 210]  # 40cm from (60,60) — below 51cm floor
    ok, report = evaluate_plan_safety(
        {"keyframes": [_kf(targets)]}, _PREV_9, drone_count=9
    )
    assert not ok
    assert "硬下限" in report


def test_tight_cluster_51_90_allowed_with_note():
    # 65cm apart (51-90 band), paths stay collinear and 65cm separated — density is free.
    prev = [[100, 100, 120], [400, 100, 120]]
    targets = [[200, 100, 120], [265, 100, 120]]
    ok, report = evaluate_plan_safety(
        {"keyframes": [_kf(targets)]}, prev, drone_count=2
    )
    assert ok, report
    assert "≥ 51cm OK" in report


def test_out_of_bounds_violates():
    targets = [list(p) for p in _SPREAD_9]
    targets[0] = [600, 60, 300]
    ok, report = evaluate_plan_safety(
        {"keyframes": [_kf(targets)]}, _PREV_9, drone_count=9
    )
    assert not ok
    assert "坐标越界" in report


def test_wrong_target_count_violates():
    ok, report = evaluate_plan_safety(
        {"keyframes": [_kf(_SPREAD_9[:7])]}, _PREV_9, drone_count=9
    )
    assert not ok
    assert "数量" in report


def test_path_spacing_conflict_violates():
    # Targets 52cm apart pass the 51cm point-table floor, but the straight-line
    # transitions converge mid-flight below 51cm under every assignment.
    prev = [[100, 100, 120], [100, 200, 120]]
    targets = [[400, 100, 120], [452, 100, 120]]
    ok, report = evaluate_plan_safety(
        {"keyframes": [_kf(targets)]}, prev, drone_count=2
    )
    assert not ok
    assert "转场路径最小间距" in report


def test_rotate_floor_names_exchange_escape():
    # An aligned 2-column rotate(steps=1) sends drones straight through each other
    # (synced path ~0cm < 51cm). The violation must name the exchange-safe escape
    # primitives so the model stops thrashing (the S03 12-round root cause).
    prev = [[100, 100, 120], [400, 100, 120]]
    targets = [[100, 100, 120], [400, 100, 120]]
    kf = _kf(targets, duration_s=4.0)
    kf["assign"] = "rotate"
    kf["rotate_steps"] = 1
    ok, report = evaluate_plan_safety({"keyframes": [kf]}, prev, drone_count=2)
    assert not ok
    assert "转场路径最小间距" in report
    assert "mirror_assign" in report
    assert "far_assign" in report
    assert "错峰" in report


def test_swap_floor_names_exchange_escape():
    # swap on an aligned pair likewise grazes the floor; same escape hint applies.
    prev = [[100, 100, 120], [100, 200, 120]]
    targets = [[400, 100, 120], [452, 100, 120]]
    kf = _kf(targets, duration_s=4.0)
    kf["assign"] = "swap"
    ok, report = evaluate_plan_safety({"keyframes": [kf]}, prev, drone_count=2)
    assert not ok
    assert "mirror_assign" in report and "far_assign" in report


def test_infeasible_flight_time_violates():
    prev = [[0, 100, 120], [0, 300, 120]]
    targets = [[540, 100, 120], [540, 300, 120]]
    ok, report = evaluate_plan_safety(
        {"keyframes": [_kf(targets, duration_s=1.0, speed=100, accel=200)]},
        prev,
        drone_count=2,
    )
    assert not ok
    assert "最长飞行" in report


def test_empty_plan_violates():
    ok, report = evaluate_plan_safety({"keyframes": []}, _PREV_9, drone_count=9)
    assert not ok


def test_revision_prompt_contains_plan_and_report():
    plan = {"keyframes": [_kf(_SPREAD_9)]}
    prompt = build_plan_revision_prompt(plan, "## 规划检查报告\n- 违规: 测试", "S02")
    assert "S02" in prompt
    assert "规划检查报告" in prompt
    assert '"keyframes"' in prompt
    assert "只输出完整修正后的 JSON" in prompt


def test_planning_prompt_has_no_seeds():
    prompt = build_planning_prompt(
        "S02", 13.0, 23.0, "展开", _PREV_9, drone_count=9
    )
    assert "seed_box" not in prompt
    assert "seed_slant" not in prompt
    assert "seed_asym" not in prompt
    assert "检查器" in prompt


def test_overclaimed_speed_is_clamped_in_feasibility():
    # 700cm 路径 1.5s：模型声称 speed=500 也必须按物理上限 200 收紧 → 不可行
    prev = [[0, 100, 120], [0, 300, 120]]
    targets = [[540, 500, 250], [540, 80, 250]]
    ok, report = evaluate_plan_safety(
        {"keyframes": [_kf(targets, duration_s=1.5, speed=500, accel=900)]},
        prev,
        drone_count=2,
    )
    assert not ok
    assert "最长飞行" in report


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASSED: {name}")
    print("\nALL PLAN CHECKER TESTS PASSED")
