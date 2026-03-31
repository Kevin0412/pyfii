import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

path = os.getcwd() + r'/src/pyfii'
sys.path.append(path)

from extensions.nl_choreo.contracts import MusicAnalysis, MusicSection
from extensions.nl_choreo.pipeline import PipelineConfig, run_nl_choreo_pipeline


class TestNlChoreoPipelineDirectMode(unittest.TestCase):
    @patch("extensions.nl_choreo.pipeline.emit_pyfii_program")
    @patch("extensions.nl_choreo.pipeline.inspect_with_qwen")
    @patch("extensions.nl_choreo.pipeline.cut_video_segment")
    @patch("extensions.nl_choreo.pipeline.render_project_pair")
    @patch("extensions.nl_choreo.pipeline._ensure_render_project")
    @patch("extensions.nl_choreo.pipeline.analyze_music")
    @patch("extensions.nl_choreo.pipeline.generate_final_design_narration")
    def test_direct_default_has_no_pattern_seed_dependency(
        self,
        mock_narration,
        mock_analyze,
        mock_ensure,
        mock_render_project_pair,
        mock_cut_segment,
        mock_inspect,
        mock_emit,
    ):
        class _R:
            def __init__(self, video):
                self.output_video = video
                self.field = 6
                self.device = "F400"
                self.frame_count_hint = 100
                self.warnings = []

        class _I:
            suggest_regenerate = False
            issues = []

        mock_analyze.return_value = MusicAnalysis(
            duration=64.0,
            tempo_estimate=128.0,
            beats=[0.5],
            onsets=[0.4],
            sections=[MusicSection(section_id="S01", start=0.0, end=64.0, energy="mid")],
            energy_curve=[0.5],
            climax_ranges=[(20.0, 40.0)],
        )
        mock_render_project_pair.side_effect = (
            lambda project_path, save_path_2d, save_path_3d, fps=25: (
                _R(save_path_2d + ".mp4"),
                _R(save_path_3d + ".mp4"),
            )
        )
        mock_cut_segment.side_effect = lambda source_video, output_video, start_sec, end_sec: output_video
        mock_inspect.return_value = _I()
        mock_ensure.return_value = None
        mock_narration.return_value = "final narration"
        mock_emit.side_effect = AssertionError("emit_pyfii_program should not be called in direct default mode")

        with tempfile.TemporaryDirectory() as d:
            cfg = PipelineConfig(
                audio_path="cjxq.mp3",
                output_dir=d,
                user_intent="direct no pattern",
                use_qwen=True,
                direct_python_codegen=True,
                max_rounds=1,
                direct_fallback_mode="none",
            )
            result = run_nl_choreo_pipeline(cfg, edit_rounds=[])
            self.assertIn(result["status"], {"completed", "failed_retryable", "stopped_max_rounds", "stopped_limits"})
            self.assertTrue(os.path.exists(result["workflow_state_path"]))
            self.assertTrue(os.path.exists(result["segment_specs_path"]))
            self.assertTrue(os.path.exists(result["program_path"]))
            self.assertEqual(mock_emit.call_count, 0)

    @patch("extensions.nl_choreo.pipeline.emit_pyfii_program")
    @patch("extensions.nl_choreo.pipeline.inspect_with_qwen")
    @patch("extensions.nl_choreo.pipeline.cut_video_segment")
    @patch("extensions.nl_choreo.pipeline.render_project_pair")
    @patch("extensions.nl_choreo.pipeline._ensure_render_project")
    @patch("extensions.nl_choreo.pipeline.analyze_music")
    @patch("extensions.nl_choreo.pipeline.generate_final_design_narration")
    @patch("extensions.nl_choreo.pipeline._generate_safe_program_with_qwen")
    @patch("extensions.nl_choreo.pipeline._generate_program_stepwise_with_qwen")
    def test_direct_pattern_seed_mode_uses_emit_only_for_fallback(
        self,
        mock_stepwise,
        mock_generate_safe,
        mock_narration,
        mock_analyze,
        mock_ensure,
        mock_render_project_pair,
        mock_cut_segment,
        mock_inspect,
        mock_emit,
    ):
        class _R:
            def __init__(self, video):
                self.output_video = video
                self.field = 6
                self.device = "F400"
                self.frame_count_hint = 100
                self.warnings = []

        class _I:
            suggest_regenerate = False
            issues = []

        mock_analyze.return_value = MusicAnalysis(
            duration=64.0,
            tempo_estimate=128.0,
            beats=[0.5],
            onsets=[0.4],
            sections=[MusicSection(section_id="S01", start=0.0, end=64.0, energy="mid")],
            energy_curve=[0.5],
            climax_ranges=[(20.0, 40.0)],
        )
        mock_render_project_pair.side_effect = (
            lambda project_path, save_path_2d, save_path_3d, fps=25: (
                _R(save_path_2d + ".mp4"),
                _R(save_path_3d + ".mp4"),
            )
        )
        mock_cut_segment.side_effect = lambda source_video, output_video, start_sec, end_sec: output_video
        mock_inspect.return_value = _I()
        mock_ensure.return_value = None
        mock_narration.return_value = "final narration"
        mock_emit.return_value = "# pattern seed\n"

        # force stepwise + oneshot to fail so fallback branch is exercised
        mock_stepwise.side_effect = RuntimeError("stepwise fail")
        mock_generate_safe.side_effect = RuntimeError("oneshot fail")

        with tempfile.TemporaryDirectory() as d:
            cfg = PipelineConfig(
                audio_path="cjxq.mp3",
                output_dir=d,
                user_intent="direct with pattern fallback",
                use_qwen=True,
                direct_python_codegen=True,
                max_rounds=1,
                direct_fallback_mode="pattern_seed",
            )
            result = run_nl_choreo_pipeline(cfg, edit_rounds=[])
            self.assertTrue(os.path.exists(result["workflow_state_path"]))
            self.assertGreaterEqual(mock_emit.call_count, 1)

            with open(result["workflow_state_path"], "r", encoding="utf-8") as f:
                state = json.loads(f.read())
            self.assertIn(state["status"], {"completed", "failed_retryable", "stopped_max_rounds", "stopped_limits"})


if __name__ == "__main__":
    unittest.main()
