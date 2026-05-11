# -*- coding: utf-8 -*-
# Keyframe-first choreography seeds and runnable program emitters.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


Point3 = tuple[int, int, int]
TimelineLayer = tuple[int, str, list[Point3], str]
DesignSection = tuple[str, int, int, str]
SceneSpec = tuple[int, int, str, int, str]

DRONE_COUNT = 7
F400_SAFE_DISTANCE_CM = 51.0
GPT55_BURST_RECOMPOSE_LAND_TIME_SEC = 62


@dataclass
class KeyframeSeedInfo:
    seed_id: str
    title: str
    timeline: list[TimelineLayer]
    design_sections: list[DesignSection]
    scene_specs: list[SceneSpec]
    land_time_sec: int
    notes: list[str]


@dataclass
class DroneSpan:
    drone_id: int
    span_x_cm: int
    span_y_cm: int


@dataclass
class TimelineDynamicsReport:
    layer_count: int
    transition_count: int
    changed_rank_layers: int
    average_rank_change: float
    rank_changes: list[int]
    drone_spans: list[DroneSpan]

    @property
    def changed_rank_ratio(self) -> float:
        if self.transition_count <= 0:
            return 0.0
        return self.changed_rank_layers / self.transition_count

    @property
    def min_span_x_cm(self) -> int:
        if not self.drone_spans:
            return 0
        return min(item.span_x_cm for item in self.drone_spans)

    @property
    def min_span_y_cm(self) -> int:
        if not self.drone_spans:
            return 0
        return min(item.span_y_cm for item in self.drone_spans)


GPT55_BURST_RECOMPOSE_TIMELINE: list[TimelineLayer] = [
    (1, "takeoff on wide diagonal", [(70, 327, 89), (148, 345, 98), (210, 296, 107), (272, 246, 116), (350, 264, 125), (428, 283, 134), (490, 233, 143)], "#4dd7ff"),
    (4, "wide diagonal reveal", [(70, 327, 89), (148, 345, 98), (210, 296, 107), (272, 246, 116), (350, 264, 125), (428, 283, 134), (490, 233, 143)], "#4dd7ff"),
    (7, "diamond expansion", [(70, 270, 160), (139, 403, 210), (269, 495, 175), (291, 65, 125), (421, 157, 155), (408, 417, 145), (490, 290, 190)], "#fff06e"),
    (10, "offset crown bridge", [(206, 124, 123), (388, 138, 147), (79, 223, 123), (486, 254, 175), (428, 386, 188), (101, 361, 146), (257, 433, 175)], "#ff9f43"),
    (13, "low double triangle", [(280, 280, 145), (206, 392, 210), (171, 210, 158), (496, 295, 170), (354, 168, 218), (67, 270, 118), (392, 354, 128)], "#ff6f91"),
    (16, "vertical break line", [(158, 392, 126), (207, 487, 118), (255, 116, 158), (353, 73, 166), (354, 306, 142), (304, 211, 150), (256, 349, 134)], "#74ff9b"),
    (19, "ribbon recoil", [(101, 304, 147), (415, 462, 171), (324, 208, 137), (399, 220, 161), (414, 329, 177), (57, 242, 171), (205, 268, 131)], "#b38bff"),
    (22, "chevron lock", [(151, 169, 170), (280, 280, 145), (361, 262, 183), (530, 192, 158), (444, 235, 221), (91, 94, 132), (214, 229, 208)], "#69dbff"),
    (25, "outer orbit bridge", [(73, 335, 148), (206, 441, 178), (396, 427, 198), (500, 304, 192), (440, 164, 165), (98, 189, 130), (261, 113, 137)], "#ffe066"),
    (28, "reverse half arc", [(124, 124, 126), (263, 499, 172), (60, 274, 128), (117, 427, 150), (418, 451, 174), (458, 151, 131), (498, 309, 154)], "#ff8a3d"),
    (31, "tilted diamond", [(80, 358, 175), (480, 202, 125), (208, 453, 145), (450, 359, 155), (356, 476, 190), (204, 84, 160), (110, 201, 210)], "#ff5da2"),
    (34, "counter ribbon", [(315, 219, 184), (490, 179, 150), (201, 396, 136), (229, 508, 150), (165, 278, 146), (200, 217, 170), (439, 227, 174)], "#8ce99a"),
    (37, "broad slash", [(337, 323, 156), (451, 410, 172), (109, 268, 132), (223, 237, 140), (109, 150, 124), (337, 205, 148), (337, 442, 164)], "#66d9ff"),
    (40, "rotated triangle burst", [(280, 280, 145), (348, 395, 218), (165, 348, 128), (212, 165, 210), (382, 92, 118), (390, 212, 158), (173, 468, 170)], "#d191ff"),
    (43, "compressed orbit", [(304, 78, 138), (156, 129, 123), (175, 448, 164), (98, 294, 135), (431, 179, 168), (441, 356, 190), (327, 476, 189)], "#c4f052"),
    (46, "falling chevron", [(257, 16, 158), (277, 110, 221), (53, 417, 132), (141, 377, 170), (283, 197, 183), (280, 280, 145), (215, 331, 208)], "#ffbe4a"),
    (49, "late arc sweep", [(214, 76, 136), (389, 95, 163), (85, 372, 141), (220, 486, 167), (83, 195, 124), (491, 240, 176), (395, 462, 175)], "#ff728a"),
    (52, "final recoil ribbon", [(272, 228, 172), (503, 299, 128), (126, 233, 130), (362, 338, 170), (190, 171, 152), (73, 364, 128), (442, 379, 148)], "#69dbff"),
    (55, "last diamond flare", [(451, 356, 145), (354, 482, 175), (362, 112, 155), (83, 352, 160), (477, 208, 190), (206, 78, 125), (198, 448, 210)], "#ffffff"),
    (58, "straight bow", [(427, 280, 110), (353, 280, 110), (280, 280, 110), (60, 280, 110), (500, 280, 110), (133, 280, 110), (207, 280, 110)], "#ffffff"),
]


