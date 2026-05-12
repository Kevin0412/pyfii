import argparse
import itertools
import math
import sys
import warnings
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / "src"))
sys.path.append(str(REPO_ROOT / "src" / "pyfii"))

import pyfii as pf
from pyfii.extensions.nl_choreo.keyframe_workflow import F400_SAFE_DISTANCE_CM


OUTPUT_DIR = REPO_ROOT / "output" / "original_flow_field_v5_70s"
PROJECT_NAME = "original_flow_field_v5_70s"
PROJECT_PATH = OUTPUT_DIR / PROJECT_NAME
DRONE_COUNT = 7
DESIGN_MIN_DISTANCE_CM = max(F400_SAFE_DISTANCE_CM, 62)
LAND_TIME_SEC = 70


FLOW_STATES = [
    (4, "seed slash", 278, 282, 170, 0.78, -0.55, 4.05, 0.10, 36, "#48dbfb"),
    (9, "left opening curl", 235, 305, 222, 0.90, 0.15, 4.85, 0.85, 48, "#ffdd59"),
    (13, "thin rising blade", 304, 252, 236, 0.72, 0.92, 3.95, 1.55, 54, "#ff6b9a"),
    (20, "wide counter halo", 286, 286, 244, 1.00, 1.95, 5.75, 2.35, 42, "#7bed9f"),
    (24, "right hook dive", 326, 286, 212, 0.82, 2.82, 4.40, 3.05, 36, "#70a1ff"),
    (31, "low river sweep", 248, 250, 230, 0.74, 3.55, 4.95, 3.82, 28, "#feca57"),
    (35, "center inhale", 280, 280, 150, 1.08, 4.20, 4.20, 4.45, 40, "#a29bfe"),
    (43, "asymmetric bloom", 292, 302, 246, 0.94, 5.20, 5.60, 5.25, 52, "#fd79a8"),
    (48, "diagonal shutter", 255, 278, 218, 0.70, 6.18, 3.90, 5.85, 45, "#81ecec"),
    (56, "slow outer breath", 282, 330, 218, 0.90, 7.05, 5.55, 6.65, 50, "#ffeaa7"),
    (60, "snap knot", 280, 280, 170, 1.02, 7.78, 4.35, 7.15, 38, "#55efc4"),
    (66, "final drifting arc", 302, 270, 220, 0.76, 8.65, 4.70, 7.90, 26, "#ffffff"),
]


def clamp(value, low, high):
    return max(low, min(high, value))


def point3(values):
    limits = ((40, 520), (40, 520), (92, 225))
    return tuple(int(round(clamp(values[idx], *limits[idx]))) for idx in range(3))


def state_points(state):
    _, _, cx, cy, radius, y_scale, rotation, span, phase, height_amp, _ = state
    points = []
    for idx in range(DRONE_COUNT):
        u = idx / (DRONE_COUNT - 1)
        theta = rotation - 0.5 * span + span * u
        theta += 0.075 * math.sin(phase + idx * 1.41)
        local_radius = radius * (1.0 + 0.07 * math.sin(phase * 0.7 + idx * 1.73))
        x0 = local_radius * math.cos(theta)
        y0 = y_scale * local_radius * math.sin(theta)
        y0 += 0.10 * math.sin(phase + rotation) * x0
        x = cx + x0 * math.cos(rotation) - y0 * math.sin(rotation)
        y = cy + x0 * math.sin(rotation) + y0 * math.cos(rotation)
        z = 154 + height_amp * math.sin(theta * 1.18 + phase * 0.45)
        z += 10 * math.cos(idx * 1.9 + rotation)
        points.append(point3((x, y, z)))
    return points


def horizontal_distance(a, b):
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


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
    usable_duration = max(0.35, duration_sec - 0.12)
    for speed in range(120, 201):
        acc = max(50, min(400, speed * 2))
        if travel_time(distance_cm, speed, acc) <= usable_duration:
            return speed, acc
    return 200, 400


def interpolated_min_distance(previous_points, target_points, samples=80):
    best = 10**9
    best_pair = (0, 0)
    best_t = 0.0
    for step in range(samples + 1):
        t = step / samples
        frame_points = []
        for idx in range(DRONE_COUNT):
            frame_points.append(
                tuple(previous_points[idx][axis] * (1 - t) + target_points[idx][axis] * t for axis in range(3))
            )
        dist, pair = min_horizontal_distance(frame_points)
        if dist < best:
            best = dist
            best_pair = pair
            best_t = t
    return best, best_pair, best_t


def choose_transition_targets(previous_points, raw_target_points):
    best_score = (-1.0, -10**9)
    best_points = None
    best_meta = None
    for perm in itertools.permutations(range(DRONE_COUNT)):
        target_points = [raw_target_points[idx] for idx in perm]
        min_dist, pair, t = interpolated_min_distance(previous_points, target_points)
        travel = sum(math.dist(previous_points[idx], target_points[idx]) for idx in range(DRONE_COUNT))
        score = (min_dist, -travel)
        if score > best_score:
            best_score = score
            best_points = target_points
            best_meta = (perm, min_dist, pair, t, travel)
    return best_points, best_meta


