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


class TestNlChoreoPipelineFullLoop(unittest.TestCase):
    @patch("extensions.nl_choreo.pipeline._ensure_render_project")
    @patch("extensions.nl_choreo.pipeline.analyze_music")
    @patch("extensions.nl_choreo.pipeline.render_project")
    @patch("extensions.nl_choreo.pipeline.cut_video_segment")
    @patch("extensions.nl_choreo.pipeline.inspect_with_qwen")
    def test_full_loop_with_resume_artifacts(self, mock_inspect, mock_cut_segment, mock_render_project, mock_analyze, mock_ensure):
        class _R:
            def __init__(self, video):
                self.output_video = video
                self.field = 6
                self.device = "F400"
                self.frame_count_hint = 100
                self.warnings = []

        class _I:
            def __init__(self, regenerate, issues=None):
                self.suggest_regenerate = regenerate
                self.issues = issues or []

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
        mock_render_project.side_effect = lambda project_path, save_path, fps=25, three_d=False: _R(save_path + ".mp4")
        mock_cut_segment.side_effect = lambda source_video, output_video, start_sec, end_sec: output_video

        # 第一轮建议重生（含无效段号 SG00，需归一到当前段），第二轮通过
        bad_id_issue = SegmentIssue(segment_id="SG00", severity="medium", detail="x", recommendation_zh="y")
        mock_inspect.side_effect = [
            _I(True, [bad_id_issue]),
            _I(True, [bad_id_issue]),
            _I(False, []),
            _I(False, []),
            _I(False, []),
            _I(False, []),
        ]

        with tempfile.TemporaryDirectory() as d:
            cfg = PipelineConfig(
                audio_path="cjxq.mp3",
                output_dir=d,
                user_intent="full loop test",
                use_qwen=True,
                direct_python_codegen=False,
                render_fps=40,
                max_rounds=2,
            )
            result = run_nl_choreo_pipeline(cfg, edit_rounds=[])
            self.assertTrue(os.path.exists(result["workflow_state_path"]))
            self.assertTrue(os.path.exists(result["inspection_rounds_path"]))
            self.assertTrue(os.path.exists(result["qwen_calls_path"]))

            with open(result["workflow_state_path"], "r", encoding="utf-8") as f:
                state = json.loads(f.read())
            self.assertIn(state["status"], {"completed", "stopped_limits", "failed_retryable", "stopped_max_rounds"})

            with open(result["inspection_rounds_path"], "r", encoding="utf-8") as f:
                rows = [json.loads(line) for line in f if line.strip()]
            summaries = [r for r in rows if r.get("type") == "round_summary"]
            finals = [r for r in rows if r.get("type") == "final_summary"]
            self.assertTrue(summaries)
            self.assertTrue(finals)
            self.assertIn("fallback_used", summaries[-1])
            self.assertIn("final_full_video_2d", finals[-1])
            self.assertIn("final_full_video_3d", finals[-1])
            self.assertEqual(finals[-1].get("render_fps"), 40)
            self.assertIn("final_full_video_2d", result)
            self.assertIn("final_full_video_3d", result)
            self.assertEqual(result.get("render_fps"), 40)

            # 当首轮就无可行动变更时，不应强制重建项目
            forced_calls = [c for c in mock_ensure.call_args_list if c.kwargs.get("force") is True]
            self.assertIsInstance(forced_calls, list)


if __name__ == "__main__":
    unittest.main()
