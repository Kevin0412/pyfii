import argparse
import itertools
import math
import os
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

sys.path.append(os.getcwd() + r"/src")
sys.path.append(os.getcwd() + r"/src/pyfii")

from pyfii.drone import Drone, drone_config_6m
from pyfii.fii import Fii
from pyfii.read import read_fii


DRONE_COUNT = 7
FIELD_MIN = 0
FIELD_MAX = 560
Z_MIN = 80
Z_MAX = 250
F400_SAFE_DISTANCE_CM = 51.0
PLAN_SAFE_DISTANCE_CM = 60.0
ASSIGNMENT_DISTANCE_CAP_CM = 78.0
OUTPUT_ROOT = Path("output/ai_choreo_candidates_60s")
DEFAULT_VARIANTS = ("weave_exchange", "burst_recompose", "calligraphy_lines")
OUTPUT_DIR = OUTPUT_ROOT / DEFAULT_VARIANTS[0]
PROJECT_NAME = f"{DEFAULT_VARIANTS[0]}_60s"
PROJECT_PATH = OUTPUT_DIR / PROJECT_NAME


@dataclass
class RawFrame:
    time_sec: int
    name: str
    points: list[tuple[int, int, int]]
    color: str


@dataclass
class OptimizedFrame:
    time_sec: int
    name: str
    points: list[tuple[int, int, int]]
    color: str
    permutation: tuple[int, ...]
    path_min_cm: float
    max_travel_cm: float
    travel_time_needed_sec: float


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _rotate(u: float, v: float, angle: float) -> tuple[float, float]:
    ca = math.cos(angle)
    sa = math.sin(angle)
    return u * ca - v * sa, u * sa + v * ca


def _rounded_point(x: float, y: float, z: float) -> tuple[int, int, int]:
    return (
        int(round(_clamp(x, FIELD_MIN, FIELD_MAX))),
        int(round(_clamp(y, FIELD_MIN, FIELD_MAX))),
        int(round(_clamp(z, Z_MIN, Z_MAX))),
    )


def _ring(
    rx: float,
    ry: float,
    phase: float,
    cx: float = 280,
    cy: float = 280,
    zbase: float = 145,
    zamp: float = 30,
) -> list[tuple[int, int, int]]:
    points = []
    for i in range(DRONE_COUNT):
        theta = 2 * math.pi * i / DRONE_COUNT + phase - math.pi / 2
        points.append(
            _rounded_point(
                cx + rx * math.cos(theta),
                cy + ry * math.sin(theta),
                zbase + zamp * math.sin(theta + 0.8),
            )
        )
    return points


def _line(
    length: float,
    angle: float,
    wave: float,
    cx: float = 280,
    cy: float = 280,
    zbase: float = 130,
    z_slope: float = 8,
) -> list[tuple[int, int, int]]:
    points = []
    for i in range(DRONE_COUNT):
        u = -length / 2 + length * i / (DRONE_COUNT - 1)
        v = wave * math.sin(i * math.pi / 2)
        x, y = _rotate(u, v, angle)
        points.append(_rounded_point(cx + x, cy + y, zbase + (i - 3) * z_slope))
    return points


def _arc(
    radius: float,
    spread: float,
    angle0: float,
    cx: float = 280,
    cy: float = 280,
    zbase: float = 135,
) -> list[tuple[int, int, int]]:
    points = []
    for i in range(DRONE_COUNT):
        theta = angle0 + spread * i / (DRONE_COUNT - 1)
        points.append(
            _rounded_point(
                cx + radius * math.cos(theta),
                cy + radius * math.sin(theta),
                zbase + 26 * math.sin(theta * 1.3),
            )
        )
    return points


