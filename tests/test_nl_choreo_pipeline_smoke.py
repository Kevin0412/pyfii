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
    @patch("extensions.nl_choreo.pipeline.analyze_music")
    def test_pipeline_generates_files(self, mock_analyze):
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

        with tempfile.TemporaryDirectory() as d:
            cfg = PipelineConfig(
                audio_path="cjxq.mp3",
                output_dir=d,
                user_intent="smoke test",
                fleet_type="F400",
                use_qwen=False,
            )
            result = run_nl_choreo_pipeline(cfg, edit_rounds=["更慢一点"])
            self.assertTrue(os.path.exists(result["analysis_path"]))
            self.assertTrue(os.path.exists(result["scene_plan_path"]))
            self.assertTrue(os.path.exists(result["segment_specs_path"]))
            self.assertTrue(os.path.exists(result["dialogue_history_path"]))
            self.assertTrue(os.path.exists(result["program_path"]))


if __name__ == "__main__":
    unittest.main()
