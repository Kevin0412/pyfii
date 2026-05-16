import os
import sys
import unittest

path = os.getcwd() + r'/src/pyfii'
sys.path.append(path)

from extensions.nl_choreo.contracts import FleetSpec, Scene, ScenePlan, validate_scene_plan


class TestNlChoreoContracts(unittest.TestCase):
    def test_validate_scene_plan_f400_ok(self):
        fleet = FleetSpec(drone_count=7, fleet_type="F400", drone_class="Drone")
        plan = ScenePlan(
            user_intent="test",
            fleet=fleet,
            scenes=[Scene(scene_id="SC01", start=0.0, end=10.0, formation="line", motion_style="smooth", transition_style="ease")],
        )
        validate_scene_plan(plan)

    def test_validate_scene_plan_reject_mixed_mapping(self):
        fleet = FleetSpec(drone_count=7, fleet_type="F400", drone_class="Drone6")
        plan = ScenePlan(
            user_intent="test",
            fleet=fleet,
            scenes=[Scene(scene_id="SC01", start=0.0, end=10.0, formation="line", motion_style="smooth", transition_style="ease")],
        )
        with self.assertRaises(ValueError):
            validate_scene_plan(plan)


if __name__ == "__main__":
    unittest.main()
