import unittest

import numpy as np

from pyfii.show import drone3d, iiid_rotate


class NumpyCompatibilityTests(unittest.TestCase):
    def test_rotation_matrix_and_3d_drone_render_data(self):
        rotation = iiid_rotate(np.array([0, 0, 0]))

        self.assertEqual(rotation.shape, (3, 3))
        np.testing.assert_allclose(rotation, np.identity(3))

        tilted_rotation = iiid_rotate(np.array([100, -50, 25]))
        self.assertEqual(tilted_rotation.shape, (3, 3))
        self.assertTrue(np.isfinite(tilted_rotation).all())

        for device in ("F400", "F600"):
            objects = []
            drone3d(
                objects,
                0,
                0,
                0,
                (255, 255, 255),
                0,
                acceleration=(100, -50, 25),
                device=device,
            )

            self.assertEqual(len(objects), 7)


if __name__ == "__main__":
    unittest.main()
