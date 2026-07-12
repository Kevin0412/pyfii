import unittest

import numpy as np

from pyfii.cv3d import IIID, IIID2
from pyfii.show import drone3d


class Cv3dRingProjectionTests(unittest.TestCase):
    @staticmethod
    def _bounds(image):
        ys, xs = np.where(np.any(image, axis=2))
        return np.ptp(xs), np.ptp(ys)

    def test_ring_normal_controls_orthographic_orientation(self):
        face_on = np.zeros((201, 201, 3), np.uint8)
        edge_on = np.zeros_like(face_on)

        IIID.ring(
            face_on, (0, 0, 0), 100, 100, 0, 0,
            (255, 255, 255), 40, d=(1, 0), normal_vector=(1, 0, 0),
        )
        IIID.ring(
            edge_on, (0, 0, 0), 100, 100, 0, 0,
            (255, 255, 255), 40, d=(1, 0), normal_vector=(0, 0, 1),
        )

        face_width, face_height = self._bounds(face_on)
        edge_width, edge_height = self._bounds(edge_on)
        self.assertGreater(face_width, 75)
        self.assertGreater(face_height, 75)
        self.assertGreater(edge_width, 75)
        self.assertLessEqual(edge_height, 3)

    def test_tilted_ring_renders_in_perspective_and_panorama(self):
        perspective = np.zeros((300, 400, 3), np.uint8)
        panorama = np.zeros((180, 360, 3), np.uint8)

        IIID.ring(
            perspective, (100, 0, 0), 200, 150, 0, 0,
            (255, 255, 255), 40, d=(100, 100), normal_vector=(1, 1, 1),
        )
        IIID2.ring(
            panorama, (100, 0, 0), (255, 255, 255), 30,
            center=(0, 0, 0), normal_vector=(1, 1, 1),
        )

        self.assertGreater(np.count_nonzero(perspective), 0)
        self.assertGreater(np.count_nonzero(panorama), 0)

    def test_drone_rotor_normal_follows_acceleration(self):
        acceleration = np.array((100, -50, 25), dtype=float)
        objects = []
        drone3d(
            objects, 0, 0, 0, (255, 255, 255), 0,
            acceleration=acceleration,
        )

        expected = acceleration - np.array((0, 0, -980), dtype=float)
        expected /= np.linalg.norm(expected)
        for rotor in objects[:4]:
            np.testing.assert_allclose(rotor[4], expected)

    def test_zero_normal_is_rejected(self):
        image = np.zeros((20, 20, 3), np.uint8)
        with self.assertRaises(ValueError):
            IIID.ring(
                image, (0, 0, 0), 10, 10, 0, 0,
                (255, 255, 255), 5, normal_vector=(0, 0, 0),
            )


if __name__ == "__main__":
    unittest.main()
