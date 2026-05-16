import argparse
import math
import sys
import warnings
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / "src"))
sys.path.append(str(REPO_ROOT / "src" / "pyfii"))

import pyfii as pf
from pyfii.extensions.nl_choreo.keyframe_workflow import (
    F400_SAFE_DISTANCE_CM,
    GPT55_BURST_RECOMPOSE_TIMELINE,
)


OUTPUT_DIR = REPO_ROOT / "output" / "gpt55_phrase_vibe_v3_60s"
PROJECT_NAME = "gpt55_phrase_vibe_v3_60s"
PROJECT_PATH = OUTPUT_DIR / PROJECT_NAME
DRONE_COUNT = 7
LAND_TIME_SEC = 64.0
SAFE_DISTANCE_CM = F400_SAFE_DISTANCE_CM
TIMELINE = GPT55_BURST_RECOMPOSE_TIMELINE
ANCHORS = [points for _time_sec, _name, points, _color in TIMELINE]


PHRASE_DURATIONS = [2, 4, 3, 3, 2, 4, 2, 3, 5, 3, 4, 2, 4, 2, 5, 3, 3, 2]
PHRASE_DESIGNS = [
    ("curtain snap into bloom", ["curtain_sweep", "height_ripple"], "wing_delay", "#4dd7ff"),
    ("long crown hinge", ["hinge_turn", "radial_bloom", "late_release"], "outer_inner", "#fff06e"),
    ("low scoop cut", ["low_scoop", "snap_fold"], "counter_pair", "#ff9f43"),
    ("vertical shutter split", ["vertical_shutter", "role_exchange"], "center_echo", "#ff6f91"),
    ("braid recoil", ["counter_braid", "height_ripple"], "chase", "#74ff9b"),
    ("wide sling bridge", ["orbit_sling", "delayed_fold", "late_release"], "outer_inner", "#b38bff"),
    ("hard chevron lock", ["snap_fold", "height_ripple"], "counter_pair", "#69dbff"),
    ("half moon pull", ["half_moon", "compression_release"], "wing_delay", "#ffe066"),
    ("slow tilted bloom", ["radial_bloom", "tilt_shear", "height_ripple"], "center_echo", "#ff8a3d"),
    ("counter ribbon jab", ["counter_braid", "snap_fold"], "chase", "#ff5da2"),
    ("broad slash shear", ["slash_shear", "role_exchange"], "wing_delay", "#8ce99a"),
    ("triangle twist hit", ["triangle_twist", "height_ripple"], "counter_pair", "#66d9ff"),
    ("compression ring breath", ["compression_release", "orbit_sling"], "outer_inner", "#d191ff"),
    ("falling gate accent", ["falling_gate", "snap_fold"], "center_echo", "#c4f052"),
    ("late arc release", ["late_sweep", "delayed_fold", "height_ripple"], "chase", "#ffbe4a"),
    ("final braid recoil", ["counter_braid", "late_release"], "wing_delay", "#ff728a"),
    ("flare lock bloom", ["radial_bloom", "snap_fold", "height_ripple"], "outer_inner", "#69dbff"),
    ("bow aftershock", ["compression_release", "curtain_sweep"], "center_echo", "#ffffff"),
]


def build_phrases():
    phrases = []
    cursor = 4.0
    for idx, duration in enumerate(PHRASE_DURATIONS):
        label, primitives, group_mode, color = PHRASE_DESIGNS[idx]
        start = round(cursor, 2)
        end = round(cursor + duration, 2)
        phrases.append(
            {
                "phrase_id": f"P{idx + 1:02d}",
                "start": start,
                "end": end,
                "start_anchor": idx + 1,
                "end_anchor": idx + 2,
                "label": label,
                "primitives": primitives,
                "group_mode": group_mode,
                "color": color,
            }
        )
        cursor = end
    return phrases


PHRASES = build_phrases()


def clamp(value, low, high):
    return max(low, min(high, value))


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
    usable_duration = max(0.28, duration_sec - 0.06)
    for speed in range(20, 201):
        acc = max(50, min(400, speed * 2))
        if travel_time(distance_cm, speed, acc) <= usable_duration:
            return speed, acc
    return 200, 400


