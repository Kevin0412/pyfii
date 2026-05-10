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


GPT55_BURST_RECOMPOSE_TIMELINE: list[TimelineLayer] = [
    (1, "takeoff ellipse", [(458, 293, 158), (391, 402, 206), (240, 428, 218), (119, 353, 185), (119, 233, 131), (240, 158, 98), (391, 185, 110)], "#4dd7ff"),
    (10, "opening expansion end", [(262, 427, 200), (176, 287, 148), (203, 167, 104), (322, 157, 101), (444, 266, 140), (477, 411, 193), (396, 483, 220)], "#4dd7ff"),
    (18, "lissajous weave end", [(163, 291, 105), (142, 196, 140), (245, 161, 189), (395, 213, 214), (478, 311, 197), (433, 383, 150), (293, 374, 109)], "#fff06e"),
    (28, "diagonal shear end", [(239, 113, 183), (363, 149, 138), (412, 263, 107), (351, 368, 115), (225, 386, 155), (128, 303, 197), (135, 182, 210)], "#ff6f91"),
    (38, "figure eight pulse end", [(307, 180, 156), (367, 244, 191), (348, 358, 200), (264, 436, 178), (178, 419, 141), (155, 320, 116), (212, 214, 123)], "#74ff9b"),
    (50, "vertical rotation end", [(225, 398, 132), (113, 315, 128), (127, 196, 147), (256, 130, 174), (403, 167, 189), (458, 279, 181), (378, 382, 156)], "#b38bff"),
    (58, "staggered bow", [(207, 280, 110), (60, 280, 110), (133, 280, 110), (280, 280, 110), (427, 280, 110), (500, 280, 110), (353, 280, 110)], "#ffffff"),
]


GPT55_BURST_RECOMPOSE_SCENES: list[SceneSpec] = [
    (4, 10, "opening", 3, "#4dd7ff"),
    (10, 18, "lissajous", 4, "#fff06e"),
    (18, 28, "diagonal", 5, "#ff6f91"),
    (28, 38, "figure8", 5, "#74ff9b"),
    (38, 50, "vertical", 6, "#b38bff"),
    (50, 58, "final", 4, "#ffffff"),
]


