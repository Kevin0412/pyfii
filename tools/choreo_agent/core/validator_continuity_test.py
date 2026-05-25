#!/usr/bin/env python3
"""Continuity gate regression tests."""
from validator import ValidationResult, _check_motion_envelope


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
    )
    assert result.passed
    assert "整体悬停" not in result.repair_feedback()


def test_motion_envelope_for_5_to_13_segment():
    assert _check_motion_envelope((5, 13), 5.8, 12.4) == []
    assert _check_motion_envelope((5, 13), 6.0, 12.4)
    assert _check_motion_envelope((5, 13), 5.8, 12.0)


if __name__ == "__main__":
    test_hover_blocks_formal_segment()
    test_takeoff_landing_exempt_from_continuity_gate()
    test_motion_envelope_for_5_to_13_segment()
    print("OK")