def phrase_group_delay(group_mode, drone_idx):
    if group_mode == "wing_delay":
        return [0.00, 0.08, 0.16, 0.22, 0.16, 0.08, 0.00][drone_idx]
    if group_mode == "outer_inner":
        return 0.00 if drone_idx in (0, 2, 4) else 0.14 if drone_idx in (1, 3, 5) else 0.22
    if group_mode == "counter_pair":
        return 0.00 if drone_idx % 2 == 0 else 0.12
    if group_mode == "center_echo":
        return 0.20 if drone_idx == 6 else 0.04 * (drone_idx % 3)
    if group_mode == "chase":
        return 0.035 * drone_idx
    return 0.0


def local_time_with_group_delay(t, group_mode, drone_idx):
    delay = phrase_group_delay(group_mode, drone_idx)
    if delay <= 0:
        return t
    return clamp((t - delay) / (1 - delay), 0.0, 1.0)


def unit_axes(start, end, base):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = max(1.0, math.hypot(dx, dy))
    ux = dx / length
    uy = dy / length
    nx = -dy / length
    ny = dx / length
    rx = base[0] - 280
    ry = base[1] - 280
    rlen = max(1.0, math.hypot(rx, ry))
    return ux, uy, nx, ny, rx / rlen, ry / rlen


def primitive_offset(name, amp, t, phase, rank, alt):
    bump = math.sin(math.pi * t)
    arc = 0.0
    along = 0.0
    radial = 0.0
    vertical = 0.0
    if name == "curtain_sweep":
        arc = amp * bump * (0.75 + 0.25 * math.sin(phase))
        along = amp * 0.25 * bump * math.sin(2 * math.pi * t + phase)
        vertical = amp * 0.30 * bump * math.cos(math.pi * t + phase)
    elif name == "height_ripple":
        vertical = amp * 0.95 * bump * math.sin(2 * math.pi * t + phase)
        arc = amp * 0.18 * bump * alt
    elif name == "hinge_turn":
        arc = amp * 0.85 * bump * alt
        along = amp * 0.25 * bump * math.sin(math.pi * t + phase)
        vertical = amp * 0.30 * bump * math.sin(phase)
    elif name == "radial_bloom":
        radial = amp * 0.95 * bump * (0.75 + 0.25 * math.sin(phase))
        arc = amp * 0.20 * bump * math.cos(2 * math.pi * t + phase)
    elif name == "late_release":
        release = math.sin(math.pi * t) * smoothstep(clamp((t - 0.45) / 0.55, 0.0, 1.0))
        radial = amp * 0.70 * release
        along = amp * 0.30 * bump * math.cos(math.pi * t + phase)
    elif name == "low_scoop":
        arc = amp * 0.45 * bump * math.sin(phase)
        along = -amp * 0.40 * bump * math.cos(math.pi * t)
        vertical = -amp * 0.75 * bump + amp * 0.20 * bump * alt
    elif name == "snap_fold":
        arc = amp * 0.60 * bump * alt
        along = -amp * 0.45 * bump
        vertical = amp * 0.35 * bump * alt
    elif name == "vertical_shutter":
        arc = amp * 0.18 * bump * alt
        vertical = amp * 0.90 * bump * alt
    elif name == "role_exchange":
        arc = amp * 0.55 * bump * math.sin(2 * math.pi * t + phase)
        along = amp * 0.45 * bump * rank
        vertical = amp * 0.20 * bump * math.cos(phase)
    elif name == "counter_braid":
        arc = amp * 0.85 * bump * math.sin(2 * math.pi * t + phase)
        along = amp * 0.38 * bump * math.cos(3 * math.pi * t + phase)
        vertical = amp * 0.28 * bump * math.cos(2 * math.pi * t + phase)
    elif name == "orbit_sling":
        arc = amp * 0.85 * bump * math.cos(2 * math.pi * t + phase)
        along = amp * 0.55 * bump * math.sin(2 * math.pi * t + phase)
        vertical = amp * 0.24 * bump * math.sin(math.pi * t + phase)
    elif name == "delayed_fold":
        arc = amp * 0.45 * bump * alt
        radial = -amp * 0.55 * bump * smoothstep(1 - t)
        vertical = amp * 0.22 * bump * math.sin(phase)
    elif name == "half_moon":
        arc = amp * bump * (0.80 + 0.20 * math.sin(phase))
        radial = -amp * 0.25 * bump * math.cos(math.pi * t + phase)
        vertical = amp * 0.24 * bump * math.sin(2 * math.pi * t + phase)
    elif name == "compression_release":
        radial = -amp * 0.85 * bump * (0.75 + 0.25 * math.cos(2 * math.pi * t + phase))
        along = amp * 0.26 * bump * math.sin(2 * math.pi * t + phase)
        vertical = amp * 0.24 * bump * math.cos(phase)
    elif name == "tilt_shear":
        arc = amp * 0.45 * bump
        along = amp * 0.50 * bump * rank
        vertical = amp * 0.45 * bump * math.sin(phase)
    elif name == "slash_shear":
        along = amp * 0.85 * bump * rank
        arc = amp * 0.28 * bump * math.sin(phase)
    elif name == "triangle_twist":
        arc = amp * 0.70 * bump * math.cos(2 * math.pi * t + phase)
        radial = amp * 0.48 * bump * math.sin(2 * math.pi * t + phase)
        vertical = amp * 0.40 * bump * alt
    elif name == "falling_gate":
        arc = amp * 0.32 * bump * alt
        vertical = -amp * 0.85 * bump * (0.75 + 0.08 * (rank + 1.0))
    elif name == "late_sweep":
        arc = amp * bump * (0.85 + 0.15 * math.sin(phase))
        along = amp * 0.40 * bump * math.sin(math.pi * t + phase)
        vertical = amp * 0.25 * bump * math.cos(2 * math.pi * t + phase)
    return arc, along, radial, vertical