def _snake(
    length: float,
    amp: float,
    angle: float,
    phase: float,
    cx: float = 280,
    cy: float = 280,
    zbase: float = 145,
) -> list[tuple[int, int, int]]:
    points = []
    for i in range(DRONE_COUNT):
        u = -length / 2 + length * i / (DRONE_COUNT - 1)
        theta = i / (DRONE_COUNT - 1) * 2 * math.pi + phase
        v = amp * math.sin(theta)
        x, y = _rotate(u, v, angle)
        points.append(_rounded_point(cx + x, cy + y, zbase + 24 * math.cos(theta)))
    return points


def _double_triangle(angle: float, cx: float = 280, cy: float = 280) -> list[tuple[int, int, int]]:
    base = [
        (-180, -115),
        (-60, -115),
        (-120, 60),
        (60, 120),
        (180, 120),
        (120, -60),
        (0, 0),
    ]
    z_values = [118, 158, 210, 128, 170, 218, 145]
    points = []
    for (u, v), z in zip(base, z_values):
        x, y = _rotate(u, v, angle)
        points.append(_rounded_point(cx + x, cy + y, z))
    return points


def _diamond(angle: float, cx: float = 280, cy: float = 280) -> list[tuple[int, int, int]]:
    base = [(0, -215), (135, -130), (210, 0), (135, 130), (0, 215), (-135, 130), (-210, 0)]
    z_values = [125, 155, 190, 145, 175, 210, 160]
    points = []
    for (u, v), z in zip(base, z_values):
        x, y = _rotate(u, v, angle)
        points.append(_rounded_point(cx + x, cy + y, z))
    return points


def _chevron(angle: float, cx: float = 280, cy: float = 280) -> list[tuple[int, int, int]]:
    base = [
        (-225, -140),
        (-150, -80),
        (-75, -35),
        (0, 0),
        (75, -35),
        (150, -80),
        (225, -140),
    ]
    z_values = [132, 170, 208, 145, 183, 221, 158]
    points = []
    for (u, v), z in zip(base, z_values):
        x, y = _rotate(u, v, angle)
        points.append(_rounded_point(cx + x, cy + y, z))
    return points


def configure_output(variant: str) -> None:
    global OUTPUT_DIR, PROJECT_NAME, PROJECT_PATH
    safe_variant = variant.replace("/", "_").replace(" ", "_")
    OUTPUT_DIR = OUTPUT_ROOT / safe_variant
    PROJECT_NAME = f"{safe_variant}_60s"
    PROJECT_PATH = OUTPUT_DIR / PROJECT_NAME


