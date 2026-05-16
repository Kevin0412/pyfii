import argparse
import runpy
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / "src"))
sys.path.append(str(REPO_ROOT / "src" / "pyfii"))

from pyfii.extensions.nl_choreo.keyframe_workflow import (
    F400_SAFE_DISTANCE_CM,
    GPT55_BURST_RECOMPOSE_LAND_TIME_SEC,
    GPT55_BURST_RECOMPOSE_SCENES,
    GPT55_BURST_RECOMPOSE_TIMELINE,
)


OUTPUT_DIR = REPO_ROOT / "output" / "gpt55_action_score_v2_60s"
PROJECT_NAME = "gpt55_action_score_v2_60s"
PROJECT_PATH = OUTPUT_DIR / PROJECT_NAME
GENERATED_SCRIPT = OUTPUT_DIR / f"{PROJECT_NAME}_generated.py"


def emit_program(music_path: str, render_fps: int, timing_fps: int) -> str:
    # v2 保留 GPT-5.5 seed 的角色重排关键帧，但把短中距离段拆成动作小节。
    timeline_repr = repr(GPT55_BURST_RECOMPOSE_TIMELINE)
    scenes_repr = repr(GPT55_BURST_RECOMPOSE_SCENES)
    project_repr = repr(str(PROJECT_PATH))
    music_repr = repr(str(music_path))
    return f'''import math
import os
import sys
import warnings

sys.path.append(os.getcwd() + r"/src")
sys.path.append(os.getcwd() + r"/src/pyfii")

import pyfii as pf


TIMELINE = {timeline_repr}
SCENES = {scenes_repr}
LAND_TIME_SEC = {GPT55_BURST_RECOMPOSE_LAND_TIME_SEC}
DRONE_COUNT = 7
SAFE_DISTANCE_CM = {F400_SAFE_DISTANCE_CM}
CURVE_MULTIPLIER = 0.55
ANCHOR_POINTS_BY_TIME = {{time_sec: points for time_sec, _name, points, _color in TIMELINE}}
SCENE_INDEX_BY_NAME = {{name: idx for idx, (_start, _end, name, _step_count, _color) in enumerate(SCENES)}}

LIGHT_PALETTES = {{
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
}}


def clamp(value, low, high):
    return max(low, min(high, value))


def point3(values):
    return (
        int(round(clamp(values[0], 0, 560))),
        int(round(clamp(values[1], 0, 560))),
        int(round(clamp(values[2], 88, 230))),
    )


def distance_3d(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


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


def travel_time(distance_cm, speed_cm_s, acc_cm_s2):
    if distance_cm <= 0:
        return 0.0
    cruise_threshold = speed_cm_s * speed_cm_s / acc_cm_s2
    if distance_cm > cruise_threshold:
        return (distance_cm - cruise_threshold) / speed_cm_s + 2 * speed_cm_s / acc_cm_s2
    return 2 * math.sqrt(distance_cm / acc_cm_s2)


def speed_for_segment(distance_cm, duration_sec):
    # 动作先定，再按该小节时长反推可完成速度。
    usable_duration = max(0.30, duration_sec - 0.05)
    for speed in range(20, 201):
        acc = max(50, min(400, speed * 2))
        if travel_time(distance_cm, speed, acc) <= usable_duration:
            return speed, acc
    return 200, 400


def smoothstep(t):
    return t * t * (3 - 2 * t)


def mix_point(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def scene_spec(scene_name):
    for start_sec, end_sec, name, _step_count, color in SCENES:
        if name == scene_name:
            return start_sec, end_sec, name, color
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
    start_sec, end_sec, _name, _color = scene_spec(scene_name)
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
    strength = curve_strength(scene_name) * CURVE_MULTIPLIER
    arc = strength * bump * (0.65 + 0.35 * math.sin(phase))
    ripple = strength * 0.35 * bump * math.sin(2 * math.pi * t + phase)
    vertical = strength * 0.42 * bump * math.cos(2 * math.pi * t + phase)
    if "ribbon" in scene_name:
        arc += 16 * CURVE_MULTIPLIER * bump * math.sin(3 * math.pi * t + phase)
        ripple += 10 * CURVE_MULTIPLIER * bump * math.cos(math.pi * t + phase)
    elif "chevron" in scene_name:
        vertical += 12 * CURVE_MULTIPLIER * bump * (1 if drone_idx % 2 == 0 else -1)
    elif "diamond" in scene_name:
        arc *= 1.15
        vertical += 8 * CURVE_MULTIPLIER * bump * math.sin(phase)
    elif "orbit" in scene_name or "arc" in scene_name:
        arc += 18 * CURVE_MULTIPLIER * bump * math.cos(math.pi * t + phase)
    elif "slash" in scene_name or "diagonal" in scene_name:
        ripple += 8 * CURVE_MULTIPLIER * bump * (drone_idx - 3) / 3
    return (
        base[0] + nx * arc + (dx / length) * ripple,
        base[1] + ny * arc + (dy / length) * ripple,
        base[2] + vertical,
    )


def scene_point(scene_name, drone_idx, t):
    return point3(scene_point_float(scene_name, drone_idx, t))


def max_travel_time_for_steps(scene_name, start_sec, step_count):
    previous_points = ANCHOR_POINTS_BY_TIME[start_sec]
    worst_time = 0.0
    for step_idx in range(step_count):
        t = (step_idx + 1) / step_count
        points = [scene_point(scene_name, idx, t) for idx in range(DRONE_COUNT)]
        for idx in range(DRONE_COUNT):
            travel = travel_time(distance_3d(previous_points[idx], points[idx]), 200, 400)
            worst_time = max(worst_time, travel)
        previous_points = points
    return worst_time


def scene_step_count(start_sec, end_sec, scene_name):
    # 候选小节必须在最大速度下按时完成；否则降级为更少小节。
    for step_count in (3, 2, 1):
        step_duration = (end_sec - start_sec) / step_count
        if max_travel_time_for_steps(scene_name, start_sec, step_count) <= step_duration - 0.05:
            return step_count
    return 1


def hex_to_rgb(color):
    color = str(color).lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def rgb_to_hex(rgb):
    return "#" + "".join("%02x" % int(round(clamp(channel, 0, 255))) for channel in rgb)


def blend_rgb(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def scale_rgb(rgb, factor):
    return tuple(clamp(channel * factor, 0, 255) for channel in rgb)


def supported_pulse_color(base_color, scene_name, drone_idx, tick_idx, tick_count):
    base = hex_to_rgb(base_color)
    palette = LIGHT_PALETTES.get(scene_name, [base_color, "#ffffff"])
    accent = hex_to_rgb(palette[(drone_idx + tick_idx // 2) % len(palette)])
    phase = tick_idx / max(1, tick_count) + drone_idx / DRONE_COUNT
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * phase)
    mix = 0.25 + 0.50 * pulse
    gain = 0.52 + 0.48 * pulse
    return rgb_to_hex(scale_rgb(blend_rgb(base, accent, mix), gain))


def apply_scene_lights(drone, drone_idx, scene_name, base_color, duration_ms):
    step_ms = 100
    steps = max(1, int(duration_ms // step_ms))
    for tick_idx in range(steps):
        if (tick_idx + drone_idx) % 13 == 12:
            drone.TurnOffAll()
        else:
            drone.TurnOnAll(supported_pulse_color(base_color, scene_name, drone_idx, tick_idx, steps))
        drone.delay(step_ms)
    remain = max(0, int(duration_ms) - steps * step_ms)
    if remain:
        drone.delay(remain)


def validate_planned_keypoints():
    points_by_scene = []
    for start_sec, end_sec, scene_name, _old_step_count, color in SCENES:
        steps = scene_step_count(start_sec, end_sec, scene_name)
        for step_idx in range(steps):
            t = (step_idx + 1) / steps
            points_by_scene.append((scene_name, t, [scene_point(scene_name, idx, t) for idx in range(DRONE_COUNT)]))
    best = 10**9
    best_label = ""
    best_pair = (0, 0)
    for scene_name, t, points in points_by_scene:
        dist, pair = min_horizontal_distance(points)
        if dist < best:
            best = dist
            best_label = f"{{scene_name}}@{{t:.2f}}"
            best_pair = pair
    if best < SAFE_DISTANCE_CM:
        raise RuntimeError(f"planned keypoint distance failed: {{best:.1f}}cm {{best_pair}} at {{best_label}}")


validate_planned_keypoints()

ds = [pf.Drone(0, 0, pf.drone_config_6m, f"192.168.51.{{51 + i}}") for i in range(DRONE_COUNT)]
start_points = TIMELINE[0][2]
for drone, point in zip(ds, start_points):
    drone.X = drone.x = point[0]
    drone.Y = drone.y = point[1]
    drone.takeoff(1, point[2])

previous_points = start_points
action_step_count = 0
for start_sec, end_sec, scene_name, _old_step_count, color in SCENES:
    steps = scene_step_count(start_sec, end_sec, scene_name)
    step_duration = (end_sec - start_sec) / steps
    duration_ms = int(round(step_duration * 1000))
    next_points = [scene_point(scene_name, drone_idx, 1.0) for drone_idx in range(DRONE_COUNT)]
    for drone_idx, drone in enumerate(ds):
        drone.inittime(start_sec)
        previous = previous_points[drone_idx]
        for step_idx in range(steps):
            t = (step_idx + 1) / steps
            target = scene_point(scene_name, drone_idx, t)
            speed, acc = speed_for_segment(distance_3d(previous, target), step_duration)
            drone.VelXY(speed, acc)
            drone.VelZ(speed, acc)
            drone.move2(*target)
            apply_scene_lights(drone, drone_idx, scene_name, color, duration_ms)
            previous = target
            action_step_count += 1
    previous_points = next_points

for drone in ds:
    drone.inittime(LAND_TIME_SEC)
    drone.TurnOnAll("#ffffff")
    drone.land()
    drone.end()

name = {project_repr}
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    project = pf.Fii(name, ds, music={music_repr})
    project.save()
save_warnings = [str(item.message) for item in caught]
unsafe = [msg for msg in save_warnings if "distance between" in msg or "action isn't completed" in msg]
if unsafe:
    raise RuntimeError("unsafe warnings while saving project: " + "; ".join(unsafe[:5]))

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    data, t0, music, field, device = pf.read_fii(name, fps={int(timing_fps)})
read_warnings = [str(item.message) for item in caught]
unsafe = [msg for msg in read_warnings if "distance between" in msg or "action isn't completed" in msg]
if unsafe:
    raise RuntimeError("unsafe warnings while reading project: " + "; ".join(unsafe[:5]))
duration_sec = t0 / float({int(timing_fps)})
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
if min_dist < SAFE_DISTANCE_CM:
    raise RuntimeError(f"readback min distance failed: {{min_dist:.1f}}cm pair={{min_pair}}")

pf.show(data, t0, music, field=field, device=device, save=name, FPS={int(render_fps)}, max_fps={int(timing_fps)})
print("GPT-5.5 action-score v2 generated")
print(f"project: {{name}}")
print(f"preview: {{name}}.mp4")
print(f"duration_sec: {{duration_sec:.2f}}")
print(f"action_steps: {{action_step_count // DRONE_COUNT}}")
print(f"readback_min_distance_cm: {{min_dist:.1f}}, pair={{min_pair}}")
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--music", default="")
    parser.add_argument("--preview-fps", type=int, default=30)
    parser.add_argument("--timing-fps", type=int, default=120)
    parser.add_argument("--write-only", action="store_true")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_SCRIPT.write_text(
        emit_program(
            music_path=args.music,
            render_fps=max(10, args.preview_fps),
            timing_fps=max(60, args.timing_fps),
        ),
        encoding="utf-8",
    )
    if not args.write_only:
        runpy.run_path(str(GENERATED_SCRIPT), run_name="__main__")

    print("GPT-5.5 action-score v2 script ready")
    print(f"generated script: {GENERATED_SCRIPT}")
    print(f"project: {PROJECT_PATH}")
    print(f"preview: {PROJECT_PATH}.mp4")


if __name__ == "__main__":
    main()
