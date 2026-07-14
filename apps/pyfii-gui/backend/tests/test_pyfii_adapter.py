from pathlib import Path
from unittest.mock import patch
import unittest
import warnings

from pyfii.fiiRead import DroneTrack
from pyfii_gui_api.services.pyfii_adapter import parse_fii_project


class PyfiiAdapterTests(unittest.TestCase):
    def test_validation_uses_track_and_keeps_warnings(self):
        def read_fii(*_args, **_kwargs):
            warnings.warn("read warning", Warning)
            return [], 0, [""], 4, "F600"

        def validate_show(track, **_kwargs):
            self.assertIsInstance(track, DroneTrack)
            self.assertEqual(track.music, [])
            warnings.warn("show warning", Warning)

        with (
            patch("pyfii.read.read_fii", side_effect=read_fii),
            patch("pyfii.show.show", side_effect=validate_show),
        ):
            project = parse_fii_project(Path("project"), fps=60, ignore_acc=False)

        self.assertEqual(project.warnings, ["read warning", "show warning"])
        self.assertEqual(project.music, [""])


if __name__ == "__main__":
    unittest.main()
