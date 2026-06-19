#!/usr/bin/env python3
"""Continuity gate regression tests."""
from core.validator import (
    ValidationResult,
    _check_effective_motion,
    _check_degradation,
    _check_agent_helper_leak,
    _check_static_code_quality,
    _check_motion_envelope,
    _check_motion_quality,
    _repair_timing_plan,
)


def test_hover_blocks_formal_segment():
    result = ValidationResult(
        compile_ok=True,
        run_ok=True,
        read_fii_ok=True,
        distance_warnings=0,
        action_warnings=0,
        dense_min_distance_cm=80,
        continuity_required=True,
        hover_check_ok=True,
        hover_segments=[(28.2, 31.0)],
        motion_envelope_ok=True,
        motion_quality_ok=True,
    )
    assert not result.passed
    assert "整体悬停" in result.repair_feedback()


def test_crossing_collision_directs_group_relay_recipe():
    # A <20cm mid-flight min-distance = two flight paths crossing (对穿). The repair
    # feedback must diagnose the crossing and name the strongest safe recipe
    # (group_relay sequential) so the model stops re-deriving it across rounds.
    result = ValidationResult(
        compile_ok=True,
        run_ok=True,
        read_fii_ok=True,
        distance_warnings=3,
        action_warnings=0,
        dense_min_distance_cm=1.4,
        min_distance_cm=1.4,
        collision_intervals=[
            {"start_s": 25.0, "end_s": 29.0, "min_time_s": 25.3,
             "min_distance_cm": 1.4, "pair": (0, 5)},
        ],
        continuity_required=True,
        hover_check_ok=True,
        motion_envelope_ok=True,
        motion_quality_ok=True,
    )
    fb = result.repair_feedback()
    assert not result.passed
    assert "对穿" in fb and "航线交叉" in fb
    assert "group_relay" in fb, "must name the zero-crossing recipe"


def test_endpoint_proximity_does_not_trigger_crossing_diagnosis():
    # A collision interval whose min-distance is >=20cm is endpoint-proximity, not a
    # crossing — must NOT emit the group_relay crossing prescription (avoid over-firing).
    result = ValidationResult(
        compile_ok=True,
        run_ok=True,
        read_fii_ok=True,
        distance_warnings=1,
        action_warnings=0,
        dense_min_distance_cm=44.0,
        min_distance_cm=44.0,
        collision_intervals=[
            {"start_s": 30.0, "end_s": 31.0, "min_time_s": 30.5,
             "min_distance_cm": 44.0, "pair": (3, 6)},
        ],
        continuity_required=True,
        hover_check_ok=True,
        motion_envelope_ok=True,
        motion_quality_ok=True,
    )
    fb = result.repair_feedback()
    assert "group_relay" not in fb, "endpoint proximity must not trigger the crossing recipe"


def test_takeoff_landing_exempt_from_continuity_gate():
    result = ValidationResult(
        compile_ok=True,
        run_ok=True,
        read_fii_ok=True,
        distance_warnings=0,
        action_warnings=0,
        dense_min_distance_cm=80,
        continuity_required=False,
        hover_check_ok=True,
        hover_segments=[(1.0, 3.0)],
        motion_envelope_ok=True,
        motion_quality_ok=False,
    )
    # 空模板无exit_state → passed=False（exit_state 硬契约）
    assert not result.passed, "空模板应不通过（无exit_state）"
    assert "整体悬停" not in result.repair_feedback()


def test_motion_envelope_for_5_to_13_segment():
    # Start within SEGMENT_EDGE_BUFFER_S (1.3s) of the window start is on time.
    assert _check_motion_envelope((5, 13), 5.8, 12.4) == []
    assert _check_motion_envelope((5, 13), 6.2, 12.4) == []  # 6.2 < 5+1.3 deadline
    # Clearly past the start deadline (6.3s) is flagged late.
    assert _check_motion_envelope((5, 13), 7.0, 12.4)
    # Early finish is no longer a hard gate; auto_init can compress the next segment.
    assert _check_motion_envelope((5, 13), 5.8, 10.0) == []


def test_effective_motion_blocks_tail_filler_and_low_activity():
    assert _check_effective_motion((13, 23), 13.4, 22.3, []) == []
    assert _check_effective_motion((13, 23), 13.4, 16.0, []) == []
    assert _check_effective_motion((13, 23), 13.4, 15.0, [])
    assert _check_effective_motion((13, 23), 13.4, 22.3, [(20.2, 22.0)])