def build_design_frames(variant: str) -> list[RawFrame]:
    if variant == "burst_recompose":
        return [
            RawFrame(4, "wide diagonal reveal", _line(430, -0.22, 35, zbase=116, z_slope=9), "#4dd7ff"),
            RawFrame(7, "diamond expansion", _diamond(0.05), "#fff06e"),
            RawFrame(10, "offset crown bridge", _ring(210, 160, 0.55, 278, 274, 154, 34), "#ff9f43"),
            RawFrame(13, "low double triangle", _double_triangle(-0.52), "#ff6f91"),
            RawFrame(16, "vertical break line", _line(440, math.pi / 2 + 0.34, 78, zbase=142, z_slope=-8), "#74ff9b"),
            RawFrame(19, "ribbon recoil", _snake(420, 118, 0.55, 0.8, zbase=154), "#b38bff"),
            RawFrame(22, "chevron lock", _chevron(0.22), "#69dbff"),
            RawFrame(25, "outer orbit bridge", _ring(220, 170, 1.7, 282, 282, 164, 35), "#ffe066"),
            RawFrame(28, "reverse half arc", _arc(220, 1.45 * math.pi, -0.2 * math.pi, zbase=150), "#ff8a3d"),
            RawFrame(31, "tilted diamond", _diamond(1.2), "#ff5da2"),
            RawFrame(34, "counter ribbon", _snake(420, 112, -0.9, 2.0, zbase=160), "#8ce99a"),
            RawFrame(37, "broad slash", _line(430, 0.65, 94, zbase=148, z_slope=8), "#66d9ff"),
            RawFrame(40, "rotated triangle burst", _double_triangle(1.5), "#d191ff"),
            RawFrame(43, "compressed orbit", _ring(178, 205, 2.85, 276, 280, 158, 35), "#c4f052"),
            RawFrame(46, "falling chevron", _chevron(-1.1), "#ffbe4a"),
            RawFrame(49, "late arc sweep", _arc(215, 1.62 * math.pi, 0.32 * math.pi, zbase=150), "#ff728a"),
            RawFrame(52, "final recoil ribbon", _snake(435, 122, -0.15, 2.7, zbase=150), "#69dbff"),
            RawFrame(55, "last diamond flare", _diamond(-0.35), "#ffffff"),
            RawFrame(58, "straight bow", _line(440, 0, 0, zbase=110, z_slope=0), "#ffffff"),
        ]

    if variant == "calligraphy_lines":
        return [
            RawFrame(4, "thin ink stroke", _line(430, 0.12, 88, zbase=112, z_slope=7), "#51d6ff"),
            RawFrame(7, "left falling arc", _arc(215, 1.52 * math.pi, -0.92 * math.pi, zbase=134), "#7cff6b"),
            RawFrame(10, "s stroke", _snake(430, 128, -0.18, 0.25, zbase=148), "#b985ff"),
            RawFrame(13, "quiet bridge crown", _ring(190, 180, 0.8, 280, 280, 150, 30), "#ffe05a"),
            RawFrame(16, "broken brush triangle", _double_triangle(0.72), "#ff8a3d"),
            RawFrame(19, "right falling arc", _arc(218, 1.58 * math.pi, -0.05 * math.pi, zbase=150), "#ff5da2"),
            RawFrame(22, "folded chevron", _chevron(0.85), "#6be7ff"),
            RawFrame(25, "vertical ink line", _line(440, math.pi / 2 - 0.1, 70, zbase=142, z_slope=-7), "#7dff9d"),
            RawFrame(28, "hook ribbon", _snake(420, 120, 0.78, 1.25, zbase=160), "#fff06e"),
            RawFrame(31, "diamond punctuation", _diamond(0.45), "#ff9f43"),
            RawFrame(34, "long counter stroke", _line(430, -0.72, 96, zbase=150, z_slope=8), "#ff6f91"),
            RawFrame(37, "small crown pause", _ring(170, 215, 2.2, 276, 278, 158, 34), "#b38bff"),
            RawFrame(40, "wide s stroke", _snake(440, 130, -0.58, 2.25, zbase=158), "#63e6be"),
            RawFrame(43, "open reverse arc", _arc(220, 1.65 * math.pi, 0.22 * math.pi, zbase=148), "#c4f052"),
            RawFrame(46, "brush chevron", _chevron(-0.48), "#ffbe4a"),
            RawFrame(49, "last orbit comma", _ring(205, 165, 3.65, 282, 276, 158, 32), "#ff728a"),
            RawFrame(52, "closing ribbon", _snake(430, 112, 0.28, 2.95, zbase=148), "#d191ff"),
            RawFrame(55, "low underline", _line(440, 0.04, 25, zbase=120, z_slope=3), "#69dbff"),
            RawFrame(58, "white bow", _line(440, 0, 0, zbase=110, z_slope=0), "#ffffff"),
        ]

    if variant != "weave_exchange":
        raise ValueError(f"unknown variant: {variant}")

    return [
        RawFrame(4, "opening slanted wave", _line(430, 0.35, 70, zbase=112, z_slope=8), "#51d6ff"),
        RawFrame(7, "opening arc", _arc(215, 1.55 * math.pi, -0.85 * math.pi, zbase=132), "#7cff6b"),
        RawFrame(10, "ellipse bridge", _ring(205, 150, 0.15, 285, 270, 150, 34), "#ffe05a"),
        RawFrame(13, "role shift crown", _ring(180, 205, 0.95, 285, 275, 155, 34), "#ff8a3d"),
        RawFrame(16, "double triangle", _double_triangle(0.3), "#ff5da2"),
        RawFrame(19, "snake ribbon", _snake(420, 115, -0.25, 0.4, zbase=152), "#b985ff"),
        RawFrame(22, "ring bridge shift", _ring(215, 165, 1.6, 270, 285, 160, 36), "#6be7ff"),
        RawFrame(25, "vertical wave line", _line(440, math.pi / 2 - 0.25, 75, zbase=140, z_slope=-7), "#7dff9d"),
        RawFrame(28, "diamond burst", _diamond(0.75), "#fff06e"),
        RawFrame(31, "orbit bridge", _ring(175, 215, 2.15, 275, 275, 158, 38), "#ff9f43"),
        RawFrame(34, "rotated double triangle", _double_triangle(math.pi / 2 + 0.25), "#ff6f91"),
        RawFrame(37, "diagonal serpent", _snake(420, 115, 0.9, 1.6, zbase=162), "#b38bff"),
        RawFrame(40, "expanded crown", _ring(220, 160, 2.9, 285, 285, 165, 34), "#63e6be"),
        RawFrame(43, "reverse arc", _arc(215, 1.65 * math.pi, 0.1 * math.pi, zbase=150), "#c4f052"),
        RawFrame(46, "counter diagonal", _line(430, -0.7, 80, zbase=148, z_slope=8), "#ffbe4a"),
        RawFrame(49, "compression bridge", _ring(185, 190, 3.75, 280, 275, 158, 35), "#ff728a"),
        RawFrame(52, "swept chevron", _chevron(-0.55), "#d191ff"),
        RawFrame(55, "final ribbon", _snake(440, 130, 0.15, 2.5, zbase=150), "#69dbff"),
        RawFrame(58, "final straight bow", _line(440, 0, 0, zbase=110, z_slope=0), "#ffffff"),
    ]


