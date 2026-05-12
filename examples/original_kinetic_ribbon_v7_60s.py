import argparse
import math
import sys
import warnings
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / "src"))
sys.path.append(str(REPO_ROOT / "src" / "pyfii"))

import pyfii as pf
from pyfii.extensions.nl_choreo.keyframe_workflow import F400_SAFE_DISTANCE_CM


OUTPUT_DIR = REPO_ROOT / "output" / "original_kinetic_ribbon_v7_60s"
PROJECT_NAME = "original_kinetic_ribbon_v7_60s"
PROJECT_PATH = OUTPUT_DIR / PROJECT_NAME
DRONE_COUNT = 7
TIMES = list(range(4, 57, 2))
LAND_TIME_SEC = 60
DESIGN_MIN_DISTANCE_CM = max(F400_SAFE_DISTANCE_CM, 68)


def clamp(value, low, high):
    return max(low, min(high, value))


def point3(values):
    limits = ((55, 505), (55, 505), (98, 225))
    return tuple(int(round(clamp(values[idx], *limits[idx]))) for idx in range(3))


def field_parameters(time_sec):
    u = (time_sec - TIMES[0]) / (TIMES[-1] - TIMES[0])
    center_x = 280 + 52 * math.sin(2 * math.pi * 1.15 * u + 0.3)
    center_x += 24 * math.sin(2 * math.pi * 2.35 * u + 1.1)
    center_y = 282 + 50 * math.cos(2 * math.pi * 0.95 * u + 0.55)
    center_y -= 28 * math.sin(2 * math.pi * 1.9 * u - 0.25)
    radius = 190 + 34 * math.sin(2 * math.pi * 1.55 * u - 0.25)
    radius += 22 * math.sin(2 * math.pi * 3.15 * u + 0.75)
    y_scale = 0.76 + 0.20 * (0.5 + 0.5 * math.sin(2 * math.pi * 1.65 * u + 1.05))
    rotation = 0.25 + 2 * math.pi * 2.15 * u
    rotation += 0.52 * math.sin(2 * math.pi * 2.25 * u - 0.15)
    span = 5.05 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * 1.35 * u + 0.7))
    phase = 2 * math.pi * 2.55 * u
    return center_x, center_y, radius, y_scale, rotation, span, phase, u


def ribbon_points(time_sec):
    center_x, center_y, radius, y_scale, rotation, span, phase, u = field_parameters(time_sec)
    points = []
    for idx in range(DRONE_COUNT):
        q = idx / (DRONE_COUNT - 1)
        theta = rotation - span / 2 + span * q
        theta += 0.08 * math.sin(phase + idx * 1.39)
        local_radius = radius * (1 + 0.07 * math.sin(phase * 1.1 + idx * 1.63))
        x0 = local_radius * math.cos(theta)
        y0 = y_scale * local_radius * math.sin(theta)
        shear = 0.10 * math.sin(2 * math.pi * u * 1.7 + 0.4)
        x = center_x + x0 + shear * y0
        y = center_y + y0
        z = 156 + 36 * math.sin(theta * 1.08 + phase * 0.56)
        z += 13 * math.cos(idx * 1.64 + phase)
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
    accel_distance = speed_cm_s * speed_cm_s / (2 * acc_cm_s2)
    if distance_cm >= 2 * accel_distance:
        return 2 * speed_cm_s / acc_cm_s2 + (distance_cm - 2 * accel_distance) / speed_cm_s
    return 2 * math.sqrt(distance_cm / acc_cm_s2)


def speed_for_segment(distance_cm, duration_sec):
    usable_duration = max(0.35, duration_sec - 0.05)
    best = (10**9, 200, 400, 0.0)
    for speed in range(20, 201):
        for acc in range(50, 401, 5):
            t = travel_time(distance_cm, speed, acc)
            if t <= usable_duration:
                score = usable_duration - t
                if score < best[0]:
                    best = (score, speed, acc, t)
    if best[0] < 10**8:
        return best[1], best[2], best[3]
    return 200, 400, travel_time(distance_cm, 200, 400)


def validate_planned_path(points_by_time):
    best = 10**9
    best_info = None
    for time_sec, points in points_by_time:
        dist, pair = min_horizontal_distance(points)
        if dist < best:
            best = dist
            best_info = (time_sec, pair, "state")

    for (t0, a), (t1, b) in zip(points_by_time, points_by_time[1:]):
        for step in range(1, 80):
            ratio = step / 80
            frame_points = []
            for idx in range(DRONE_COUNT):
                frame_points.append(tuple(a[idx][axis] * (1 - ratio) + b[idx][axis] * ratio for axis in range(3)))
            dist, pair = min_horizontal_distance(frame_points)
            if dist < best:
                best = dist
                best_info = ((t0, t1, ratio), pair, "transition")

    if best < DESIGN_MIN_DISTANCE_CM:
        raise RuntimeError(f"planned path distance failed: {best:.1f}cm pair={best_info[1]} at {best_info[0]}")
    return best, best_info