GPT55_BURST_RECOMPOSE_DESIGN_SECTIONS: list[DesignSection] = [
    (
        "expanding_rotated_ellipse",
        1,
        10,
        "The fleet takes off already separated on an ellipse, then expands and rotates with small center drift instead of jumping between fixed poses.",
    ),
    (
        "lissajous_and_diagonal_shear",
        10,
        28,
        "The phase order stays safe while the visual frame becomes a wave, then shears into a diagonal slash with changing height.",
    ),
    (
        "figure8_and_vertical_rotation",
        28,
        50,
        "The center of the whole formation traces a figure-eight pulse, then the ellipse turns into a 3D vertical rotation with strong height contrast.",
    ),
    (
        "ordered_bow_recompose",
        50,
        60,
        "The final section preserves the sorted visual order from the 3D rotation and recomposes into a low bow without crossing paths.",
    ),
]


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
    bow_map_repr = repr({1: 60, 2: 133, 0: 207, 3: 280, 6: 353, 4: 427, 5: 500})
    palette_repr = repr(
        {
            "opening": ["#4dd7ff", "#ffffff", "#69dbff"],
            "lissajous": ["#fff06e", "#ffbe4a", "#ffffff"],
            "diagonal": ["#ff6f91", "#d191ff", "#ffffff"],
            "figure8": ["#74ff9b", "#69dbff", "#ffffff"],
            "vertical": ["#b38bff", "#ff728a", "#ffffff"],
            "final": ["#ffffff", "#dbeafe", "#fff06e"],
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
BOW_X_BY_DRONE = {bow_map_repr}
LIGHT_PALETTES = {palette_repr}
LAND_TIME_SEC = {GPT55_BURST_RECOMPOSE_LAND_TIME_SEC}
DRONE_COUNT = 7
F400_SAFE_DISTANCE_CM = {F400_SAFE_DISTANCE_CM}


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
        int(round(clamp(values[0], 50, 510))),
        int(round(clamp(values[1], 50, 510))),
        int(round(clamp(values[2], 88, 230))),
    )


def smoothstep(t):
    return t * t * (3 - 2 * t)


def mix_point(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def ellipse_point(drone_idx, rotation, cx, cy, rx, ry, angle, z_base, z_amp, z_phase):
    theta = 2 * math.pi * drone_idx / DRONE_COUNT + rotation
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    x = cx + rx * cos_t * cos_a - ry * sin_t * sin_a
    y = cy + rx * cos_t * sin_a + ry * sin_t * cos_a
    z = z_base + z_amp * math.sin(theta + z_phase)
    return (x, y, z)


def scene_time(scene_name, t):
    for start_sec, end_sec, name, _step_count, _color in SCENES:
        if name == scene_name:
            return start_sec + (end_sec - start_sec) * t
    raise ValueError("unknown scene: " + scene_name)


def orbit_point_float(drone_idx, time_sec):
    u = (time_sec - 4) / 46
    base = 2 * math.pi * drone_idx / DRONE_COUNT
    rotation = 2.6 * math.pi * u + 0.25 * math.sin(4 * math.pi * u)
    cx = 280 + 42 * math.sin(2 * math.pi * u) + 24 * math.sin(6 * math.pi * u)
    cy = 280 + 34 * math.sin(3 * math.pi * u + 0.4)
    rx = 165 + 28 * math.sin(2 * math.pi * u + 0.5)
    ry = 118 + 22 * math.sin(4 * math.pi * u + 1.2)
    angle = 0.8 * math.sin(2 * math.pi * u) + 0.35 * math.sin(5 * math.pi * u)
    x, y, z = ellipse_point(
        drone_idx,
        rotation,
        cx,
        cy,
        rx,
        ry,
        angle,
        158,
        44,
        2.6 * math.pi * u,
    )
    z += 18 * math.sin(6 * math.pi * u + base)
    return (x, y, z)


def scene_point_float(scene_name, drone_idx, t):
    if scene_name == "final":
        start = orbit_point_float(drone_idx, 50)
        bow = (BOW_X_BY_DRONE[drone_idx], 280, 110)
        ease = smoothstep(t)
        phase = 2 * math.pi * drone_idx / DRONE_COUNT
        wobble = (
            (1 - ease) * 20 * math.sin(2 * math.pi * t + phase),
            (1 - ease) * 16 * math.cos(2 * math.pi * t + phase),
            (1 - ease) * 12 * math.sin(4 * math.pi * t + phase),
        )
        blended = mix_point(start, bow, ease)
        return tuple(blended[i] + wobble[i] for i in range(3))
    return orbit_point_float(drone_idx, scene_time(scene_name, t))


def scene_point(scene_name, drone_idx, t):
    return point3(scene_point_float(scene_name, drone_idx, t))


def generate_motion_layers():
    layers = []
    for start_sec, end_sec, scene_name, step_count, color in SCENES:
        duration = end_sec - start_sec
        step_duration = duration / step_count
        for step_idx in range(step_count):
            t = (step_idx + 1) / step_count
            time_sec = int(round(start_sec + step_idx * step_duration))
            duration_sec = int(round(step_duration))
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
for time_sec, duration, label, scene_name, points, color in generate_motion_layers():
    duration_ms = int(duration * 1000)
    for drone_idx, (d, previous, target) in enumerate(zip(ds, previous_points, points)):
        speed, acc = speed_for_segment(distance_3d(previous, target), duration)
        d.inittime(time_sec)
        d.VelXY(speed, acc)
        d.VelZ(speed, acc)
        d.move2(*target)
        apply_scene_lights(d, drone_idx, scene_name, color, duration_ms)
    previous_points = points

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
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    layers = "\n".join(f"- {time_sec:02d}s: {name}" for time_sec, name, _, _ in seed.timeline[1:])
    sections = "\n".join(
        f"- {start_sec:02d}-{end_sec:02d}s `{section_id}`: {summary}"
        for section_id, start_sec, end_sec, summary in seed.design_sections
    )
    report = f"""# {seed.title}

This seed is now part of the nl_choreo keyframe workflow.

## Design Sections

{sections}

## Structure

{layers}

## Notes

""" + "\n".join(f"- {note}" for note in seed.notes) + f"""

## Artifacts

- Fii project: `{output_path}`
- Preview video: `{preview_path}`
"""
    report_path = out_dir / "design_report.md"
    report_path.write_text(report, encoding="utf-8")
    return str(report_path)
