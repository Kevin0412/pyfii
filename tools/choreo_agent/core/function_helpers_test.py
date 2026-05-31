"""Tests for project_template/scripts/function.py helpers."""

import importlib.util
from pathlib import Path


class FakeDrone:
    def __init__(self, time_ms: int):
        self.time = time_ms
        self.x = 0
        self.y = 0
        self.z = 100
        self.called = []
        self.moves = []

    def inittime(self, time_s: int):
        self.called.append(time_s)
        self.time = time_s * 1000

    def VelXY(self, _speed, _accel):
        pass

    def VelZ(self, _speed, _accel):
        pass

    def move2(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
        self.moves.append((x, y, z))


def _load_template_function_module():
    path = Path(__file__).resolve().parent.parent / "project_template" / "scripts" / "function.py"
    spec = importlib.util.spec_from_file_location("template_function", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_auto_init_uses_time_cursor_not_missing_init_time():
    module = _load_template_function_module()
    drones = [FakeDrone(1200), FakeDrone(6400), FakeDrone(6000)]

    t = module.auto_init(drones)

    assert t == 7
    assert [d.called for d in drones] == [[7], [7], [7]]
    assert [d.time for d in drones] == [7000, 7000, 7000]
    print("PASSED: auto_init uses Drone.time cursor, not init_time")


def test_auto_init_waits_for_last_move_without_delay():
    module = _load_template_function_module()
    drone = FakeDrone(4000)

    module.move2(drone, (120, 0, 100), 3500)
    t = module.auto_init([drone])

    assert t == 8
    assert drone.called == [8]
    assert drone.time == 8000
    assert drone._agent_motion_end_ms == 7500
    print("PASSED: auto_init waits for pending final move")


if __name__ == "__main__":
    test_auto_init_uses_time_cursor_not_missing_init_time()
    test_auto_init_waits_for_last_move_without_delay()
    print("OK")
