import unittest
from unittest.mock import patch

from pyfii.fiiRead import DroneTrack, FiiRender, from_fii
from pyfii.show import show


class ShowTrackTests(unittest.TestCase):
    def test_empty_music_from_old_scripts_is_normalized(self):
        self.assertEqual(DroneTrack(music=[""]).music, [])
        self.assertEqual(DroneTrack(music=["动作组/"]).music, [])

    def test_new_show_path_accepts_track(self):
        track = DroneTrack([], 0, [], 4, "F600")

        with patch("pyfii.fiiRead.FiiRender2D") as renderer_class:
            show(track, show=False)

        self.assertIs(renderer_class.call_args.args[0], track)
        renderer_class.return_value.show.assert_called_once_with(display=False)

    def test_from_fii_returns_track(self):
        result = (["dots"], 1000, [], 4, "F600")

        with patch("pyfii.read.read_fii", return_value=result):
            track = from_fii("project", fps=60)

        self.assertEqual(track.dots, ["dots"])
        self.assertEqual(track.t0, 1000)
        self.assertEqual(track.field, 4)
        self.assertEqual(track.device, "F600")

    def test_old_show_path_is_kept(self):
        with patch("pyfii.fiiRead.FiiRender2D") as renderer_class:
            show([], 0, [""], field=4, device="F600", show=False)

        track = renderer_class.call_args.args[0]
        self.assertEqual(track.music, [])
        self.assertEqual(track.field, 4)
        self.assertEqual(track.device, "F600")

    def test_empty_music_does_not_start_pygame(self):
        renderer = FiiRender(DroneTrack(music=[""]))

        with patch("pyfii.fiiRead.pygame.mixer.init") as mixer_init:
            renderer._start_music(0)

        mixer_init.assert_not_called()


if __name__ == "__main__":
    unittest.main()
