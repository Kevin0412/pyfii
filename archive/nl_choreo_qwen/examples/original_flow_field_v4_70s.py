import argparse
import math
import warnings
from pathlib import Path

import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / "src"))
sys.path.append(str(REPO_ROOT / "src" / "pyfii"))

import pyfii as pf
from pyfii.extensions.nl_choreo.keyframe_workflow import F400_SAFE_DISTANCE_CM


OUTPUT_DIR = REPO_ROOT / "output" / "original_flow_field_v4_70s"
PROJECT_NAME = "original_flow_field_v4_70s"
PROJECT_PATH = OUTPUT_DIR / PROJECT_NAME
DRONE_COUNT = 7
SAFE_DISTANCE_CM = F400_SAFE_DISTANCE_CM
LAND_TIME_SEC = 66


FLOW_STATES = [
    (4, "tight skew wake", 280, 280, 118, 0.72, 0.10, 20, "#48dbfb"),
    (7, "wide left peel", 250, 300, 210, 0.58, 0.62, 34, "#ffdd59"),
    (11, "tall shutter", 285, 275, 150, 1.50, 1.05, 42, "#ff9f43"),
    (14, "right scoop", 315, 260, 205, 0.78, 1.72, 28, "#ff6b9a"),
    (19, "slow high bloom", 280, 285, 232, 1.05, 2.40, 46, "#7bed9f"),
    (22, "hard compression", 280, 280, 105, 0.92, 3.20, 34, "#a29bfe"),
    (27, "reverse field sweep", 300, 300, 226, 0.70, 4.05, 38, "#70a1ff"),
    (31, "low traveling wave", 270, 250, 176, 0.50, 4.90, 26, "#feca57"),
    (36, "vertical breathing loop", 280, 286, 188, 1.34, 5.70, 44, "#ff6b81"),
    (39, "center snap", 280, 280, 112, 0.88, 6.45, 32, "#55efc4"),
    (44, "offcenter flare", 245, 298, 224, 1.02, 7.18, 40, "#74b9ff"),
    (48, "tilted blade field", 310, 275, 196, 0.62, 7.92, 30, "#fd79a8"),
    (53, "largest halo", 280, 280, 238, 0.88, 8.70, 48, "#ffeaa7"),
    (57, "narrow aftershock", 280, 292, 126, 0.56, 9.45, 28, "#81ecec"),
    (61, "low final breath", 280, 280, 190, 0.36, 10.25, 18, "#ffffff"),
]


def clamp(value, low, high):
    return max(low, min(high, value))


def point3(values):
    return (
        int(round(clamp(values[0], 40, 520))),
        int(round(clamp(values[1], 40, 520))),
        int(round(clamp(values[2], 88, 230))),
    )


def state_points(state):
    time_sec, name, cx, cy, radius, y_scale, rotation, height_amp, color = state
    points = []
    for idx in range(DRONE_COUNT):
        base = 2 * math.pi * idx / DRONE_COUNT
        theta = base + rotation + 0.18 * math.sin(rotation * 0.7 + idx * 1.31)
        local_radius = radius * (0.90 + 0.10 * math.sin(rotation + idx * 1.73))
        x = cx + local_radius * math.cos(theta)
        y = cy + y_scale * local_radius * math.sin(theta)
        z = 150 + height_amp * math.sin(theta * 1.55 + rotation * 0.4) + 11 * math.cos(idx * 1.17 + rotation)
        points.append(point3((x, y, z)))
    return points


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
    usable_duration = max(0.35, duration_sec - 0.08)
    for speed in range(20, 201):
        acc = max(50, min(400, speed * 2))
        if travel_time(distance_cm, speed, acc) <= usable_duration:
            return speed, acc
    return 200, 400


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
    accent = (255, 255, 255) if (tick_idx + drone_idx) % 5 == 0 else (120, 230, 255)
    phase = tick_idx / max(1, tick_count) + drone_idx / DRONE_COUNT
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * phase)
    return rgb_to_hex(scale_rgb(blend_rgb(base, accent, 0.18 + 0.36 * pulse), 0.60 + 0.40 * pulse))


def apply_state_lights(drone, drone_idx, color, duration_ms):
    if duration_ms <= 0:
        drone.TurnOnAll(color)
        return
    step_ms = 100
    steps = max(1, int(duration_ms // step_ms))
    for tick_idx in range(steps):
        if (tick_idx + 2 * drone_idx) % 23 == 22:
            drone.TurnOffAll()
        else:
            drone.TurnOnAll(pulse_color(color, drone_idx, tick_idx, steps))
        drone.delay(step_ms)
    remain = max(0, int(duration_ms) - steps * step_ms)
    if remain:
        drone.delay(remain)


def validate_planned_states():
    best = 10**9
    best_label = ""
    best_pair = (0, 0)
    for state in FLOW_STATES:
        points = state_points(state)
        dist, pair = min_horizontal_distance(points)
        if dist < best:
            best = dist
            best_pair = pair
            best_label = state[1]
    if best < SAFE_DISTANCE_CM:
        raise RuntimeError(f"state distance failed: {best:.1f}cm pair={best_pair} at {best_label}")


def build_drones():
    validate_planned_states()
    ds = [pf.Drone(0, 0, pf.drone_config_6m, f"192.168.51.{51 + i}") for i in range(DRONE_COUNT)]
    start_points = state_points(FLOW_STATES[0])
    for drone, point in zip(ds, start_points):
        drone.X = drone.x = point[0]
        drone.Y = drone.y = point[1]
        drone.takeoff(1, point[2])

    previous_points = start_points
    action_steps = 0
    for idx, state in enumerate(FLOW_STATES[1:], start=1):
        previous_state = FLOW_STATES[idx - 1]
        target_points = state_points(state)
        duration = state[0] - previous_state[0]
        light_sec = 0.0
        move_duration = duration - light_sec
        duration_ms = int(round(light_sec * 1000))
        for drone_idx, drone in enumerate(ds):
            previous = previous_points[drone_idx]
            target = target_points[drone_idx]
            speed, acc = 200, 400
            drone.inittime(state[0])
            drone.VelXY(speed, acc)
            drone.VelZ(speed, acc)
            drone.move2(*target)
            apply_state_lights(drone, drone_idx, state[8], duration_ms)
            action_steps += 1
        previous_points = target_points

    for drone in ds:
        drone.inittime(LAND_TIME_SEC)
        drone.TurnOnAll("#ffffff")
        drone.land()
        drone.end()
    return ds, action_steps // DRONE_COUNT


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
    ds, action_steps = build_drones()
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
    if min_dist < SAFE_DISTANCE_CM:
        raise RuntimeError(f"readback min distance failed: {min_dist:.1f}cm pair={min_pair}")

    pf.show(data, t0, music, field=field, device=device, save=name, FPS=max(10, args.preview_fps), max_fps=timing_fps)
    print("Original flow-field v4 generated")
    print(f"project: {name}")
    print(f"preview: {name}.mp4")
    print(f"duration_sec: {t0 / float(timing_fps):.2f}")
    print(f"action_steps: {action_steps}")
    print(f"readback_min_distance_cm: {min_dist:.1f}, pair={min_pair}")


if __name__ == "__main__":
    main()