def phrase_strength(phrase):
    duration = phrase["end"] - phrase["start"]
    strength = clamp(18 + duration * 2.8, 22, 34)
    if phrase["phrase_id"] in {"P10", "P12"}:
        strength *= 0.78
    return strength


def phrase_point_float(phrase, drone_idx, t):
    start = ANCHORS[phrase["start_anchor"]][drone_idx]
    end = ANCHORS[phrase["end_anchor"]][drone_idx]
    local_t = local_time_with_group_delay(t, phrase["group_mode"], drone_idx)
    ease = smoothstep(local_t)
    base = mix_point(start, end, ease)
    ux, uy, nx, ny, rx, ry = unit_axes(start, end, base)
    phrase_idx = int(phrase["phrase_id"][1:]) - 1
    phase = 2 * math.pi * drone_idx / DRONE_COUNT + phrase_idx * 0.61
    rank = (drone_idx - 3) / 3
    alt = 1 if drone_idx % 2 == 0 else -1
    primitives = phrase["primitives"]
    weight = 1 / max(1, len(primitives))
    strength = phrase_strength(phrase)
    arc = 0.0
    along = 0.0
    radial = 0.0
    vertical = 0.0
    for primitive in primitives:
        p_arc, p_along, p_radial, p_vertical = primitive_offset(primitive, strength * weight, local_t, phase, rank, alt)
        arc += p_arc
        along += p_along
        radial += p_radial
        vertical += p_vertical
    return (
        base[0] + nx * arc + ux * along + rx * radial,
        base[1] + ny * arc + uy * along + ry * radial,
        base[2] + vertical,
    )


def phrase_point(phrase, drone_idx, t):
    return point3(phrase_point_float(phrase, drone_idx, t))


def max_travel_time_for_steps(phrase, step_count):
    previous_points = ANCHORS[phrase["start_anchor"]]
    worst_time = 0.0
    for step_idx in range(step_count):
        t = (step_idx + 1) / step_count
        points = [phrase_point(phrase, idx, t) for idx in range(DRONE_COUNT)]
        for idx in range(DRONE_COUNT):
            travel = travel_time(distance_3d(previous_points[idx], points[idx]), 200, 400)
            worst_time = max(worst_time, travel)
        previous_points = points
    return worst_time


def phrase_step_count(phrase):
    duration = phrase["end"] - phrase["start"]
    for step_count in (4, 3, 2, 1):
        step_duration = duration / step_count
        if max_travel_time_for_steps(phrase, step_count) <= step_duration - 0.05:
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


def pulse_color(base_color, drone_idx, tick_idx, tick_count):
    base = hex_to_rgb(base_color)
    warm = (255, 240, 190)
    cool = (110, 220, 255)
    accent = warm if (tick_idx // 3 + drone_idx) % 2 == 0 else cool
    phase = tick_idx / max(1, tick_count) + drone_idx / DRONE_COUNT
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * phase)
    return rgb_to_hex(scale_rgb(blend_rgb(base, accent, 0.20 + 0.35 * pulse), 0.60 + 0.40 * pulse))


