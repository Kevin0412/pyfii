import os
import sys
import unittest

path = os.getcwd() + r"/src/pyfii"
sys.path.append(path)

from extensions.nl_choreo.motion_phrase import (
    DroneGroup,
    MotionDesignSpec,
    MotionPhrase,
    MotionPrimitive,
    evaluate_motion_phrase_flexibility,
    validate_motion_design_spec,
    validate_phrase_design_direction,
)


def _phrase(
    phrase_id,
    start,
    end,
    primitives,
    groups=None,
    role_mapping=None,
):
    return MotionPhrase(
        phrase_id=phrase_id,
        start=start,
        end=end,
        intent=f"{phrase_id} intent",
        primitives=[MotionPrimitive(name=name) for name in primitives],
        groups=groups or [],
        role_mapping=role_mapping or {},
        risk="crossing center",
        repair_strategy="stagger entry timing",
    )


class TestNlChoreoMotionPhrase(unittest.TestCase):
    def test_phrase_metrics_capture_flexible_design(self):
        spec = MotionDesignSpec(
            user_intent="vibe edit",
            duration=20.0,
            phrases=[
                _phrase(
                    "P01",
                    0.0,
                    2.4,
                    ["curtain_sweep", "height_ripple"],
                    groups=[
                        DroneGroup(group_id="outer", drones=[1, 3, 5], role="outer arc"),
                        DroneGroup(group_id="inner", drones=[2, 4, 6, 7], role="delayed fold"),
                    ],
                ),
                _phrase("P02", 2.2, 6.7, ["compression", "late_release"]),
                _phrase(
                    "P03",
                    7.1,
                    10.0,
                    ["counter_braid", "role_exchange"],
                    groups=[DroneGroup(group_id="braid", drones=[1, 2, 6], role="counter motion")],
                ),
                _phrase("P04", 10.0, 15.8, ["orbit_sling", "falling_gate"], role_mapping={1: "lead", 5: "echo"}),
            ],
        )

        self.assertEqual(validate_motion_design_spec(spec), [])
        self.assertEqual(validate_phrase_design_direction(spec), [])
        metrics = evaluate_motion_phrase_flexibility(spec)
        self.assertEqual(metrics.phrase_count, 4)
        self.assertGreaterEqual(metrics.unique_primitive_count, 8)
        self.assertTrue(metrics.has_non_uniform_timing)
        self.assertEqual(metrics.overlapping_phrase_pairs, 1)
        self.assertEqual(metrics.grouped_phrase_ratio, 0.5)

    def test_design_direction_rejects_uniform_template_list(self):
        spec = MotionDesignSpec(
            user_intent="template grid",
            duration=12.0,
            phrases=[
                _phrase("P01", 0.0, 3.0, ["orbit"]),
                _phrase("P02", 3.0, 6.0, ["orbit"]),
                _phrase("P03", 6.0, 9.0, ["orbit"]),
                _phrase("P04", 9.0, 12.0, ["orbit"]),
            ],
        )

        errors = validate_phrase_design_direction(spec)
        self.assertTrue(any("insufficient motion vocabulary" in error for error in errors))
        self.assertTrue(any("insufficient subgroup choreography" in error for error in errors))
        self.assertTrue(any("insufficient phrase composition" in error for error in errors))
        self.assertTrue(any("phrase timing is too uniform" in error for error in errors))

    def test_design_direction_rejects_random_and_global_rotation(self):
        spec = MotionDesignSpec(
            user_intent="self-designed crosscut",
            duration=18.0,
            phrases=[
                _phrase(
                    "P01",
                    0.0,
                    2.4,
                    ["random_search", "crosscut"],
                    groups=[DroneGroup(group_id="slash", drones=[1, 3, 5], role="diagonal cut")],
                ),
                _phrase(
                    "P02",
                    2.4,
                    6.8,
                    ["global_rotation", "height_ripple"],
                    groups=[DroneGroup(group_id="counter", drones=[2, 4, 6, 7], role="counter layer")],
                ),
                _phrase("P03", 7.2, 11.0, ["compression", "late_release"]),
                _phrase("P04", 11.0, 18.0, ["opposed_shelves", "role_exchange"], role_mapping={1: "lead"}),
            ],
        )

        errors = validate_phrase_design_direction(spec)
        self.assertTrue(any("prohibited design primitive" in error for error in errors))
        self.assertTrue(any("random_search" in error for error in errors))
        self.assertTrue(any("global_rotation" in error for error in errors))

    def test_spec_validation_rejects_invalid_groups_and_roles(self):
        spec = MotionDesignSpec(
            user_intent="bad groups",
            duration=8.0,
            phrases=[
                _phrase(
                    "P01",
                    0.0,
                    4.0,
                    ["arc"],
                    groups=[
                        DroneGroup(group_id="dup", drones=[1, 8], role="bad"),
                        DroneGroup(group_id="dup", drones=[1, 2], role="bad"),
                    ],
                    role_mapping={0: "invalid", 3: ""},
                )
            ],
        )

        errors = validate_motion_design_spec(spec)
        self.assertTrue(any("duplicate group id" in error for error in errors))
        self.assertTrue(any("drone id out of range: 8" in error for error in errors))
        self.assertTrue(any("drone 1 appears in multiple groups" in error for error in errors))
        self.assertTrue(any("role mapping drone id out of range" in error for error in errors))
        self.assertTrue(any("role mapping for drone 3 is empty" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
