import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from dataclasses import asdict

import numpy as np

path = os.getcwd() + r'/src/pyfii'
sys.path.append(path)

from extensions.nl_choreo.contracts import MusicAnalysis, MusicSection
from extensions.nl_choreo.pipeline import PipelineConfig, run_nl_choreo_pipeline


class TestNlChoreoPipelineSmoke(unittest.TestCase):
    @patch("extensions.nl_choreo.pipeline._ensure_render_project")
    @patch("extensions.nl_choreo.pipeline.render_project_pair")
    @patch("extensions.nl_choreo.pipeline.analyze_music")
    def test_pipeline_generates_files(self, mock_analyze, mock_render_project_pair, mock_ensure):
        mock_analyze.return_value = MusicAnalysis(
            duration=64.0,
            tempo_estimate=128.0,
            beats=[0.5, 1.0, 1.5],
            onsets=[0.45, 0.95],
            sections=[
                MusicSection(section_id="S01", start=0.0, end=20.0, energy="low"),
                MusicSection(section_id="S02", start=20.0, end=40.0, energy="mid"),
                MusicSection(section_id="S03", start=40.0, end=64.0, energy="high"),
            ],
            energy_curve=[0.1, 0.4, 0.9],
            climax_ranges=[(45.0, 58.0)],
        )

        class _R:
            def __init__(self, video):
                self.output_video = video
                self.field = 6
                self.device = "F400"
                self.frame_count_hint = 100
                self.warnings = []

        mock_render_project_pair.side_effect = (
            lambda project_path, save_path_2d, save_path_3d, fps=25: (
                _R(save_path_2d + ".mp4"),
                _R(save_path_3d + ".mp4"),
            )
        )
        mock_ensure.return_value = None

        with tempfile.TemporaryDirectory() as d:
            cfg = PipelineConfig(
                audio_path="cjxq.mp3",
                output_dir=d,
                user_intent="smoke test",
                fleet_type="F400",
                use_qwen=False,
                direct_python_codegen=False,
                render_fps=40,
            )
            result = run_nl_choreo_pipeline(cfg, edit_rounds=["更慢一点"])
            self.assertTrue(os.path.exists(result["analysis_path"]))
            self.assertTrue(os.path.exists(result["scene_plan_path"]))
            self.assertTrue(os.path.exists(result["segment_specs_path"]))
            self.assertTrue(os.path.exists(result["dialogue_history_path"]))
            self.assertTrue(os.path.exists(result["program_path"]))
            self.assertIn("final_full_video_2d", result)
            self.assertIn("final_full_video_3d", result)
            self.assertEqual(result.get("render_fps"), 40)


if __name__ == "__main__":
    unittest.main()