def hex_to_rgb(color):
    color = str(color).lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def rgb_to_hex(rgb):
    return "#" + "".join("%02x" % int(round(clamp(channel, 0, 255))) for channel in rgb)


def blend_rgb(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def ribbon_color(time_sec, drone_idx):
    palette = ["#48dbfb", "#ffdd59", "#ff6b9a", "#7bed9f", "#70a1ff", "#fd79a8", "#ffeaa7"]
    u = (time_sec - TIMES[0]) / (TIMES[-1] - TIMES[0])
    palette_pos = u * (len(palette) - 1)
    base_idx = min(len(palette) - 1, int(palette_pos))
    next_idx = min(len(palette) - 1, base_idx + 1)
    base = hex_to_rgb(palette[base_idx])
    next_color = hex_to_rgb(palette[next_idx])
    shimmer = 0.5 + 0.5 * math.sin(2 * math.pi * (u * 4.1 + drone_idx / DRONE_COUNT))
    mixed = blend_rgb(base, next_color, min(1.0, palette_pos - base_idx + 0.18 * shimmer))
    return rgb_to_hex(blend_rgb(mixed, (255, 255, 255), 0.10 * shimmer))


def build_drones():
    points_by_time = [(time_sec, ribbon_points(time_sec)) for time_sec in TIMES]
    planned_min, planned_info = validate_planned_path(points_by_time)
    ds = [pf.Drone(0, 0, pf.drone_config_6m, f"192.168.51.{51 + i}") for i in range(DRONE_COUNT)]

    start_points = points_by_time[0][1]
    for drone_idx, (drone, point) in enumerate(zip(ds, start_points)):
        drone.X = drone.x = point[0]
        drone.Y = drone.y = point[1]
        drone.takeoff(1, point[2])
        drone.inittime(TIMES[0])
        drone.TurnOnAll(ribbon_color(TIMES[0], drone_idx))

    action_steps = 0
    timing_report = []
    move_distances = []
    for (start_time, start_points), (end_time, target_points) in zip(points_by_time, points_by_time[1:]):
        duration = end_time - start_time
        for drone_idx, drone in enumerate(ds):
            distance = math.dist(start_points[drone_idx], target_points[drone_idx])
            speed, acc, estimated = speed_for_segment(distance, duration)
            drone.inittime(start_time)
            drone.VelXY(speed, acc)
            drone.VelZ(speed, acc)
            drone.move2(*target_points[drone_idx])
            drone.TurnOnAll(ribbon_color(end_time, drone_idx))
            action_steps += 1
            move_distances.append(distance)
            timing_report.append((start_time, end_time, drone_idx + 1, distance, speed, acc, estimated))

    for drone in ds:
        drone.inittime(LAND_TIME_SEC)
        drone.TurnOnAll("#ffffff")
        drone.land()
        drone.end()
    return ds, action_steps // DRONE_COUNT, planned_min, planned_info, timing_report, move_distances


def readback_min_distance(data, fps):
    min_dist = 10**9
    min_pair = (0, 0)
    min_sec = 0.0
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
            min_sec = frame_idx / float(fps)
    return min_dist, min_pair, min_sec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--music", default="")
    parser.add_argument("--preview-fps", type=int, default=20)
    parser.add_argument("--timing-fps", type=int, default=120)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ds, action_steps, planned_min, planned_info, timing_report, move_distances = build_drones()
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

    min_dist, min_pair, min_sec = readback_min_distance(data, timing_fps)
    if min_dist < DESIGN_MIN_DISTANCE_CM:
        raise RuntimeError(f"readback min distance failed: {min_dist:.1f}cm pair={min_pair} at {min_sec:.2f}s")

    pf.show(data, t0, music, field=field, device=device, save=name, FPS=max(10, args.preview_fps), max_fps=timing_fps)
    longest_hover = max(max(0.0, end - start - estimated) for start, end, _, _, _, _, estimated in timing_report)
    mean_distance = sum(move_distances) / len(move_distances)
    max_distance = max(move_distances)
    print("Original kinetic ribbon v7 generated")
    print(f"project: {name}")
    print(f"preview: {name}.mp4")
    print(f"duration_sec: {t0 / float(timing_fps):.2f}")
    print(f"action_steps: {action_steps}")
    print(f"planned_min_distance_cm: {planned_min:.1f}, info={planned_info}")
    print(f"readback_min_distance_cm: {min_dist:.1f}, pair={min_pair}, sec={min_sec:.2f}")
    print(f"mean_segment_distance_cm: {mean_distance:.1f}")
    print(f"max_segment_distance_cm: {max_distance:.1f}")
    print(f"max_estimated_hover_gap_sec: {longest_hover:.2f}")


if __name__ == "__main__":
    main()
