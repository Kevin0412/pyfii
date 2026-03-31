import os
import sys
import unittest
from unittest.mock import patch

path = os.getcwd() + r'/src/pyfii'
sys.path.append(path)

from extensions.nl_choreo.renderer import render_project_pair


class TestNlChoreoRendererTiming(unittest.TestCase):
    @patch("extensions.nl_choreo.renderer._render_with_shared_track")
    def test_render_project_pair_uses_one_shared_track(self, mock_shared):
        class _R:
            def __init__(self, video):
                self.output_video = video
                self.field = 6
                self.device = "F400"
                self.frame_count_hint = 100
                self.warnings = []

        mock_shared.return_value = (_R("/tmp/o2d.mp4"), {
            "/tmp/o2d": _R("/tmp/o2d.mp4"),
            "/tmp/o3d": _R("/tmp/o3d.mp4"),
        })

        r2d, r3d = render_project_pair(
            project_path="/tmp/demo",
            save_path_2d="/tmp/o2d",
            save_path_3d="/tmp/o3d",
            fps=30,
        )

        self.assertEqual(mock_shared.call_count, 1)
        kwargs = mock_shared.call_args.kwargs
        self.assertEqual(kwargs["project_path"], "/tmp/demo")
        self.assertEqual(kwargs["variants"], [("/tmp/o2d", False, 30), ("/tmp/o3d", True, 30)])
        self.assertEqual(r2d.output_video, "/tmp/o2d.mp4")
        self.assertEqual(r3d.output_video, "/tmp/o3d.mp4")


if __name__ == "__main__":
    unittest.main()
