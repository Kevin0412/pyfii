#!/usr/bin/env python3
"""Continuity gate regression tests."""
from validator import (
    ValidationResult,
    _check_effective_motion,
    _check_degradation,
    _check_agent_helper_leak,
    _check_motion_envelope,
    _check_motion_quality,
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
    assert result.passed
    assert "整体悬停" not in result.repair_feedback()


def test_motion_envelope_for_5_to_13_segment():
    assert _check_motion_envelope((5, 13), 5.8, 12.4) == []
    assert _check_motion_envelope((5, 13), 6.0, 12.4)
    assert _check_motion_envelope((5, 13), 5.8, 12.0)


def test_effective_motion_blocks_tail_filler_and_low_activity():
    assert _check_effective_motion((13, 23), 13.4, 22.3, []) == []
    assert _check_effective_motion((13, 23), 13.4, 20.9, [])
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


if __name__ == "__main__":
    test_hover_blocks_formal_segment()
    test_takeoff_landing_exempt_from_continuity_gate()
    test_motion_envelope_for_5_to_13_segment()
    test_effective_motion_blocks_tail_filler_and_low_activity()
    test_motion_quality_blocks_small_jitter()
    test_degradation_blocks_obvious_lanes_and_rigid_circle()
    test_agent_motion_helpers_do_not_belong_in_design_py()
    print("OK")
