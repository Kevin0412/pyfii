#!/usr/bin/env python3
"""Planning tool regression tests."""
from planning_tools import (
    assign_targets,
    budget_layers,
    timeline_cues,
    to_xyz,
)


def test_to_xyz_normalizes_2d_and_3d_points():
    assert to_xyz([(1.2, 2.6), (3.1, 4.2, 5.8)], default_z=110) == [
        (1, 3, 110),
        (3, 4, 6),
    ]


def test_timeline_cues_are_adjacent_and_cover_segment_body():
    cues = timeline_cues(4, 13, count=4, weights=[1, 1, 1, 1])
    assert len(cues) == 4
    assert round(cues[0].start_s, 2) == 4.15
    assert round(cues[-1].end_s, 2) == 12.65
    for left, right in zip(cues, cues[1:]):
        assert left.end_s == right.start_s


def test_assign_targets_returns_hardcode_ready_permutation():
    plan = assign_targets(
        [(0, 0, 110), (100, 0, 110), (200, 0, 110)],
        [(200, 0, 120), (100, 0, 130), (0, 0, 140)],
    )
    assert sorted(plan.perm) == [0, 1, 2]
    assert len(plan.assigned_targets) == 3


def test_budget_layers_returns_concrete_move_tables():
    prev = [(0, 0, 110), (140, 0, 110), (280, 0, 110)]
    layers = [
        [(0, 120, 130), (140, 120, 150), (280, 120, 130)],
        [(40, 220, 160), (180, 220, 180), (320, 220, 160)],
    ]
    cues = timeline_cues(4, 9, count=2)
    plans = budget_layers(prev, layers, cues, feels=["soft", "crisp"], light_ticks=6)
    assert len(plans) == 2
    for plan in plans:
        assert len(plan.moves) == 3
        assert sorted(plan.perm) == [0, 1, 2]
        for move in plan.moves:
            assert 20 <= move.speed_cm_s <= 200
            assert 50 <= move.accel_cm_s2 <= 400
            assert move.delay_ms >= 120


if __name__ == "__main__":
    test_to_xyz_normalizes_2d_and_3d_points()
    test_timeline_cues_are_adjacent_and_cover_segment_body()
    test_assign_targets_returns_hardcode_ready_permutation()
    test_budget_layers_returns_concrete_move_tables()
    print("OK")
