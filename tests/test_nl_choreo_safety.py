import os
import sys
import unittest

path = os.getcwd() + r'/src/pyfii'
sys.path.append(path)

from extensions.nl_choreo.contracts import DroneOp, DroneTrackSpec, FleetSpec, SegmentSpec
from extensions.nl_choreo.safety import validate_segment_specs


class TestNlChoreoSafety(unittest.TestCase):
    def test_segment_coordinate_out_of_range(self):
        fleet = FleetSpec(drone_count=7, fleet_type="F400", drone_class="Drone")
        seg = SegmentSpec(
            segment_id="SG01",
            scene_id="SC01",
            start=0.0,
            end=5.0,
            tracks=[
                DroneTrackSpec(
                    drone_id=1,
                    ops=[DroneOp(op="move2", args=[9999, 100, 120])],
                )
            ],
        )
        res = validate_segment_specs([seg], fleet)
        self.assertFalse(res.ok)
        self.assertTrue(res.errors)


if __name__ == "__main__":
    unittest.main()
