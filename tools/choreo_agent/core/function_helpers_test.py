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
        self.lights = []

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

    def delay(self, ms: int):
        self.called.append(("delay", ms))
        self.time += ms

    def TurnOnAll(self, color: str):
        self.lights.append(color)


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


def test_best_assign_accepts_2d_and_returns_targets():
    module = _load_template_function_module()
    starts = [(0, 0), (100, 0)]
    targets = [(100, 0), (0, 0)]

    assigned = module.best_assign(starts, targets)

    assert assigned == [(0, 0), (100, 0)]
    print("PASSED: best_assign accepts 2D and returns targets list")


def test_far_assign_encourages_large_safe_paths():
    module = _load_template_function_module()
    starts = [(100, 80, 150), (100, 230, 150), (100, 380, 150), (100, 530, 150)]
    targets = [(500, 80, 200), (500, 230, 200), (500, 380, 200), (500, 530, 200)]

    assigned = module.far_assign(starts, targets, min_path_cm=250)
    distances = [module.Distance(a, b) for a, b in zip(starts, assigned)]

    assert sorted(assigned) == sorted(targets)
    assert sorted(distances)[len(distances) // 2] >= 250
    print("PASSED: far_assign encourages larger paths")


def test_wait_until_uses_delay_not_inittime():
    module = _load_template_function_module()
    drones = [FakeDrone(1000), FakeDrone(2500)]

    t = module.wait_until(drones, 4)

    assert t == 4
    assert drones[0].time == 4000
    assert drones[1].time == 4000
    assert drones[0].called == [("delay", 3000)]
    assert drones[1].called == [("delay", 1500)]
    print("PASSED: wait_until aligns by delay, not inittime")


def test_move_group_returns_targets_and_records_motion_end():
    module = _load_template_function_module()
    drones = [FakeDrone(4000), FakeDrone(4000), FakeDrone(4000)]
    targets = [(100, 120, 130), (220, 240, 160), (340, 360, 190)]

    prev = module.move_group(drones, targets, 3000, "#44aaff", 4)

    assert prev == targets
    assert [d.moves[-1] for d in drones] == targets
    assert [d.lights for d in drones] == [["#44aaff"] * 4] * 3
    assert [d._agent_motion_end_ms for d in drones] == [7000, 7000, 7000]
    assert all(("delay", 2700) in d.called for d in drones)


def test_move_group_staggered_adds_group_delay_and_color_cycle():
    module = _load_template_function_module()
    drones = [FakeDrone(4000), FakeDrone(4000), FakeDrone(4000), FakeDrone(4000)]
    targets = [(100, 120, 130), (220, 240, 160), (340, 360, 190), (460, 480, 220)]

    prev = module.move_group_staggered(
        drones,
        targets,
        3000,
        ["#44aaff", "#ffcc44"],
        4,
        group_mod=3,
        stagger_ms=120,
    )

    assert prev == targets
    assert drones[0].called[0] == ("delay", 100)
    assert drones[1].called[0] == ("delay", 120)
    assert drones[2].called[0] == ("delay", 240)
    assert drones[3].called[0] == ("delay", 100)
    assert drones[0].lights == ["#44aaff"] * 4
    assert drones[1].lights == ["#ffcc44"] * 4


def test_geometry_primitives_return_safe_points_for_7_and_9():
    module = _load_template_function_module()
    builders = [
        module.geo_wide_v,
        module.geo_arrow,
        module.geo_box,
        module.geo_diagonal,
        module.geo_wave,
        module.geo_grid,
    ]

    for n in (7, 9):
        for builder in builders:
            points = builder(n)
            assert len(points) == n
            for x, y, z in points:
                assert 0 <= x <= 560
                assert 0 <= y <= 560
                assert 80 <= z <= 250
            min_d = min(
                module.Distance(points[i], points[j])
                for i in range(n)
                for j in range(i + 1, n)
            )
            assert min_d >= 45, f"{builder.__name__}({n}) minD={min_d}"


if __name__ == "__main__":
    test_auto_init_uses_time_cursor_not_missing_init_time()
    test_auto_init_waits_for_last_move_without_delay()
    test_best_assign_accepts_2d_and_returns_targets()
    test_far_assign_encourages_large_safe_paths()
    test_wait_until_uses_delay_not_inittime()
    test_move_group_returns_targets_and_records_motion_end()
    test_move_group_staggered_adds_group_delay_and_color_cycle()
    test_geometry_primitives_return_safe_points_for_7_and_9()
    print("OK")