GPT55_BURST_RECOMPOSE_SCENES: list[SceneSpec] = [
    (4, 7, "wide_diagonal_reveal", 1, "#4dd7ff"),
    (7, 10, "diamond_expansion", 1, "#fff06e"),
    (10, 13, "offset_crown_bridge", 1, "#ff9f43"),
    (13, 16, "low_double_triangle", 1, "#ff6f91"),
    (16, 19, "vertical_break_line", 1, "#74ff9b"),
    (19, 22, "ribbon_recoil", 1, "#b38bff"),
    (22, 25, "chevron_lock", 1, "#69dbff"),
    (25, 28, "outer_orbit_bridge", 1, "#ffe066"),
    (28, 31, "reverse_half_arc", 1, "#ff8a3d"),
    (31, 34, "tilted_diamond", 1, "#ff5da2"),
    (34, 37, "counter_ribbon", 1, "#8ce99a"),
    (37, 40, "broad_slash", 1, "#66d9ff"),
    (40, 43, "rotated_triangle_burst", 1, "#d191ff"),
    (43, 46, "compressed_orbit", 1, "#c4f052"),
    (46, 49, "falling_chevron", 1, "#ffbe4a"),
    (49, 52, "late_arc_sweep", 1, "#ff728a"),
    (52, 55, "final_recoil_ribbon", 1, "#69dbff"),
    (55, 58, "last_diamond_flare", 1, "#ffffff"),
]


GPT55_BURST_RECOMPOSE_DESIGN_SECTIONS: list[DesignSection] = [
    (
        "diagonal_diamond_crown",
        1,
        13,
        "The fleet opens as a wide diagonal, snaps into a tall diamond, then offsets into a crown bridge with visible role exchange.",
    ),
    (
        "triangle_ribbon_chevron",
        13,
        28,
        "Double-triangle geometry breaks into a vertical line, recoils as a ribbon, locks into a chevron, then bridges through an outer orbit.",
    ),
    (
        "arc_diamond_counterstroke",
        28,
        43,
        "A reverse arc sweep becomes a tilted diamond, then a counter-ribbon and broad slash push the formation across the whole field.",
    ),
    (
        "compression_fall_recompose",
        43,
        60,
        "The closing section compresses, falls through a chevron, sweeps late, recoils once more, flashes into a final diamond, and bows.",
    ),
]


def _rank_order(points: list[Point3]) -> tuple[int, ...]:
    return tuple(sorted(range(len(points)), key=lambda idx: (points[idx][0], points[idx][1])))


def _rank_change(prev_rank: tuple[int, ...], next_rank: tuple[int, ...]) -> int:
    prev_pos = {drone_idx: pos for pos, drone_idx in enumerate(prev_rank)}
    next_pos = {drone_idx: pos for pos, drone_idx in enumerate(next_rank)}
    return sum(abs(prev_pos[drone_idx] - next_pos[drone_idx]) for drone_idx in prev_pos)