def horizontal_distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def point_distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def min_horizontal_distance(points: list[tuple[float, float, float]]) -> tuple[float, tuple[int, int]]:
    best_dist = 10**9
    best_pair = (0, 0)
    for i in range(DRONE_COUNT):
        for j in range(i + 1, DRONE_COUNT):
            dist = horizontal_distance(points[i], points[j])
            if dist < best_dist:
                best_dist = dist
                best_pair = (i + 1, j + 1)
    return best_dist, best_pair


def transition_min_distance(
    start: list[tuple[int, int, int]],
    end: list[tuple[int, int, int]],
    samples: int,
) -> tuple[float, tuple[int, int], float]:
    best_dist = 10**9
    best_pair = (0, 0)
    best_alpha = 0.0
    for step in range(samples + 1):
        alpha = step / samples
        points = [
            tuple(start[i][axis] * (1 - alpha) + end[i][axis] * alpha for axis in range(3))
            for i in range(DRONE_COUNT)
        ]
        dist, pair = min_horizontal_distance(points)
        if dist < best_dist:
            best_dist = dist
            best_pair = pair
            best_alpha = alpha
    return best_dist, best_pair, best_alpha


def travel_time_for_speed(distance_cm: float, speed_cm_s: int, acc_cm_s2: int) -> float:
    if distance_cm <= 0:
        return 0.0
    cruise_threshold = speed_cm_s * speed_cm_s / acc_cm_s2
    if distance_cm > cruise_threshold:
        return (distance_cm - cruise_threshold) / speed_cm_s + 2 * speed_cm_s / acc_cm_s2
    return 2 * math.sqrt(distance_cm / acc_cm_s2)


def fastest_travel_time(distance_cm: float) -> float:
    return travel_time_for_speed(distance_cm, 200, 400)


def max_travel(start: list[tuple[int, int, int]], end: list[tuple[int, int, int]]) -> float:
    return max(point_distance(start[i], end[i]) for i in range(DRONE_COUNT))


