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


class TestNlChoreoPipelineFullLoop(unittest.TestCase):
    @patch("extensions.nl_choreo.pipeline.analyze_music")
    @patch("extensions.nl_choreo.pipeline.render_project")
    @patch("extensions.nl_choreo.pipeline.cut_video_segment")
    @patch("extensions.nl_choreo.pipeline.inspect_with_qwen")
    def test_full_loop_with_resume_artifacts(self, mock_inspect, mock_cut_segment, mock_render_project, mock_analyze):
        class _R:
            def __init__(self, video):
                self.output_video = video
                self.field = 6
                self.device = "F400"
                self.frame_count_hint = 100

        class _I:
            def __init__(self, regenerate):
                self.suggest_regenerate = regenerate
                self.issues = []

        mock_analyze.return_value = MusicAnalysis(
            duration=64.0,
            tempo_estimate=128.0,
            beats=[0.5, 1.0],
            onsets=[0.4],
            sections=[
                MusicSection(section_id="S01", start=0.0, end=20.0, energy="low"),
                MusicSection(section_id="S02", start=20.0, end=40.0, energy="mid"),
                MusicSection(section_id="S03", start=40.0, end=64.0, energy="high"),
            ],
            energy_curve=[0.1, 0.2, 0.8],
            climax_ranges=[(44.0, 58.0)],
        )
        mock_render_project.side_effect = lambda project_path, save_path, fps=25: _R(save_path + ".mp4")
        mock_cut_segment.side_effect = lambda source_video, output_video, start_sec, end_sec: output_video

        # 第一轮建议重生，第二轮通过
        mock_inspect.side_effect = [_I(True), _I(True), _I(False), _I(False), _I(False), _I(False)]

        with tempfile.TemporaryDirectory() as d:
            cfg = PipelineConfig(
                audio_path="cjxq.mp3",
                output_dir=d,
                user_intent="full loop test",
                use_qwen=True,
                max_rounds=2,
            )
            result = run_nl_choreo_pipeline(cfg, edit_rounds=[])
            self.assertTrue(os.path.exists(result["workflow_state_path"]))
            self.assertTrue(os.path.exists(result["inspection_rounds_path"]))
            self.assertTrue(os.path.exists(result["qwen_calls_path"]))

            with open(result["workflow_state_path"], "r", encoding="utf-8") as f:
                state = json.loads(f.read())
            self.assertIn(state["status"], {"completed", "stopped_limits", "failed_retryable"})


if __name__ == "__main__":
    unittest.main()
