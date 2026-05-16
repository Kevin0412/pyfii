import os
import sys
import unittest

path = os.getcwd() + r'/src/pyfii'
sys.path.append(path)

from extensions.nl_choreo.pipeline import (
    _validate_generated_program_text,
    _validate_stepwise_candidate_text,
)


def _program_text() -> str:
    return """
import pyfii as pf

d1=pf.Drone(0,0,pf.drone_config_6m,"192.168.51.51")
d2=pf.Drone(0,0,pf.drone_config_6m,"192.168.51.52")
d3=pf.Drone(0,0,pf.drone_config_6m,"192.168.51.53")
d4=pf.Drone(0,0,pf.drone_config_6m,"192.168.51.54")
d5=pf.Drone(0,0,pf.drone_config_6m,"192.168.51.55")
d6=pf.Drone(0,0,pf.drone_config_6m,"192.168.51.56")
d7=pf.Drone(0,0,pf.drone_config_6m,"192.168.51.57")

ds=[d1,d2,d3,d4,d5,d6,d7]
group_a=ds[:4]
group_b=ds[4:]
for d in ds:
    d.X=d.x=280
    d.Y=d.y=280
    d.takeoff(1,100)

for d in group_a:
    d.inittime(4)
    d.VelXY(150,260)
    d.VelZ(120,220)
    d.move2(40,100,120)
for d in group_b:
    d.inittime(4)
    d.VelXY(150,260)
    d.VelZ(120,220)
    d.move2(520,460,140)

for d in group_a:
    d.inittime(8)
    d.VelXY(150,260)
    d.VelZ(120,220)
    d.move2(60,460,122)
for d in group_b:
    d.inittime(8)
    d.VelXY(150,260)
    d.VelZ(120,220)
    d.move2(500,120,138)

for d in group_a:
    d.inittime(12)
    d.VelXY(150,260)
    d.VelZ(120,220)
    d.move2(90,140,124)
for d in group_b:
    d.inittime(12)
    d.VelXY(150,260)
    d.VelZ(120,220)
    d.move2(470,430,136)

for d in group_a:
    d.inittime(16)
    d.VelXY(150,260)
    d.VelZ(120,220)
    d.move2(120,420,126)
for d in group_b:
    d.inittime(16)
    d.VelXY(150,260)
    d.VelZ(120,220)
    d.move2(440,160,134)

for d in group_a:
    d.inittime(20)
    d.VelXY(150,260)
    d.VelZ(120,220)
    d.move2(150,180,128)
for d in group_b:
    d.inittime(20)
    d.VelXY(150,260)
    d.VelZ(120,220)
    d.move2(410,400,132)

for d in group_a:
    d.inittime(24)
    d.VelXY(150,260)
    d.VelZ(120,220)
    d.move2(180,380,130)
for d in group_b:
    d.inittime(24)
    d.VelXY(150,260)
    d.VelZ(120,220)
    d.move2(380,200,130)

for d in group_a:
    d.inittime(28)
    d.VelXY(150,260)
    d.VelZ(120,220)
    d.move2(220,130,128)
for d in group_b:
    d.inittime(28)
    d.VelXY(150,260)
    d.VelZ(120,220)
    d.move2(340,430,132)

for d in ds:
    d.land()
    d.end()
"""


class TestNlChoreoQualityValidator(unittest.TestCase):
    def test_accepts_compliant_program(self):
        errs = _validate_generated_program_text(
            _program_text(),
            expected_fps=40,
            target_script_duration_sec=30.0,
        )
        self.assertEqual(errs, [])

    def test_rejects_sparse_timeline_gap(self):
        txt = _program_text().replace("d.inittime(24)", "d.inittime(30)")
        errs = _validate_generated_program_text(txt, expected_fps=40)
        self.assertTrue(any("movement too sparse" in e for e in errs))

    def test_rejects_low_move2_count_in_step(self):
        txt = """
import pyfii as pf
for d in []:
    pass

d1=pf.Drone(0,0,pf.drone_config_6m,"192.168.51.51")
d1.takeoff(1,100)
d1.inittime(4)
d1.VelXY(150,260)
d1.VelZ(120,220)
d1.move2(100,100,120)
d1.inittime(8)
d1.VelXY(150,260)
d1.VelZ(120,220)
d1.move2(200,200,120)
d1.land()
d1.end()
"""
        errs = _validate_stepwise_candidate_text(txt, expected_fps=40, step_idx=1, total_steps=3)
        self.assertTrue(any("insufficient choreography complexity" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
