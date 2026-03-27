import os
import sys
import unittest

path = os.getcwd() + r'/src/pyfii'
sys.path.append(path)

from extensions.nl_choreo.codegen import emit_pyfii_program
from extensions.nl_choreo.contracts import DroneOp, DroneTrackSpec, FleetSpec, SegmentSpec


class TestNlChoreoCodegenStyle(unittest.TestCase):
    def test_emit_uses_inittime_groups_and_relationship_lists(self):
        fleet = FleetSpec(drone_count=3, fleet_type="F400", drone_class="Drone")

        seg1 = SegmentSpec(
            segment_id="SG01",
            scene_id="SC01",
            start=5.0,
            end=10.0,
            tracks=[
                DroneTrackSpec(
                    drone_id=1,
                    ops=[
                        DroneOp(op="inittime", args=[5]),
                        DroneOp(op="VelXY", args=[160, 320]),
                        DroneOp(op="VelZ", args=[160, 320]),
                        DroneOp(op="move2", args=[80, 40, 120]),
                        DroneOp(op="TurnOnAll", args=["#ff5555"]),
                        DroneOp(op="delay", args=[3000]),
                    ],
                ),
                DroneTrackSpec(
                    drone_id=2,
                    ops=[
                        DroneOp(op="inittime", args=[5]),
                        DroneOp(op="VelXY", args=[160, 320]),
                        DroneOp(op="VelZ", args=[160, 320]),
                        DroneOp(op="move2", args=[150, 120, 120]),
                        DroneOp(op="TurnOnAll", args=["#ff5555"]),
                        DroneOp(op="delay", args=[3000]),
                    ],
                ),
                DroneTrackSpec(
                    drone_id=3,
                    ops=[
                        DroneOp(op="inittime", args=[5]),
                        DroneOp(op="VelXY", args=[160, 320]),
                        DroneOp(op="VelZ", args=[160, 320]),
                        DroneOp(op="move2", args=[220, 200, 120]),
                        DroneOp(op="TurnOnAll", args=["#ff5555"]),
                        DroneOp(op="delay", args=[3000]),
                    ],
                ),
            ],
        )

        seg2 = SegmentSpec(
            segment_id="SG02",
            scene_id="SC02",
            start=10.0,
            end=15.0,
            tracks=[
                DroneTrackSpec(
                    drone_id=1,
                    ops=[
                        DroneOp(op="inittime", args=[10]),
                        DroneOp(op="VelXY", args=[128, 256]),
                        DroneOp(op="VelZ", args=[128, 256]),
                        DroneOp(op="move2", args=[120, 40, 170]),
                        DroneOp(op="TurnOnAll", args=["#ffaa00"]),
                        DroneOp(op="delay", args=[2500]),
                    ],
                ),
                DroneTrackSpec(
                    drone_id=2,
                    ops=[
                        DroneOp(op="inittime", args=[10]),
                        DroneOp(op="VelXY", args=[128, 256]),
                        DroneOp(op="VelZ", args=[128, 256]),
                        DroneOp(op="move2", args=[175, 120, 150]),
                        DroneOp(op="TurnOnAll", args=["#ffaa00"]),
                        DroneOp(op="delay", args=[2500]),
                    ],
                ),
                DroneTrackSpec(
                    drone_id=3,
                    ops=[
                        DroneOp(op="inittime", args=[10]),
                        DroneOp(op="VelXY", args=[128, 256]),
                        DroneOp(op="VelZ", args=[128, 256]),
                        DroneOp(op="move2", args=[230, 200, 130]),
                        DroneOp(op="TurnOnAll", args=["#ffaa00"]),
                        DroneOp(op="delay", args=[2500]),
                    ],
                ),
            ],
        )

        script = emit_pyfii_program(
            output_path="output/nl_choreo_demo",
            fleet=fleet,
            segments=[seg1, seg2],
            program_name="nl_choreo_demo",
            music_path="cjxq.mp3",
        )

        self.assertIn("# startTime = 5s", script)
        self.assertIn("# endTime = 10s", script)
        self.assertIn("# startTime = 10s", script)
        self.assertIn("for d in ds:\n    d.inittime(5)", script)
        self.assertIn("for d in ds:\n    d.inittime(10)", script)
        self.assertIn("for i,d in enumerate(ds):", script)
        self.assertIn("xs=[80+70*i for i in range(3)]", script)

        self.assertLess(script.index("d.takeoff(1,80)"), script.index("d.move2("))
        self.assertLess(script.index("d.VelXY("), script.index("d.move2("))
        self.assertLess(script.index("d.VelZ("), script.index("d.move2("))

        self.assertIn("for d in ds:\n    d.land()\n    d.end()", script)


if __name__ == "__main__":
    unittest.main()
