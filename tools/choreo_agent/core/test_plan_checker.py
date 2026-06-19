"""Deterministic plan-checker (calculator) tests for choreo_agent."""

from core.planning_pass import (
    build_plan_revision_prompt,
    build_planning_prompt,
    evaluate_plan_safety,
)
from core.validator import motion_quality_minimums


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


def test_salvageable_floor_directs_far_assign():
    # rotate(steps=1) forces a crossing, BUT best_assign keeps the two drones 300cm
    # apart (identity) — a collision-free permutation EXISTS (opt_md>=51). The directive
    # must name far_assign (switch the mapping), NOT mirror (points are not too close).
    prev = [[100, 100, 120], [400, 100, 120]]
    targets = [[100, 100, 120], [400, 100, 120]]
    kf = _kf(targets, duration_s=4.0)
    kf["assign"] = "rotate"
    kf["rotate_steps"] = 1
    ok, report = evaluate_plan_safety({"keyframes": [kf]}, prev, drone_count=2)
    assert not ok
    assert "转场路径最小间距" in report
    assert "最优排列可达" in report
    assert "far_assign" in report
    assert "mirror_assign" not in report, "a salvageable permutation must not be sent to mirror"


def test_unsalvageable_floor_directs_mirror():
    # Two drones must converge onto two targets only 52cm apart: NO permutation clears
    # 51cm (opt_md<51). far_assign cannot help (best already maximizes clearance) — the
    # directive must say so and route to mirror+错峰 / spread-the-points.
    prev = [[100, 100, 120], [100, 200, 120]]
    targets = [[400, 100, 120], [452, 100, 120]]
    kf = _kf(targets, duration_s=4.0)  # default assign=best
    ok, report = evaluate_plan_safety({"keyframes": [kf]}, prev, drone_count=2)
    assert not ok
    assert "连最优排列" in report
    assert "mirror_assign" in report and "错峰" in report
    assert "far_assign 都无效" in report, "must tell the model far_assign cannot help here"


def test_feasible_path_band_printed_on_pass():
    # Every keyframe gets a readout band [motion-min, flight-max] to kill the climax
    # too-big<->too-small oscillation. Lower bound == motion_quality_minimums (no new gate).
    ok, report = evaluate_plan_safety({"keyframes": [_kf(_SPREAD_9)]}, _PREV_9, drone_count=9)
    assert ok, report
    assert "可行路径带" in report
    lo = int(motion_quality_minimums(3.2, 9)["min_max_excursion_cm"])
    assert f"[{lo}," in report, "band lower bound must be the motion-quality minimum"


def test_feasible_band_inversion_message():
    # A 0.6s keyframe cannot fit even the minimum motion-quality move at clamped speed:
    # report must direct raising duration/speed, never relax the floor.
    kf = _kf(_SPREAD_9, duration_s=0.6)
    _ok, report = evaluate_plan_safety({"keyframes": [kf]}, _PREV_9, drone_count=9)
    assert "窗口太短" in report
    assert "提高 duration_s 或 speed" in report


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
