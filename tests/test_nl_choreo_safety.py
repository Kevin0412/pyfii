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

    def test_move_requires_velxy_velz(self):
        fleet = FleetSpec(drone_count=7, fleet_type="F400", drone_class="Drone")
        seg = SegmentSpec(
            segment_id="SG01",
            scene_id="SC01",
            start=0.0,
            end=5.0,
            tracks=[
                DroneTrackSpec(
                    drone_id=1,
                    ops=[DroneOp(op="move2", args=[100, 100, 120])],
                )
            ],
        )
        res = validate_segment_specs([seg], fleet)
        self.assertFalse(res.ok)
        self.assertTrue(any("move2 before VelXY/VelZ" in e for e in res.errors))

    def test_min_spacing_violation_fails(self):
        fleet = FleetSpec(drone_count=7, fleet_type="F400", drone_class="Drone")
        seg = SegmentSpec(
            segment_id="SG01",
            scene_id="SC01",
            start=0.0,
            end=5.0,
            tracks=[
                DroneTrackSpec(
                    drone_id=1,
                    ops=[
                        DroneOp(op="VelXY", args=[100, 200]),
                        DroneOp(op="VelZ", args=[100, 200]),
                        DroneOp(op="move2", args=[100, 100, 120]),
                    ],
                ),
                DroneTrackSpec(
                    drone_id=2,
                    ops=[
                        DroneOp(op="VelXY", args=[100, 200]),
                        DroneOp(op="VelZ", args=[100, 200]),
                        DroneOp(op="move2", args=[130, 100, 120]),
                    ],
                ),
            ],
        )
        res = validate_segment_specs([seg], fleet)
        self.assertFalse(res.ok)
        self.assertTrue(any("too close" in e for e in res.errors))

    def test_path_conflict_violation_fails(self):
        fleet = FleetSpec(drone_count=7, fleet_type="F400", drone_class="Drone")
        seg1 = SegmentSpec(
            segment_id="SG01",
            scene_id="SC01",
            start=0.0,
            end=5.0,
            tracks=[
                DroneTrackSpec(
                    drone_id=1,
                    ops=[
                        DroneOp(op="VelXY", args=[100, 200]),
                        DroneOp(op="VelZ", args=[100, 200]),
                        DroneOp(op="move2", args=[100, 100, 120]),
                    ],
                ),
                DroneTrackSpec(
                    drone_id=2,
                    ops=[
                        DroneOp(op="VelXY", args=[100, 200]),
                        DroneOp(op="VelZ", args=[100, 200]),
                        DroneOp(op="move2", args=[200, 100, 120]),
                    ],
                ),
            ],
        )
        seg2 = SegmentSpec(
            segment_id="SG02",
            scene_id="SC02",
            start=5.0,
            end=10.0,
            tracks=[
                DroneTrackSpec(
                    drone_id=1,
                    ops=[
                        DroneOp(op="VelXY", args=[100, 200]),
                        DroneOp(op="VelZ", args=[100, 200]),
                        DroneOp(op="move2", args=[200, 100, 120]),
                    ],
                ),
                DroneTrackSpec(
                    drone_id=2,
                    ops=[
                        DroneOp(op="VelXY", args=[100, 200]),
                        DroneOp(op="VelZ", args=[100, 200]),
                        DroneOp(op="move2", args=[100, 100, 120]),
                    ],
                ),
            ],
        )
        res = validate_segment_specs([seg1, seg2], fleet)
        self.assertFalse(res.ok)
        self.assertTrue(any("path conflict" in e for e in res.errors))


if __name__ == "__main__":
    unittest.main()