def optimize_assignment(
    previous: list[tuple[int, int, int]],
    target_roles: list[tuple[int, int, int]],
    duration_sec: float,
) -> tuple[list[tuple[int, int, int]], tuple[int, ...], float, float, float]:
    best = None
    for permutation in itertools.permutations(range(DRONE_COUNT)):
        candidate = [target_roles[i] for i in permutation]
        path_min, _, _ = transition_min_distance(previous, candidate, samples=18)
        travel = max_travel(previous, candidate)
        needed = fastest_travel_time(travel)
        feasible = needed <= max(0.1, duration_sec - 0.05)
        avg_travel = sum(point_distance(previous[i], candidate[i]) for i in range(DRONE_COUNT)) / DRONE_COUNT
        role_changes = sum(1 for idx, target_idx in enumerate(permutation) if idx != target_idx)
        # Once a transition is safely above the buffer, prefer visible role exchange
        # instead of rewarding ever more conservative neighbor preservation.
        score = (
            1 if feasible else 0,
            min(path_min, ASSIGNMENT_DISTANCE_CAP_CM),
            role_changes,
            avg_travel,
            path_min,
            -needed,
        )
        if best is None or score > best[0]:
            best = (score, candidate, permutation, path_min, travel, needed)
    if best is None:
        raise RuntimeError("assignment optimizer failed")
    _, candidate, permutation, path_min, travel, needed = best
    return candidate, permutation, path_min, travel, needed


def optimize_frames(raw_frames: list[RawFrame]) -> tuple[list[tuple[int, list[tuple[int, int, int]], str]], list[OptimizedFrame]]:
    start_points = list(raw_frames[0].points)
    optimized: list[OptimizedFrame] = []
    previous = start_points
    previous_time = 1

    for frame in raw_frames:
        assigned, permutation, path_min, travel, needed = optimize_assignment(
            previous=previous,
            target_roles=frame.points,
            duration_sec=frame.time_sec - previous_time,
        )
        optimized.append(
            OptimizedFrame(
                time_sec=frame.time_sec,
                name=frame.name,
                points=assigned,
                color=frame.color,
                permutation=permutation,
                path_min_cm=path_min,
                max_travel_cm=travel,
                travel_time_needed_sec=needed,
            )
        )
        previous = assigned
        previous_time = frame.time_sec

    timeline = [(1, start_points, "takeoff lattice")]
    timeline.extend((frame.time_sec, frame.points, frame.name) for frame in optimized)
    return timeline, optimized


def speed_for_segment(distance_cm: float, duration_sec: float) -> tuple[int, int]:
    usable_duration = max(0.35, duration_sec - 0.25)
    for speed in range(20, 201):
        acc = max(50, min(400, speed * 2))
        if travel_time_for_speed(distance_cm, speed, acc) <= usable_duration:
            return speed, acc
    return 200, 400