def evaluate_timeline_dynamics(timeline: list[TimelineLayer]) -> TimelineDynamicsReport:
    if not timeline:
        return TimelineDynamicsReport(
            layer_count=0,
            transition_count=0,
            changed_rank_layers=0,
            average_rank_change=0.0,
            rank_changes=[],
            drone_spans=[],
        )

    ranks = [_rank_order(points) for _time_sec, _name, points, _color in timeline]
    rank_changes = [_rank_change(prev, nxt) for prev, nxt in zip(ranks, ranks[1:])]
    changed_rank_layers = sum(1 for change in rank_changes if change > 0)
    average_rank_change = sum(rank_changes) / len(rank_changes) if rank_changes else 0.0

    drone_count = len(timeline[0][2])
    drone_spans: list[DroneSpan] = []
    for drone_idx in range(drone_count):
        xs = [points[drone_idx][0] for _time_sec, _name, points, _color in timeline]
        ys = [points[drone_idx][1] for _time_sec, _name, points, _color in timeline]
        drone_spans.append(
            DroneSpan(
                drone_id=drone_idx + 1,
                span_x_cm=max(xs) - min(xs),
                span_y_cm=max(ys) - min(ys),
            )
        )

    return TimelineDynamicsReport(
        layer_count=len(timeline),
        transition_count=max(0, len(timeline) - 1),
        changed_rank_layers=changed_rank_layers,
        average_rank_change=average_rank_change,
        rank_changes=rank_changes,
        drone_spans=drone_spans,
    )


def validate_timeline_dynamics(
    timeline: list[TimelineLayer],
    *,
    min_changed_rank_ratio: float = 0.55,
    min_average_rank_change: float = 5.0,
    min_span_x_cm: int = 240,
    min_span_y_cm: int = 240,
) -> list[str]:
    report = evaluate_timeline_dynamics(timeline)
    errors: list[str] = []
    if report.transition_count <= 0:
        errors.append("timeline has no transitions")
        return errors
    if report.changed_rank_ratio < min_changed_rank_ratio:
        errors.append(
            "fixed-lane degeneration: changed rank layers "
            f"{report.changed_rank_layers}/{report.transition_count}, "
            f"require ratio >= {min_changed_rank_ratio:.2f}"
        )
    if report.average_rank_change < min_average_rank_change:
        errors.append(
            "weak role exchange: average rank change "
            f"{report.average_rank_change:.2f}, require >= {min_average_rank_change:.2f}"
        )
    for span in report.drone_spans:
        if span.span_x_cm < min_span_x_cm:
            errors.append(
                f"d{span.drone_id} insufficient x span: "
                f"{span.span_x_cm}cm < {min_span_x_cm}cm"
            )
        if span.span_y_cm < min_span_y_cm:
            errors.append(
                f"d{span.drone_id} insufficient y span: "
                f"{span.span_y_cm}cm < {min_span_y_cm}cm"
            )
    return errors


def get_gpt55_burst_recompose_seed_info() -> KeyframeSeedInfo:
    return KeyframeSeedInfo(
        seed_id="gpt55_burst_recompose",
        title="GPT-5.5 Burst Recompose 60s",
        timeline=GPT55_BURST_RECOMPOSE_TIMELINE,
        design_sections=GPT55_BURST_RECOMPOSE_DESIGN_SECTIONS,
        scene_specs=GPT55_BURST_RECOMPOSE_SCENES,
        land_time_sec=GPT55_BURST_RECOMPOSE_LAND_TIME_SEC,
        notes=[
            "Fixed 60s F400 choreography seed derived from the accepted GPT-5.5 design and rebuilt as continuous scene motion.",
            "The design is scene-first: each section samples a continuous mathematical path, then solves speed per step.",
            "Lighting uses simulator-supported direct control only: TurnOnAll(hex), TurnOffAll(), and 100ms delays interleaved with motion.",
            "Landing is placed after the 60s performance mark so the final bow can complete before descent.",
        ],
    )