def validate_and_plan_states():
    planned = [state_points(FLOW_STATES[0])]
    transition_meta = []

    static_best = 10**9
    static_label = ""
    static_pair = (0, 0)
    for state in FLOW_STATES:
        points = state_points(state)
        dist, pair = min_horizontal_distance(points)
        if dist < static_best:
            static_best = dist
            static_pair = pair
            static_label = state[1]

    if static_best < DESIGN_MIN_DISTANCE_CM:
        raise RuntimeError(f"static state distance failed: {static_best:.1f}cm pair={static_pair} at {static_label}")

    previous_points = planned[0]
    for state in FLOW_STATES[1:]:
        target_points, meta = choose_transition_targets(previous_points, state_points(state))
        _, min_dist, pair, t, _ = meta
        if min_dist < DESIGN_MIN_DISTANCE_CM:
            raise RuntimeError(
                f"transition distance failed: {min_dist:.1f}cm pair={pair} t={t:.2f} into {state[1]}"
            )
        planned.append(target_points)
        transition_meta.append((state[1], meta))
        previous_points = target_points

    return planned, transition_meta, static_best


def hex_to_rgb(color):
    color = str(color).lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def rgb_to_hex(rgb):
    return "#" + "".join("%02x" % int(round(clamp(channel, 0, 255))) for channel in rgb)


def blend_rgb(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def pulse_color(base_color, drone_idx, tick_idx, tick_count):
    base = hex_to_rgb(base_color)
    accent = (255, 255, 255) if (tick_idx + drone_idx) % 4 == 0 else (90, 220, 255)
    phase = tick_idx / max(1, tick_count) + drone_idx / DRONE_COUNT
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * phase)
    mixed = blend_rgb(base, accent, 0.15 + 0.34 * pulse)
    return rgb_to_hex(tuple(clamp(channel * (0.62 + 0.38 * pulse), 0, 255) for channel in mixed))


def apply_state_lights(drone, drone_idx, color, duration_ms):
    if duration_ms <= 0:
        drone.TurnOnAll(color)
        return
    step_ms = 100
    steps = max(1, int(duration_ms // step_ms))
    for tick_idx in range(steps):
        if (tick_idx + 3 * drone_idx) % 29 == 28:
            drone.TurnOffAll()
        else:
            drone.TurnOnAll(pulse_color(color, drone_idx, tick_idx, steps))
        drone.delay(step_ms)
    remain = max(0, int(duration_ms) - steps * step_ms)
    if remain:
        drone.delay(remain)


def build_drones():
    planned_states, transition_meta, static_best = validate_and_plan_states()
    ds = [pf.Drone(0, 0, pf.drone_config_6m, f"192.168.51.{51 + i}") for i in range(DRONE_COUNT)]
    start_points = planned_states[0]
    for drone, point in zip(ds, start_points):
        drone.X = drone.x = point[0]
        drone.Y = drone.y = point[1]
        drone.takeoff(1, point[2])

    action_steps = 0
    previous_points = start_points
    for idx, state in enumerate(FLOW_STATES[1:], start=1):
        previous_state = FLOW_STATES[idx - 1]
        target_points = planned_states[idx]
        duration = state[0] - previous_state[0]
        for drone_idx, drone in enumerate(ds):
            distance = math.dist(previous_points[drone_idx], target_points[drone_idx])
            speed, acc = speed_for_segment(distance, duration)
            drone.inittime(state[0])
            drone.VelXY(speed, acc)
            drone.VelZ(speed, acc)
            drone.move2(*target_points[drone_idx])
            apply_state_lights(drone, drone_idx, state[10], 0)
            action_steps += 1
        previous_points = target_points

    for drone in ds:
        drone.inittime(LAND_TIME_SEC)
        drone.TurnOnAll("#ffffff")
        drone.land()
        drone.end()
    return ds, action_steps // DRONE_COUNT, transition_meta, static_best


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
    ds, action_steps, transition_meta, static_best = build_drones()
    name = str(PROJECT_PATH)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        project = pf.Fii(name, ds, music=args.music)
        project.save()
    save_warnings = [str(item.message) for item in caught]
    unsafe = [msg for msg in save_warnings if "distance between" in msg or "action isn't completed" in msg]
    if unsafe:
        raise RuntimeError("unsafe warnings while saving project: " + "; ".join(unsafe[:5]))

    timing_fps = max(60, args.timing_fps)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        data, t0, music, field, device = pf.read_fii(name, fps=timing_fps)
    read_warnings = [str(item.message) for item in caught]
    unsafe = [msg for msg in read_warnings if "distance between" in msg or "action isn't completed" in msg]
    if unsafe:
        raise RuntimeError("unsafe warnings while reading project: " + "; ".join(unsafe[:5]))

    min_dist, min_pair = readback_min_distance(data)
    if min_dist < DESIGN_MIN_DISTANCE_CM:
        raise RuntimeError(f"readback min distance failed: {min_dist:.1f}cm pair={min_pair}")

    pf.show(data, t0, music, field=field, device=device, save=name, FPS=max(10, args.preview_fps), max_fps=timing_fps)
    print("Original flow-field v5 generated")
    print(f"project: {name}")
    print(f"preview: {name}.mp4")
    print(f"duration_sec: {t0 / float(timing_fps):.2f}")
    print(f"action_steps: {action_steps}")
    print(f"static_min_distance_cm: {static_best:.1f}")
    print(f"readback_min_distance_cm: {min_dist:.1f}, pair={min_pair}")
    print("transition_min_distance_cm:")
    for label, meta in transition_meta:
        _, dist, pair, t, _ = meta
        print(f"  {label}: {dist:.1f}, pair={pair}, t={t:.2f}")


if __name__ == "__main__":
    main()
