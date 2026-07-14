import os
import time
import unittest
import warnings
from unittest.mock import patch

import numpy as np

from pyfii.fiiRead import (
    DroneTrack,
    FiiRender,
    ProcessPoolExecutor,
    _render_worker_count,
)
from pyfii.read import _trajectory_worker_count


class _VideoWriter:
    def __init__(self):
        self.frames = []

    def write(self, image):
        self.frames.append((int(image[0, 0, 0]), int(image[0, 0, 1])))

    def release(self):
        pass


class _ConcurrentRenderer(FiiRender):
    @property
    def frame_size(self):
        return (8, 8)

    def getOne(self, k, draw=True):
        time.sleep(0.01)
        warnings.warn(f"frame {k}", Warning)
        image = np.full((8, 8, 3), k, np.uint8)
        image[:, :, 1] = os.getpid() % 256
        return image


class ParallelExecutionTests(unittest.TestCase):
    def test_video_pool_uses_thread_safe_loky_backend(self):
        self.assertTrue(ProcessPoolExecutor.__module__.startswith("joblib.externals.loky"))

    def test_auto_worker_counts_use_all_available_cores(self):
        with patch("pyfii.fiiRead.os.cpu_count", return_value=8):
            self.assertEqual(_render_worker_count(None, 20), 8)
        with patch("pyfii.read.os.cpu_count", return_value=8):
            self.assertEqual(_trajectory_worker_count(None, 20), 8)
            self.assertEqual(_trajectory_worker_count(None, 3), 3)

    def test_video_frames_render_concurrently_but_write_in_order(self):
        track = DroneTrack()
        track.t0 = 3
        writer = _VideoWriter()
        renderer = _ConcurrentRenderer(
            track,
            {
                "FPS": 1,
                "max_fps": 1,
                "workers": None,
                "progress": False,
            },
        )
        renderer._mux_audio = lambda path: None

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            with (
                patch("pyfii.fiiRead.os.cpu_count", return_value=4),
                patch("pyfii.fiiRead.cv2.VideoWriter", return_value=writer),
            ):
                renderer.save("unused")

        self.assertGreater(len({pid for _, pid in writer.frames}), 1)
        self.assertEqual([index for index, _ in writer.frames], [0, 1, 2, 3, 4, 5])
        self.assertEqual([str(item.message) for item in captured], [f"frame {k}" for k in range(6)])

    def test_video_falls_back_to_serial_under_debugger(self):
        track = DroneTrack()
        track.t0 = 1
        writer = _VideoWriter()
        renderer = _ConcurrentRenderer(
            track,
            {"FPS": 1, "max_fps": 1, "workers": None, "progress": False},
        )
        renderer._mux_audio = lambda path: None

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            with (
                patch("pyfii.fiiRead.os.cpu_count", return_value=4),
                patch("pyfii.fiiRead._debugger_active", return_value=True),
                patch("pyfii.fiiRead.cv2.VideoWriter", return_value=writer),
            ):
                renderer.save("unused")

        self.assertEqual({pid for _, pid in writer.frames}, {os.getpid() % 256})
        self.assertTrue(
            any("disabled while a debugger is attached" in str(item.message) for item in captured)
        )

    def test_video_reports_written_frame_progress(self):
        track = DroneTrack()
        track.t0 = 1
        writer = _VideoWriter()
        progress = []
        renderer = _ConcurrentRenderer(
            track,
            {"FPS": 1, "max_fps": 1, "workers": 1, "progress": False},
            progress_callback=lambda completed, total: progress.append((completed, total)),
        )
        renderer._mux_audio = lambda path: None

        with (
            warnings.catch_warnings(),
            patch("pyfii.fiiRead.cv2.VideoWriter", return_value=writer),
        ):
            warnings.simplefilter("ignore")
            renderer.save("unused")

        self.assertEqual(progress, [(0, 4), (1, 4), (2, 4), (3, 4), (4, 4)])


if __name__ == "__main__":
    unittest.main()