def emit_gpt55_burst_recompose_program(
    output_path: str,
    music_path: str = "",
    render_fps: int = 40,
    timing_fps: int = 120,
) -> str:
    output_path_repr = repr(str(Path(output_path)))
    music_path_repr = repr(str(music_path))
    render_fps = max(10, int(render_fps))
    timing_fps = max(60, int(timing_fps))
    timeline_repr = repr(GPT55_BURST_RECOMPOSE_TIMELINE)
    design_sections_repr = repr(GPT55_BURST_RECOMPOSE_DESIGN_SECTIONS)
    scene_specs_repr = repr(GPT55_BURST_RECOMPOSE_SCENES)
    palette_repr = repr(
        {
            "wide_diagonal_reveal": ["#4dd7ff", "#ffffff", "#69dbff"],
            "diamond_expansion": ["#fff06e", "#ffbe4a", "#ffffff"],
            "offset_crown_bridge": ["#ff9f43", "#fff06e", "#ffffff"],
            "low_double_triangle": ["#ff6f91", "#d191ff", "#ffffff"],
            "vertical_break_line": ["#74ff9b", "#69dbff", "#ffffff"],
            "ribbon_recoil": ["#b38bff", "#ff728a", "#ffffff"],
            "chevron_lock": ["#69dbff", "#74ff9b", "#ffffff"],
            "outer_orbit_bridge": ["#ffe066", "#ffbe4a", "#ffffff"],
            "reverse_half_arc": ["#ff8a3d", "#ff728a", "#ffffff"],
            "tilted_diamond": ["#ff5da2", "#d191ff", "#ffffff"],
            "counter_ribbon": ["#8ce99a", "#63e6be", "#ffffff"],
            "broad_slash": ["#66d9ff", "#4dd7ff", "#ffffff"],
            "rotated_triangle_burst": ["#d191ff", "#ff6f91", "#ffffff"],
            "compressed_orbit": ["#c4f052", "#fff06e", "#ffffff"],
            "falling_chevron": ["#ffbe4a", "#ff728a", "#ffffff"],
            "late_arc_sweep": ["#ff728a", "#ff5da2", "#ffffff"],
            "final_recoil_ribbon": ["#69dbff", "#b38bff", "#ffffff"],
            "last_diamond_flare": ["#ffffff", "#dbeafe", "#fff06e"],
        }
    )

    return f'''import math
import os
import sys
import warnings

sys.path.append(os.getcwd() + r"/src")
sys.path.append(os.getcwd() + r"/src/pyfii")

import pyfii as pf


TIMELINE = {timeline_repr}
DESIGN_SECTIONS = {design_sections_repr}
SCENES = {scene_specs_repr}
LIGHT_PALETTES = {palette_repr}
LAND_TIME_SEC = {GPT55_BURST_RECOMPOSE_LAND_TIME_SEC}
DRONE_COUNT = 7
F400_SAFE_DISTANCE_CM = {F400_SAFE_DISTANCE_CM}
ANCHOR_POINTS_BY_TIME = {{time_sec: points for time_sec, _name, points, _color in TIMELINE}}
SCENE_INDEX_BY_NAME = {{name: idx for idx, (_start, _end, name, _step_count, _color) in enumerate(SCENES)}}


def distance_3d(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def travel_time(distance_cm, speed_cm_s, acc_cm_s2):
    if distance_cm <= 0:
        return 0.0
    cruise_threshold = speed_cm_s * speed_cm_s / acc_cm_s2
    if distance_cm > cruise_threshold:
        return (distance_cm - cruise_threshold) / speed_cm_s + 2 * speed_cm_s / acc_cm_s2
    return 2 * math.sqrt(distance_cm / acc_cm_s2)


def speed_for_segment(distance_cm, duration_sec):
    usable_duration = max(0.35, duration_sec - 0.25)
    for speed in range(20, 201):
        acc = max(50, min(400, speed * 2))
        if travel_time(distance_cm, speed, acc) <= usable_duration:
            return speed, acc
    return 200, 400


def horizontal_distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def min_horizontal_distance(points):
    best = 10**9
    pair = (0, 0)
    for i in range(DRONE_COUNT):
        for j in range(i + 1, DRONE_COUNT):
            dist = horizontal_distance(points[i], points[j])
            if dist < best:
                best = dist
                pair = (i + 1, j + 1)
    return best, pair


def clamp(value, low, high):
    return max(low, min(high, value))


def clamp_channel(value):
    return max(0, min(255, int(round(value))))


def point3(values):
    return (
        int(round(clamp(values[0], 0, 560))),
        int(round(clamp(values[1], 0, 560))),
        int(round(clamp(values[2], 88, 230))),
    )


def smoothstep(t):
    return t * t * (3 - 2 * t)


def mix_point(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def scene_spec(scene_name):
    for start_sec, end_sec, name, step_count, color in SCENES:
        if name == scene_name:
            return start_sec, end_sec, name, step_count, color
    raise ValueError("unknown scene: " + scene_name)


def curve_strength(scene_name):
    if "ribbon" in scene_name or "arc" in scene_name:
        return 30
    if "chevron" in scene_name or "triangle" in scene_name:
        return 22
    if "diamond" in scene_name or "crown" in scene_name:
        return 26
    if "slash" in scene_name or "diagonal" in scene_name:
        return 18
    if "orbit" in scene_name:
        return 32
    return 24


def scene_point_float(scene_name, drone_idx, t):
    start_sec, end_sec, _name, _step_count, _color = scene_spec(scene_name)
    start = ANCHOR_POINTS_BY_TIME[start_sec][drone_idx]
    end = ANCHOR_POINTS_BY_TIME[end_sec][drone_idx]
    ease = smoothstep(t)
    base = mix_point(start, end, ease)
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = max(1.0, math.hypot(dx, dy))
    nx = -dy / length
    ny = dx / length
    scene_idx = SCENE_INDEX_BY_NAME[scene_name]
    phase = 2 * math.pi * drone_idx / DRONE_COUNT + scene_idx * 0.73
    bump = math.sin(math.pi * t)
    strength = curve_strength(scene_name)
    arc = strength * bump * (0.65 + 0.35 * math.sin(phase))
    ripple = strength * 0.35 * bump * math.sin(2 * math.pi * t + phase)
    vertical = strength * 0.42 * bump * math.cos(2 * math.pi * t + phase)
    if "ribbon" in scene_name:
        arc += 16 * bump * math.sin(3 * math.pi * t + phase)
        ripple += 10 * bump * math.cos(math.pi * t + phase)
    elif "chevron" in scene_name:
        vertical += 12 * bump * (1 if drone_idx % 2 == 0 else -1)
    elif "diamond" in scene_name:
        arc *= 1.15
        vertical += 8 * bump * math.sin(phase)
    elif "orbit" in scene_name or "arc" in scene_name:
        arc += 18 * bump * math.cos(math.pi * t + phase)
    elif "slash" in scene_name or "diagonal" in scene_name:
        ripple += 8 * bump * (drone_idx - 3) / 3
    return (
        base[0] + nx * arc + (dx / length) * ripple,
        base[1] + ny * arc + (dy / length) * ripple,
        base[2] + vertical,
    )


def scene_point(scene_name, drone_idx, t):
    return point3(scene_point_float(scene_name, drone_idx, t))


def generate_motion_layers():
    layers = []
    for start_sec, end_sec, scene_name, step_count, color in SCENES:
        duration = end_sec - start_sec
        step_duration = duration / step_count
        for step_idx in range(step_count):
            t = (step_idx + 1) / step_count
            time_sec = start_sec + step_idx * step_duration
            duration_sec = step_duration
            points = [scene_point(scene_name, drone_idx, t) for drone_idx in range(DRONE_COUNT)]
            label = scene_name + " step " + str(step_idx + 1)
            layers.append((time_sec, duration_sec, label, scene_name, points, color))
    return layers


def hex_to_rgb(color):
    color = str(color).lstrip("#")
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))


def rgb_to_hex(rgb):
    return "#" + "".join("%02x" % clamp_channel(c) for c in rgb)


def blend_rgb(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def scale_rgb(rgb, factor):
    return tuple(clamp_channel(c * factor) for c in rgb)


def supported_pulse_color(base_color, scene_name, drone_idx, tick_idx, tick_count):
    base = hex_to_rgb(base_color)
    palette = LIGHT_PALETTES.get(scene_name, [base_color, "#ffffff"])
    accent = hex_to_rgb(palette[(drone_idx + tick_idx // 3) % len(palette)])
    phase = tick_idx / max(1, tick_count) + drone_idx / DRONE_COUNT
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * phase)
    mix = 0.2 + 0.55 * pulse
    gain = 0.50 + 0.50 * pulse
    return rgb_to_hex(scale_rgb(blend_rgb(base, accent, mix), gain))


def apply_scene_lights(d, drone_idx, scene_name, base_color, duration_ms):
    step_ms = 100
    steps = max(1, int(duration_ms // step_ms))
    for step_idx in range(steps):
        if scene_name in ("diagonal", "figure8") and (step_idx + drone_idx) % 10 == 9:
            d.TurnOffAll()
        else:
            d.TurnOnAll(supported_pulse_color(base_color, scene_name, drone_idx, step_idx, steps))
        d.delay(step_ms)
    remain = max(0, int(duration_ms) - steps * step_ms)
    if remain:
        d.delay(remain)


ds = [pf.Drone(0, 0, pf.drone_config_6m, f"192.168.51.{{51 + i}}") for i in range(DRONE_COUNT)]
start_points = TIMELINE[0][2]
for d, point in zip(ds, start_points):
    d.X = d.x = point[0]
    d.Y = d.y = point[1]
    d.takeoff(1, point[2])

previous_points = start_points
for start_sec, end_sec, scene_name, step_count, color in SCENES:
    step_duration = (end_sec - start_sec) / step_count
    duration_ms = int(round(step_duration * 1000))
    next_points = [scene_point(scene_name, drone_idx, 1.0) for drone_idx in range(DRONE_COUNT)]
    for drone_idx, d in enumerate(ds):
        d.inittime(start_sec)
        previous = previous_points[drone_idx]
        for step_idx in range(step_count):
            t = (step_idx + 1) / step_count
            target = scene_point(scene_name, drone_idx, t)
            speed, acc = speed_for_segment(distance_3d(previous, target), step_duration)
            d.VelXY(speed, acc)
            d.VelZ(speed, acc)
            d.move2(*target)
            apply_scene_lights(d, drone_idx, scene_name, color, duration_ms)
            previous = target
    previous_points = next_points

for d in ds:
    d.inittime(LAND_TIME_SEC)
    d.TurnOnAll("#ffffff")
    d.land()
    d.end()

name = {output_path_repr}
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    F = pf.Fii(name, ds, music={music_path_repr})
    F.save()
unsafe = [str(item.message) for item in caught if "distance between" in str(item.message)]
if unsafe:
    raise RuntimeError("unsafe warnings while saving project: " + "; ".join(unsafe[:5]))

data, t0, music, field, device = pf.read_fii(name, fps={timing_fps})
min_dist = 10**9
min_pair = (0, 0)
max_len = max(len(track) for track in data)
for frame_idx in range(max_len):
    frame_points = []
    for track in data:
        item = track[frame_idx] if frame_idx < len(track) else track[-1]
        frame_points.append((float(item[1]), float(item[2]), float(item[3])))
    dist, pair = min_horizontal_distance(frame_points)
    if dist < min_dist:
        min_dist = dist
        min_pair = pair
if min_dist < F400_SAFE_DISTANCE_CM:
    raise RuntimeError(f"readback min distance failed: {{min_dist:.1f}}cm pair={{min_pair}}")

pf.show(data, t0, music, field=field, device=device, save=name, FPS={render_fps}, max_fps={timing_fps})
'''


