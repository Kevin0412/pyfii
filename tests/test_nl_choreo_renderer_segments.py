import os
import sys
import tempfile
import unittest

import cv2
import numpy as np

path = os.getcwd() + r'/src/pyfii'
sys.path.append(path)

from extensions.nl_choreo.renderer import cut_video_segment


class TestNlChoreoRendererSegments(unittest.TestCase):
    def test_cut_video_segment(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "src.mp4")
            dst = os.path.join(d, "dst.mp4")

            w, h, fps = 320, 240, 10
            writer = cv2.VideoWriter(src, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
            for _ in range(50):
                frame = np.zeros((h, w, 3), dtype=np.uint8)
                writer.write(frame)
            writer.release()

            out = cut_video_segment(src, dst, start_sec=1.0, end_sec=2.0)
            self.assertTrue(os.path.exists(out))

            cap = cv2.VideoCapture(out)
            count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            self.assertGreaterEqual(count, 8)


if __name__ == "__main__":
    unittest.main()
