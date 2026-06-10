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


def test_star_import_surface_excludes_geo_templates():
    module = _load_template_function_module()
    public = set(module.__all__)

    assert "custom_points" in public
    assert "best_assign" in public
    assert "far_assign" in public
    assert "move_group" in public
    assert all(not name.startswith("geo_") for name in public)
    print("PASSED: agent import surface excludes geo templates")


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


def test_far_assign_penalizes_crossing_collisions():
    module = _load_template_function_module()
    starts = [
        (80, 80, 120),
        (80, 480, 120),
        (480, 80, 120),
        (480, 480, 120),
    ]
    targets = [
        (480, 80, 120),
        (480, 480, 120),
        (80, 480, 120),
        (80, 80, 120),
    ]

    assigned = module.far_assign(starts, targets, min_path_cm=250, min_spacing_cm=120)
    min_path_spacing = 1e9
    for step in range(0, 51):
        ratio = step / 50
        for i in range(len(starts)):
            for j in range(i + 1, len(starts)):
                ai = tuple(starts[i][k] * (1 - ratio) + assigned[i][k] * ratio for k in range(2))
                aj = tuple(starts[j][k] * (1 - ratio) + assigned[j][k] * ratio for k in range(2))
                min_path_spacing = min(
                    min_path_spacing,
                    ((ai[0] - aj[0]) ** 2 + (ai[1] - aj[1]) ** 2) ** 0.5,
                )

    assert min_path_spacing >= 58


def test_active_min_path_cm_scales_with_flying_ms():
    module = _load_template_function_module()

    assert module.active_min_path_cm(2000) < module.active_min_path_cm(3600)
    assert module.active_min_path_cm(3600) >= 150
    assert module.active_min_path_cm(9000) <= 280


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


def test_custom_points_normalizes_and_checks_count():
    module = _load_template_function_module()

    points = module.custom_points(
        [
            (45, 65, 100),
            (185, 45, 160),
            (340, 75, 220),
            (505, 55, 120),
            (75, 260, 180),
            (280, 230, 240),
            (505, 275, 140),
            (150, 500, 200),
            (405, 485, 160),
        ],
        n=9,
        min_xy_cm=90,
    )

    assert len(points) == 9
    assert all(isinstance(value, int) for point in points for value in point)
    assert all(0 <= x <= 560 and 0 <= y <= 560 and 80 <= z <= 250 for x, y, z in points)


def test_custom_points_rejects_too_close_xy():
    module = _load_template_function_module()

    try:
        module.custom_points([(100, 100, 120), (130, 120, 180)], n=2, min_xy_cm=90)
    except ValueError as exc:
        assert "min_xy" in str(exc)
    else:
        raise AssertionError("custom_points should reject unsafe XY spacing")


def test_jitter_points_preserves_count_and_bounds():
    module = _load_template_function_module()
    base = [
        (45, 65, 100),
        (185, 45, 160),
        (340, 75, 220),
        (505, 55, 120),
        (75, 260, 180),
        (280, 230, 240),
        (505, 275, 140),
        (150, 500, 200),
        (405, 485, 160),
    ]

    points = module.jitter_points(base, xy=12, z=8, seed=2, min_xy_cm=70)

    assert len(points) == 9
    assert all(0 <= x <= 560 and 0 <= y <= 560 and 80 <= z <= 250 for x, y, z in points)


def test_move_group_returns_targets_and_records_motion_end():
    module = _load_template_function_module()
    drones = [FakeDrone(4000), FakeDrone(4000), FakeDrone(4000)]
    targets = [(100, 120, 130), (220, 240, 160), (340, 360, 190)]

    prev = module.move_group(drones, targets, 3000, "#44aaff", 4)

    assert prev == targets
    assert [d.moves[-1] for d in drones] == targets
    assert [d.lights for d in drones] == [["#44aaff"] * 4] * 3
    assert [d._agent_motion_end_ms for d in drones] == [7000, 7000, 7000]
    assert all(("delay", 2600) in d.called for d in drones)


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
                ((points[i][0] - points[j][0]) ** 2 + (points[i][1] - points[j][1]) ** 2) ** 0.5
                for i in range(n)
                for j in range(i + 1, n)
            )
            assert min_d >= 45, f"{builder.__name__}({n}) minD={min_d}"


def test_geometry_primitives_accept_reverse_and_spread_modifiers():
    module = _load_template_function_module()
    builders = [
        module.geo_wide_v,
        module.geo_arrow,
        module.geo_box,
        module.geo_diagonal,
        module.geo_wave,
        module.geo_grid,
    ]

    for builder in builders:
        points = builder(9, reverse=True, spread=1.5)
        assert len(points) == 9
        for x, y, z in points:
            assert 0 <= x <= 560
            assert 0 <= y <= 560
            assert 80 <= z <= 250


def test_geo_box_accepts_common_size_modifiers():
    module = _load_template_function_module()

    points = module.geo_box(9, center=(280, 280), width=420, height=420, spread=1.1)

    assert len(points) == 9
    for x, y, z in points:
        assert 0 <= x <= 560
        assert 0 <= y <= 560
        assert 80 <= z <= 250
    min_xy = min(
        ((points[i][0] - points[j][0]) ** 2 + (points[i][1] - points[j][1]) ** 2) ** 0.5
        for i in range(9)
        for j in range(i + 1, 9)
    )
    assert min_xy >= 100


if __name__ == "__main__":
    test_star_import_surface_excludes_geo_templates()
    test_auto_init_uses_time_cursor_not_missing_init_time()
    test_auto_init_waits_for_last_move_without_delay()
    test_best_assign_accepts_2d_and_returns_targets()
    test_far_assign_encourages_large_safe_paths()
    test_far_assign_penalizes_crossing_collisions()
    test_active_min_path_cm_scales_with_flying_ms()
    test_wait_until_uses_delay_not_inittime()
    test_custom_points_normalizes_and_checks_count()
    test_custom_points_rejects_too_close_xy()
    test_jitter_points_preserves_count_and_bounds()
    test_move_group_returns_targets_and_records_motion_end()
    test_move_group_staggered_adds_group_delay_and_color_cycle()
    test_geometry_primitives_return_safe_points_for_7_and_9()
    test_geometry_primitives_accept_reverse_and_spread_modifiers()
    test_geo_box_accepts_common_size_modifiers()
    print("OK")