def validate_timeline(timeline: list[tuple[int, list[tuple[int, int, int]], str]]) -> dict[str, object]:
    global_min = 10**9
    global_pair = (0, 0)
    global_time = 0.0
    largest_travel = 0.0
    tight_segments = []

    for time_sec, points, name in timeline:
        for x, y, z in points:
            if not (FIELD_MIN <= x <= FIELD_MAX and FIELD_MIN <= y <= FIELD_MAX and Z_MIN <= z <= Z_MAX):
                raise ValueError(f"{name} has out-of-range point {(x, y, z)}")
        static_min, pair = min_horizontal_distance(points)
        if static_min < PLAN_SAFE_DISTANCE_CM:
            raise ValueError(f"{name} static distance too close: {static_min:.1f}cm for d{pair[0]}/d{pair[1]}")

    for idx in range(1, len(timeline)):
        start_t, start_points, start_name = timeline[idx - 1]
        end_t, end_points, end_name = timeline[idx]
        duration = end_t - start_t
        samples = max(1, int(duration * 80))
        path_min, pair, alpha = transition_min_distance(start_points, end_points, samples=samples)
        if path_min < global_min:
            global_min = path_min
            global_pair = pair
            global_time = start_t + duration * alpha
        travel = max_travel(start_points, end_points)
        largest_travel = max(largest_travel, travel)
        needed = fastest_travel_time(travel)
        if needed > duration - 0.05:
            tight_segments.append((start_name, end_name, travel, needed, duration))

    if global_min < PLAN_SAFE_DISTANCE_CM:
        raise ValueError(
            f"path distance too close: {global_min:.1f}cm at {global_time:.2f}s for d{global_pair[0]}/d{global_pair[1]}"
        )
    if tight_segments:
        raise ValueError(f"segments too tight for F400 speed limits: {tight_segments}")

    spans = []
    for drone_idx in range(DRONE_COUNT):
        xs = [points[drone_idx][0] for _, points, _ in timeline]
        ys = [points[drone_idx][1] for _, points, _ in timeline]
        spans.append((max(xs) - min(xs), max(ys) - min(ys)))
        if max(xs) - min(xs) < 140 or max(ys) - min(ys) < 140:
            raise ValueError(f"d{drone_idx + 1} does not move enough in XY: span={spans[-1]}")

    return {
        "planned_min_distance_cm": round(global_min, 2),
        "planned_min_pair": global_pair,
        "planned_min_time_sec": round(global_time, 3),
        "largest_travel_cm": round(largest_travel, 2),
        "drone_spans_cm": spans,
    }


def _hex_to_bgr(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[4:6], 16), int(color[2:4], 16), int(color[0:2], 16)