def write_gpt55_burst_seed_report(output_dir: str | Path, output_path: str, preview_path: str) -> str:
    seed = get_gpt55_burst_recompose_seed_info()
    dynamics = evaluate_timeline_dynamics(seed.timeline)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    layers = "\n".join(f"- {time_sec:02d}s: {name}" for time_sec, name, _, _ in seed.timeline[1:])
    sections = "\n".join(
        f"- {start_sec:02d}-{end_sec:02d}s `{section_id}`: {summary}"
        for section_id, start_sec, end_sec, summary in seed.design_sections
    )
    spans = "\n".join(
        f"- d{item.drone_id}: x span {item.span_x_cm}cm, y span {item.span_y_cm}cm"
        for item in dynamics.drone_spans
    )
    report = f"""# {seed.title}

This seed is now part of the nl_choreo keyframe workflow.

## Design Sections

{sections}

## Structure

{layers}

## Notes

""" + "\n".join(f"- {note}" for note in seed.notes) + f"""

## Dynamics Guard

- Rank-changing transitions: {dynamics.changed_rank_layers}/{dynamics.transition_count}
- Average rank change: {dynamics.average_rank_change:.2f}
- Minimum X/Y span: {dynamics.min_span_x_cm}cm / {dynamics.min_span_y_cm}cm

{spans}

## Artifacts

- Fii project: `{output_path}`
- Preview video: `{preview_path}`
"""
    report_path = out_dir / "design_report.md"
    report_path.write_text(report, encoding="utf-8")
    return str(report_path)
