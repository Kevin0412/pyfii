import os
import sys
import unittest
from unittest.mock import patch

import numpy as np

path = os.getcwd() + r'/src/pyfii'
sys.path.append(path)

from extensions.nl_choreo.audio_analyzer import analyze_music


class _FakeBeat:
    @staticmethod
    def beat_track(y, sr, hop_length):
        return 128.0, np.array([0, 10, 20])


class _FakeOnset:
    @staticmethod
    def onset_detect(y, sr, hop_length, units):
        return np.array([5, 15, 25])


class _FakeFeature:
    @staticmethod
    def rms(y, hop_length):
        return np.array([[0.1, 0.2, 0.6, 0.8, 0.3]])


class _FakeLibrosa:
    beat = _FakeBeat()
    onset = _FakeOnset()
    feature = _FakeFeature()

    @staticmethod
    def load(audio_path, sr):
        return np.array([0.0, 0.1, 0.2]), sr

    @staticmethod
    def get_duration(y, sr):
        return 64.0

    @staticmethod
    def frames_to_time(frames, sr, hop_length):
        return np.array(frames) * 0.1


class TestNlChoreoAudio(unittest.TestCase):
    @patch("extensions.nl_choreo.audio_analyzer._import_librosa", return_value=_FakeLibrosa)
    def test_analyze_music(self, _):
        result = analyze_music("dummy.mp3")
        self.assertAlmostEqual(result.duration, 64.0)
        self.assertTrue(result.beats)
        self.assertTrue(result.onsets)
        self.assertTrue(result.sections)


if __name__ == "__main__":
    unittest.main()