def render_keyframe_images(timeline: list[tuple[int, list[tuple[int, int, int]], str]], colors: dict[int, str]) -> None:
    keyframe_dir = OUTPUT_DIR / "keyframes"
    keyframe_dir.mkdir(parents=True, exist_ok=True)
    scale = 2
    margin = 60
    canvas_size = FIELD_MAX * scale + margin * 2
    trails = [[] for _ in range(DRONE_COUNT)]

    for time_sec, points, name in timeline[1:]:
        img = np.full((canvas_size, canvas_size, 3), 245, dtype=np.uint8)
        for grid in range(0, FIELD_MAX + 1, 70):
            x = margin + grid * scale
            cv2.line(img, (x, margin), (x, margin + FIELD_MAX * scale), (220, 220, 220), 1)
            y = margin + grid * scale
            cv2.line(img, (margin, y), (margin + FIELD_MAX * scale, y), (220, 220, 220), 1)
        cv2.rectangle(
            img,
            (margin, margin),
            (margin + FIELD_MAX * scale, margin + FIELD_MAX * scale),
            (60, 60, 60),
            2,
        )

        for i, point in enumerate(points):
            trails[i].append(point)
            bgr = _hex_to_bgr(colors.get(time_sec, "#51d6ff"))
            trail_pts = []
            for x, y, _ in trails[i][-7:]:
                trail_pts.append((int(margin + x * scale), int(margin + (FIELD_MAX - y) * scale)))
            for a, b in zip(trail_pts, trail_pts[1:]):
                cv2.line(img, a, b, bgr, 2)
            x, y, z = point
            px = int(margin + x * scale)
            py = int(margin + (FIELD_MAX - y) * scale)
            cv2.circle(img, (px, py), 18, bgr, -1)
            cv2.circle(img, (px, py), 19, (30, 30, 30), 2)
            cv2.putText(img, str(i + 1), (px - 8, py + 7), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (20, 20, 20), 2)
            cv2.putText(img, f"z{z}", (px - 18, py + 38), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (60, 60, 60), 1)

        cv2.putText(img, f"T+{time_sec:02d}s  {name}", (margin, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (30, 30, 30), 2)
        cv2.imwrite(str(keyframe_dir / f"keyframe_{time_sec:02d}s.png"), img)


def build_pyfii_project(timeline: list[tuple[int, list[tuple[int, int, int]], str]], colors: dict[int, str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    drones = [
        Drone(0, 0, drone_config_6m, f"192.168.51.{51 + idx}")
        for idx in range(DRONE_COUNT)
    ]

    start_points = timeline[0][1]
    for drone, point in zip(drones, start_points):
        drone.X = drone.x = point[0]
        drone.Y = drone.y = point[1]
        drone.takeoff(1, point[2])

    previous_points = start_points
    previous_time = timeline[0][0]
    for time_sec, points, _ in timeline[1:]:
        duration = time_sec - previous_time
        for drone, previous, target in zip(drones, previous_points, points):
            distance = point_distance(previous, target)
            speed, acc = speed_for_segment(distance, duration)
            drone.inittime(time_sec)
            drone.VelXY(speed, acc)
            drone.VelZ(speed, acc)
            drone.move2(*target)
            drone.TurnOnAll(colors.get(time_sec, "#ffffff"))
        previous_points = points
        previous_time = time_sec

    for drone in drones:
        drone.inittime(60)
        drone.TurnOnAll("#ffffff")
        drone.land()
        drone.end()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        project = Fii(str(PROJECT_PATH), drones)
        project.save()
    unsafe = [str(item.message) for item in caught if "distance between" in str(item.message)]
    if unsafe:
        raise RuntimeError("pyfii emitted distance warnings while saving: " + "; ".join(unsafe[:5]))


def readback_safety() -> dict[str, object]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        data, t0, music, field, device = read_fii(str(PROJECT_PATH), fps=120)

    min_dist = 10**9
    min_pair = (0, 0)
    min_time = 0.0
    max_len = max(len(track) for track in data)
    for frame_idx in range(max_len):
        points = []
        time_sec = 0.0
        for track in data:
            item = track[frame_idx] if frame_idx < len(track) else track[-1]
            time_sec = max(time_sec, float(item[0]) / 1000.0)
            points.append((float(item[1]), float(item[2]), float(item[3])))
        dist, pair = min_horizontal_distance(points)
        if dist < min_dist:
            min_dist = dist
            min_pair = pair
            min_time = time_sec

    warning_texts = [str(item.message) for item in caught]
    unsafe = [msg for msg in warning_texts if "distance between" in msg]
    if min_dist < F400_SAFE_DISTANCE_CM or unsafe:
        raise RuntimeError(
            f"readback safety failed: min={min_dist:.1f}cm at {min_time:.2f}s pair={min_pair}, warnings={unsafe[:5]}"
        )

    return {
        "readback_min_distance_cm": round(min_dist, 2),
        "readback_min_pair": min_pair,
        "readback_min_time_sec": round(min_time, 3),
        "readback_frame_count_hint": int(t0),
        "field": field,
        "device": device,
        "warning_count": len(warning_texts),
    }


def write_report(
    variant: str,
    optimized: list[OptimizedFrame],
    plan_summary: dict[str, object],
    readback_summary: dict[str, object],
) -> None:
    lines = [
        f"# AI Choreography Candidate: {variant}",
        "",
        "## Design",
        "",
        "- 7 F400 drones on the 6m field.",
        "- 60s flight timeline: takeoff at 1s, choreographic layers from 4s to 58s, land at 60s.",
        "- The design deliberately avoids fixed per-drone safety zones. Ring/neighbor-preserving moves are allowed only when they serve the visual idea; they are not treated as a global restriction.",
        "- The assignment optimizer caps the value of extra clearance, then prefers role changes and larger motion. Once a transition is safe enough, it stops rewarding conservatism.",
        "- Formation changes include slanted wave, arc, crown, double triangle, snake ribbon, vertical wave line, diamond burst, reverse arc, chevron, and final bow.",
        "- Role rotation is produced by per-frame assignment optimization, so center, edge, lead, and outer roles are not held by one fixed drone.",
        "",
        "## Optimization Result",
        "",
        f"- Planned dense-sample min distance: {plan_summary['planned_min_distance_cm']} cm at {plan_summary['planned_min_time_sec']}s, pair d{plan_summary['planned_min_pair'][0]}/d{plan_summary['planned_min_pair'][1]}.",
        f"- Readback min distance from generated Fii: {readback_summary['readback_min_distance_cm']} cm at {readback_summary['readback_min_time_sec']}s, pair d{readback_summary['readback_min_pair'][0]}/d{readback_summary['readback_min_pair'][1]}.",
        f"- Largest single-layer travel: {plan_summary['largest_travel_cm']} cm.",
        f"- Readback field/device: {readback_summary['field']}m / {readback_summary['device']}.",
        "",
        "## Keyframes",
        "",
        "| Time | Scene | Permutation | Path min | Max travel | Fastest needed |",
        "| ---: | --- | --- | ---: | ---: | ---: |",
    ]
    for frame in optimized:
        lines.append(
            f"| {frame.time_sec}s | {frame.name} | {frame.permutation} | "
            f"{frame.path_min_cm:.1f}cm | {frame.max_travel_cm:.1f}cm | {frame.travel_time_needed_sec:.2f}s |"
        )

    lines.extend(
        [
        "",
        "## Artifacts",
            "",
            f"- Project: `{PROJECT_PATH}`",
            f"- Keyframe images: `{OUTPUT_DIR / 'keyframes'}`",
            "",
        ]
    )
    (OUTPUT_DIR / "design_report.md").write_text("\n".join(lines), encoding="utf-8")


def render_video() -> None:
    from pyfii.show import show

    data, t0, music, field, device = read_fii(str(PROJECT_PATH), fps=120)
    show(data, t0, music, field=field, device=device, save=str(PROJECT_PATH), FPS=20, max_fps=120)


def generate_candidate(variant: str, render_preview: bool = False) -> dict[str, object]:
    configure_output(variant)
    raw_frames = build_design_frames(variant)
    timeline, optimized = optimize_frames(raw_frames)
    colors = {frame.time_sec: frame.color for frame in optimized}
    plan_summary = validate_timeline(timeline)
    render_keyframe_images(timeline, colors)
    build_pyfii_project(timeline, colors)
    readback_summary = readback_safety()
    write_report(variant, optimized, plan_summary, readback_summary)
    if render_preview:
        render_video()
    return {
        "variant": variant,
        "project": str(PROJECT_PATH),
        "report": str(OUTPUT_DIR / "design_report.md"),
        "keyframes": str(OUTPUT_DIR / "keyframes"),
        **plan_summary,
        **readback_summary,
    }


def write_comparison_report(rows: list[dict[str, object]]) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    lines = [
        "# AI Choreography Candidates 60s",
        "",
        "这些是候选动作，不是工作流改造。先挑动作审美，再把有效经验沉淀进工作流。",
        "",
        "| Variant | Planned min | Readback min | Largest travel | Report | Keyframes |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['variant']} | {row['planned_min_distance_cm']}cm | "
            f"{row['readback_min_distance_cm']}cm | {row['largest_travel_cm']}cm | "
            f"`{row['report']}` | `{row['keyframes']}` |"
        )
    lines.append("")
    (OUTPUT_ROOT / "comparison_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=DEFAULT_VARIANTS, default=DEFAULT_VARIANTS[0])
    parser.add_argument("--all", action="store_true", help="generate all choreography candidates")
    parser.add_argument("--render-video", action="store_true", help="also render 2D mp4 previews")
    args = parser.parse_args()

    variants = DEFAULT_VARIANTS if args.all else (args.variant,)
    rows = []
    for variant in variants:
        rows.append(generate_candidate(variant, render_preview=args.render_video))
    if len(rows) > 1:
        write_comparison_report(rows)

    print("AI keyframe workflow complete")
    for row in rows:
        print(f"variant: {row['variant']}")
        print(f"project: {row['project']}")
        print(f"planned min distance: {row['planned_min_distance_cm']} cm")
        print(f"readback min distance: {row['readback_min_distance_cm']} cm")


if __name__ == "__main__":
    main()
