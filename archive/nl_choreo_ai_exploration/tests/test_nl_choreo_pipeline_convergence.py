import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

path = os.getcwd() + r'/src/pyfii'
sys.path.append(path)

from extensions.nl_choreo.contracts import MusicAnalysis, MusicSection, SegmentIssue
from extensions.nl_choreo.pipeline import PipelineConfig, run_nl_choreo_pipeline


class TestNlChoreoPipelineConvergence(unittest.TestCase):
    @patch("extensions.nl_choreo.pipeline._ensure_render_project")
    @patch("extensions.nl_choreo.pipeline.analyze_music")
    @patch("extensions.nl_choreo.pipeline.render_project_pair")
    @patch("extensions.nl_choreo.pipeline.cut_video_segment")
    @patch("extensions.nl_choreo.pipeline.inspect_with_qwen")
    @patch("extensions.nl_choreo.pipeline.generate_final_design_narration")
    def test_fallback_in_strict_mode_sets_retryable(self, mock_narration, mock_inspect, mock_cut_segment, mock_render_project_pair, mock_analyze, mock_ensure):
        mock_analyze.return_value = MusicAnalysis(
            duration=64.0,
            tempo_estimate=128.0,
            beats=[0.5],
            onsets=[0.4],
            sections=[MusicSection(section_id="S01", start=0.0, end=64.0, energy="mid")],
            energy_curve=[0.5],
            climax_ranges=[(20.0, 40.0)],
        )

        def _render_fail(*args, **kwargs):
            raise RuntimeError("render failed")

        class _I:
            suggest_regenerate = False
            issues = []

        mock_render_project_pair.side_effect = _render_fail
        mock_ensure.return_value = None
        mock_narration.return_value = "final narration"
        mock_cut_segment.side_effect = lambda source_video, output_video, start_sec, end_sec: output_video
        mock_inspect.return_value = _I()

        with tempfile.TemporaryDirectory() as d:
            fallback_path = os.path.join(d, "fb.mp4")
            with open(fallback_path, "wb") as f:
                f.write(b"0")
            out_video = os.path.join(d, "nl_choreo_output.mp4")
            if os.path.exists(out_video):
                os.remove(out_video)
            cfg = PipelineConfig(
                audio_path="cjxq.mp3",
                output_dir=d,
                user_intent="strict fallback test",
                use_qwen=True,
                direct_python_codegen=False,
                max_rounds=1,
                fallback_video_path=fallback_path,
                strict_render_source=True,
            )
            result = run_nl_choreo_pipeline(cfg, edit_rounds=[])
            with open(result["workflow_state_path"], "r", encoding="utf-8") as f:
                state = json.loads(f.read())
            self.assertEqual(state["status"], "failed_retryable")

    @patch("extensions.nl_choreo.pipeline.analyze_music")
    @patch("extensions.nl_choreo.pipeline.render_project_pair")
    @patch("extensions.nl_choreo.pipeline.cut_video_segment")
    @patch("extensions.nl_choreo.pipeline.inspect_with_qwen")
    @patch("extensions.nl_choreo.pipeline.generate_final_design_narration")
    def test_non_actionable_issues_complete(self, mock_narration, mock_inspect, mock_cut_segment, mock_render_project_pair, mock_analyze):
        class _R:
            def __init__(self, video):
                self.output_video = video
                self.field = 6
                self.device = "F400"
                self.frame_count_hint = 100
                self.warnings = []

        class _I:
            def __init__(self, issues):
                self.suggest_regenerate = True
                self.issues = issues

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
        mock_render_project_pair.side_effect = (
            lambda project_path, save_path_2d, save_path_3d, fps=25: (
                _R(save_path_2d + ".mp4"),
                _R(save_path_3d + ".mp4"),
            )
        )
        mock_narration.return_value = "final narration"
        mock_cut_segment.side_effect = lambda source_video, output_video, start_sec, end_sec: output_video

        # 全部问题都指向未知段，不可行动；应在第一轮视为 completed
        unknown_issue = SegmentIssue(segment_id="XX01", severity="low", detail="note", recommendation_zh="none")
        mock_inspect.side_effect = [_I([unknown_issue]) for _ in range(6)]

        with tempfile.TemporaryDirectory() as d:
            cfg = PipelineConfig(
                audio_path="cjxq.mp3",
                output_dir=d,
                user_intent="non actionable",
                use_qwen=True,
                direct_python_codegen=False,
                max_rounds=2,
            )
            result = run_nl_choreo_pipeline(cfg, edit_rounds=[])
            with open(result["workflow_state_path"], "r", encoding="utf-8") as f:
                state = json.loads(f.read())
            self.assertEqual(state["status"], "completed")


if __name__ == "__main__":
    unittest.main()