def apply_phrase_lights(drone, drone_idx, phrase, duration_ms):
    step_ms = 100
    steps = max(1, int(duration_ms // step_ms))
    for tick_idx in range(steps):
        if (tick_idx + drone_idx) % 17 == 16:
            drone.TurnOffAll()
        else:
            drone.TurnOnAll(pulse_color(phrase["color"], drone_idx, tick_idx, steps))
        drone.delay(step_ms)
    remain = max(0, int(duration_ms) - steps * step_ms)
    if remain:
        drone.delay(remain)


def validate_planned_keypoints():
    best = 10**9
    best_label = ""
    best_pair = (0, 0)
    for phrase in PHRASES:
        samples = max(8, phrase_step_count(phrase) * 4)
        for sample_idx in range(samples + 1):
            t = sample_idx / samples
            points = [phrase_point(phrase, idx, t) for idx in range(DRONE_COUNT)]
            dist, pair = min_horizontal_distance(points)
            if dist < best:
                best = dist
                best_label = f"{phrase['phrase_id']}:{phrase['label']}@{t:.2f}"
                best_pair = pair
    if best < SAFE_DISTANCE_CM:
        raise RuntimeError(f"planned keypoint distance failed: {best:.1f}cm {best_pair} at {best_label}")


def build_drones():
    validate_planned_keypoints()
    ds = [pf.Drone(0, 0, pf.drone_config_6m, f"192.168.51.{51 + i}") for i in range(DRONE_COUNT)]
    start_points = ANCHORS[1]
    for drone, point in zip(ds, start_points):
        drone.X = drone.x = point[0]
        drone.Y = drone.y = point[1]
        drone.takeoff(1, point[2])

    previous_points = start_points
    action_step_count = 0
    used_step_counts = []
    for phrase in PHRASES:
        steps = phrase_step_count(phrase)
        used_step_counts.append((phrase["phrase_id"], steps))
        step_duration = (phrase["end"] - phrase["start"]) / steps
        duration_ms = int(round(step_duration * 1000))
        next_points = [phrase_point(phrase, drone_idx, 1.0) for drone_idx in range(DRONE_COUNT)]
        for drone_idx, drone in enumerate(ds):
            drone.inittime(phrase["start"])
            previous = previous_points[drone_idx]
            for step_idx in range(steps):
                t = (step_idx + 1) / steps
                target = phrase_point(phrase, drone_idx, t)
                speed, acc = speed_for_segment(distance_3d(previous, target), step_duration)
                drone.VelXY(speed, acc)
                drone.VelZ(speed, acc)
                drone.move2(*target)
                apply_phrase_lights(drone, drone_idx, phrase, duration_ms)
                previous = target
                action_step_count += 1
        previous_points = next_points

    for drone in ds:
        drone.inittime(LAND_TIME_SEC)
        drone.TurnOnAll("#ffffff")
        drone.land()
        drone.end()
    return ds, action_step_count // DRONE_COUNT, used_step_counts


def readback_min_distance(data):
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
    return min_dist, min_pair


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--music", default="")
    parser.add_argument("--preview-fps", type=int, default=20)
    parser.add_argument("--timing-fps", type=int, default=120)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ds, action_steps, used_step_counts = build_drones()
    name = str(PROJECT_PATH)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        project = pf.Fii(name, ds, music=args.music)
        project.save()
    save_warnings = [str(item.message) for item in caught]
    unsafe = [msg for msg in save_warnings if "distance between" in msg or "action isn't completed" in msg]
    if unsafe:
        raise RuntimeError("unsafe warnings while saving project: " + "; ".join(unsafe[:5]))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        data, t0, music, field, device = pf.read_fii(name, fps=max(60, args.timing_fps))
    read_warnings = [str(item.message) for item in caught]
    unsafe = [msg for msg in read_warnings if "distance between" in msg or "action isn't completed" in msg]
    if unsafe:
        raise RuntimeError("unsafe warnings while reading project: " + "; ".join(unsafe[:5]))

    min_dist, min_pair = readback_min_distance(data)
    if min_dist < SAFE_DISTANCE_CM:
        raise RuntimeError(f"readback min distance failed: {min_dist:.1f}cm pair={min_pair}")

    pf.show(data, t0, music, field=field, device=device, save=name, FPS=max(10, args.preview_fps), max_fps=max(60, args.timing_fps))
    print("GPT-5.5 phrase-vibe v3 generated")
    print(f"project: {name}")
    print(f"preview: {name}.mp4")
    print(f"duration_sec: {t0 / float(max(60, args.timing_fps)):.2f}")
    print(f"action_steps: {action_steps}")
    print(f"step_counts: {used_step_counts}")
    print(f"readback_min_distance_cm: {min_dist:.1f}, pair={min_pair}")


if __name__ == "__main__":
    main()