def test_motion_quality_blocks_small_jitter():
    assert _check_motion_quality(
        (4, 24),
        {
            "drone_count": 7,
            "moving_drones": 0,
            "median_path_cm": 24.0,
            "median_excursion_cm": 8.0,
            "max_excursion_cm": 12.0,
        },
    )
    assert _check_motion_quality(
        (4, 24),
        {
            "drone_count": 7,
            "moving_drones": 7,
            "median_path_cm": 190.0,
            "median_excursion_cm": 95.0,
            "max_excursion_cm": 190.0,
        },
    ) == []


def test_degradation_blocks_obvious_lanes_and_rigid_circle():
    assert _check_degradation(
        (4, 14),
        {
            "drone_count": 7,
            "lane_x_locked_drones": 6,
            "lane_y_locked_drones": 0,
            "circle_like_fraction": 0.0,
            "order_stable_fraction": 0.0,
            "radius_range_cm": 120.0,
            "fixed_height_drones": 0,
            "window_z_range_cm": 80.0,
            "flat_height_fraction": 0.2,
        },
    )
    assert _check_degradation(
        (4, 14),
        {
            "drone_count": 7,
            "lane_x_locked_drones": 0,
            "lane_y_locked_drones": 0,
            "circle_like_fraction": 0.9,
            "order_stable_fraction": 0.95,
            "radius_range_cm": 20.0,
            "fixed_height_drones": 0,
            "window_z_range_cm": 80.0,
            "flat_height_fraction": 0.2,
        },
    )
    assert _check_degradation(
        (4, 14),
        {
            "drone_count": 7,
            "lane_x_locked_drones": 0,
            "lane_y_locked_drones": 0,
            "circle_like_fraction": 0.2,
            "order_stable_fraction": 0.2,
            "radius_range_cm": 100.0,
            "fixed_height_drones": 6,
            "window_z_range_cm": 12.0,
            "flat_height_fraction": 0.9,
        },
    )
    assert _check_degradation(
        (4, 14),
        {
            "drone_count": 7,
            "lane_x_locked_drones": 1,
            "lane_y_locked_drones": 1,
            "circle_like_fraction": 0.4,
            "order_stable_fraction": 0.5,
            "radius_range_cm": 100.0,
            "fixed_height_drones": 1,
            "window_z_range_cm": 80.0,
            "flat_height_fraction": 0.3,
        },
    ) == []


def test_agent_motion_helpers_do_not_belong_in_design_py():
    errors = _check_agent_helper_leak(
        """
def dist3(a, b):
    return 0

def flight_time_ms(distance_cm, v, a):
    return 0
"""
    )
    assert errors
    assert "agent 侧运动学工具" in errors[0]


def test_code_quality_blocks_segment_imports_and_best_assign_definition():
    errors = _check_static_code_quality(
        """
import itertools

def best_assign(starts, targets):
    return (), 0
"""
    )
    assert any("不要新增 import" in item for item in errors)
    assert any("best_assign" in item for item in errors)


def test_code_quality_blocks_decimal_inittime():
    errors = _check_static_code_quality("drone.inittime(4.0)\n")
    assert errors
    assert "inittime" in errors[0]


def test_code_quality_blocks_float_variable_inittime():
    errors = _check_static_code_quality("start_s = 13.0\ndrone.inittime(start_s)\n")
    assert errors
    assert "浮点变量" in errors[0]


def test_code_quality_requires_velocity_pairing():
    errors = _check_static_code_quality(
        """
drone.inittime(4)
drone.VelXY(120, 180)
drone.move2(100, 100, 120)
"""
    )
    assert errors
    assert "VelZ" in errors[0]


def test_code_quality_accepts_paired_integer_timing():
    assert _check_static_code_quality(
        """
drone.inittime(4)
drone.VelXY(speed, accel)
drone.VelZ(speed, accel)
drone.move2(100, 100, 120)
"""
    ) == []


def test_repair_timing_plan_reports_late_start_only():
    assert _repair_timing_plan((4, 13), 4.1, 10.2) == ""
    text = _repair_timing_plan((4, 13), 5.5, 10.2)
    assert "启动晚了" in text
    assert "auto_init" in text


if __name__ == "__main__":
    test_hover_blocks_formal_segment()
    test_takeoff_landing_exempt_from_continuity_gate()
    test_motion_envelope_for_5_to_13_segment()
    test_effective_motion_blocks_tail_filler_and_low_activity()
    test_motion_quality_blocks_small_jitter()
    test_degradation_blocks_obvious_lanes_and_rigid_circle()
    test_agent_motion_helpers_do_not_belong_in_design_py()
    test_code_quality_blocks_segment_imports_and_best_assign_definition()
    test_code_quality_blocks_decimal_inittime()
    test_code_quality_blocks_float_variable_inittime()
    test_code_quality_requires_velocity_pairing()
    test_code_quality_accepts_paired_integer_timing()
    test_repair_timing_plan_reports_late_start_only()
    print("OK")
