import os
import sys
import tempfile
import unittest

path = os.getcwd() + r"/src/pyfii"
sys.path.append(path)

from extensions.nl_choreo.contracts import FleetSpec
from extensions.nl_choreo.keyframe_workflow import (
    GPT55_BURST_RECOMPOSE_LAND_TIME_SEC,
    GPT55_BURST_RECOMPOSE_TIMELINE,
    emit_gpt55_burst_recompose_program,
    evaluate_timeline_dynamics,
    get_gpt55_burst_recompose_seed_info,
    validate_timeline_dynamics,
)

try:
    from extensions.nl_choreo.pipeline import PipelineConfig, _choose_direct_seed_program
except ModuleNotFoundError:
    PipelineConfig = None
    _choose_direct_seed_program = None


class TestNlChoreoKeyframeWorkflow(unittest.TestCase):
    def test_seed_metadata_is_complete_60s_choreography(self):
        info = get_gpt55_burst_recompose_seed_info()
        times = [layer[0] for layer in info.timeline]
        self.assertEqual(info.seed_id, "gpt55_burst_recompose")
        self.assertEqual(times[0], 1)
        self.assertEqual(times[-1], 58)
        self.assertEqual(info.land_time_sec, GPT55_BURST_RECOMPOSE_LAND_TIME_SEC)
        self.assertGreaterEqual(len(info.timeline), 7)
        self.assertEqual(len(info.design_sections), 4)
        self.assertGreaterEqual(len(info.scene_specs), 18)
        self.assertGreaterEqual(sum(scene[3] for scene in info.scene_specs), 18)
        self.assertEqual(info.design_sections[0][1], 1)
        self.assertEqual(info.design_sections[-1][2], 60)
        self.assertTrue(any("TurnOnAll(hex)" in note for note in info.notes))
        for _, _, points, _ in info.timeline:
            self.assertEqual(len(points), 7)

    def test_program_emitter_outputs_runnable_pyfii_script_shape(self):
        program = emit_gpt55_burst_recompose_program(
            output_path="output/test_gpt55_seed/nl_choreo_output",
            music_path="",
            render_fps=20,
        )
        self.assertIn("TIMELINE =", program)
        self.assertIn("DESIGN_SECTIONS =", program)
        self.assertIn("SCENES =", program)
        self.assertIn("LAND_TIME_SEC = 62", program)
        self.assertIn("speed_for_segment", program)
        self.assertIn("supported_pulse_color", program)
        self.assertIn("apply_scene_lights", program)
        self.assertIn("ANCHOR_POINTS_BY_TIME", program)
        self.assertIn("curve_strength", program)
        self.assertIn("d.TurnOnAll(supported_pulse_color", program)
        self.assertIn("d.TurnOffAll()", program)
        self.assertNotIn("orbit_point_float", program)
        self.assertNotIn("led_chase_pattern", program)
        self.assertIn("pf.Fii", program)
        self.assertIn("pf.show", program)
        self.assertIn("readback min distance failed", program)

    def test_seed_dynamics_guard_accepts_role_exchange_baseline(self):
        report = evaluate_timeline_dynamics(GPT55_BURST_RECOMPOSE_TIMELINE)
        self.assertEqual(report.layer_count, len(GPT55_BURST_RECOMPOSE_TIMELINE))
        self.assertGreaterEqual(report.changed_rank_layers, 16)
        self.assertGreaterEqual(report.average_rank_change, 9.0)
        self.assertGreaterEqual(report.min_span_x_cm, 320)
        self.assertGreaterEqual(report.min_span_y_cm, 320)
        self.assertEqual(validate_timeline_dynamics(GPT55_BURST_RECOMPOSE_TIMELINE), [])

    def test_dynamics_guard_rejects_fixed_lane_regression(self):
        fixed_lane_timeline = [
            (
                time_sec,
                f"fixed lane {time_sec}",
                [
                    (80, 120 + time_sec * 8, 120),
                    (150, 180 + time_sec * 6, 130),
                    (220, 240 + time_sec * 4, 140),
                    (290, 300 + time_sec * 2, 150),
                    (360, 240 + time_sec * 4, 140),
                    (430, 180 + time_sec * 6, 130),
                    (500, 120 + time_sec * 8, 120),
                ],
                "#ffffff",
            )
            for time_sec in range(1, 6)
        ]
        errors = validate_timeline_dynamics(fixed_lane_timeline)
        self.assertTrue(any("fixed-lane degeneration" in err for err in errors))
        self.assertTrue(any("insufficient x span" in err for err in errors))

    def test_pipeline_direct_seed_selection_uses_gpt55_seed(self):
        if PipelineConfig is None or _choose_direct_seed_program is None:
            self.skipTest("pipeline optional dependencies are not installed")
        with tempfile.TemporaryDirectory() as d:
            cfg = PipelineConfig(
                audio_path="",
                output_dir=d,
                user_intent="seed test",
                use_qwen=False,
                direct_fallback_mode="gpt55_burst_seed",
            )
            fleet = FleetSpec(drone_count=7, fleet_type="F400", drone_class="Drone")
            program = _choose_direct_seed_program(
                config=cfg,
                deterministic_seed_program_text=None,
                fleet=fleet,
            )
        self.assertIsNotNone(program)
        self.assertIn(repr(os.path.join(d, "nl_choreo_output")), program)
        self.assertIn(repr(""), program)
        self.assertIn(repr(GPT55_BURST_RECOMPOSE_TIMELINE), program)


if __name__ == "__main__":
    unittest.main()
