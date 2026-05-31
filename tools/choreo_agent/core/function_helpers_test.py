"""Tests for project_template/scripts/function.py helpers."""

import importlib.util
from pathlib import Path


class FakeDrone:
    def __init__(self, time_ms: int):
        self.time = time_ms
        self.called = []

    def inittime(self, time_s: int):
        self.called.append(time_s)
        self.time = time_s * 1000


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


if __name__ == "__main__":
    test_auto_init_uses_time_cursor_not_missing_init_time()
    print("OK")
