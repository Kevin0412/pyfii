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


OUTPUT_DIR = REPO_ROOT / "output" / "original_phrase_motion_v4_70s"
PROJECT_NAME = "original_phrase_motion_v4_70s"
PROJECT_PATH = OUTPUT_DIR / PROJECT_NAME
DRONE_COUNT = 7
SAFE_DISTANCE_CM = F400_SAFE_DISTANCE_CM
LAND_TIME_SEC = 69


FORMATIONS = [
    ("asymmetric_launch", [(80, 120, 100), (155, 220, 130), (90, 380, 160), (260, 90, 180), (320, 420, 120), (455, 230, 200), (500, 360, 150)]),
    ("wide_star", [(280, 60, 170), (450, 135, 125), (500, 310, 185), (385, 500, 140), (175, 500, 210), (60, 310, 150), (110, 135, 195)]),
    ("broken_column", [(250, 60, 120), (310, 140, 175), (250, 220, 210), (310, 300, 145), (310, 460, 130), (250, 540, 165), (250, 380, 190)]),
    ("two_clusters_lead", [(115, 160, 210), (165, 260, 150), (115, 360, 180), (280, 260, 230), (445, 440, 120), (395, 340, 200), (445, 540, 145)]),
    ("compact_ring", [(170, 280, 190), (225, 185, 140), (225, 375, 120), (280, 280, 210), (390, 375, 170), (390, 280, 130), (280, 445, 220)]),
    ("s_curve", [(90, 90, 180), (190, 145, 120), (120, 430, 170), (290, 250, 210), (370, 430, 190), (430, 150, 145), (280, 520, 130)]),
    ("wide_x", [(80, 80, 130), (180, 180, 180), (280, 280, 220), (380, 380, 120), (480, 480, 165), (480, 80, 200), (80, 480, 145)]),
    ("horizontal_wave", [(60, 300, 160), (140, 210, 210), (220, 300, 125), (300, 390, 180), (460, 390, 220), (540, 210, 135), (140, 390, 190)]),
    ("rear_crescent", [(80, 420, 150), (145, 315, 205), (240, 245, 130), (350, 245, 190), (510, 420, 210), (445, 315, 120), (280, 490, 165)]),
    ("spiral_bloom", [(140, 280, 200), (190, 410, 120), (280, 280, 130), (340, 210, 190), (430, 250, 150), (440, 360, 220), (330, 440, 170)]),
    ("diagonal_blade", [(100, 280, 120), (170, 430, 165), (240, 340, 210), (310, 250, 145), (380, 190, 190), (460, 300, 180), (400, 430, 135)]),
    ("exploded_asymmetry", [(60, 80, 210), (120, 500, 130), (240, 420, 185), (280, 120, 150), (520, 80, 190), (500, 320, 140), (400, 500, 220)]),
    ("gate_columns", [(160, 120, 150), (160, 440, 220), (160, 280, 130), (280, 280, 200), (400, 120, 160), (400, 280, 200), (400, 440, 120)]),
    ("counter_spiral", [(140, 190, 130), (280, 500, 160), (90, 320, 190), (280, 90, 220), (420, 190, 180), (470, 320, 125), (380, 430, 210)]),
    ("final_v", [(60, 280, 110), (150, 210, 130), (240, 160, 150), (330, 160, 170), (420, 210, 190), (510, 280, 210), (285, 350, 160)]),
    ("bow_line", [(70, 280, 110), (140, 280, 110), (210, 280, 110), (280, 280, 110), (420, 280, 110), (490, 280, 110), (350, 280, 110)]),
]


PHRASE_DURATIONS = [4, 4, 3, 5, 4, 5, 3, 4, 5, 4, 5, 4, 5, 4, 3]
PHRASE_COLORS = [
    "#48dbfb",
    "#ffdd59",
    "#ff9f43",
    "#ff6b9a",
    "#7bed9f",
    "#a29bfe",
    "#70a1ff",
    "#feca57",
    "#ff6b81",
    "#55efc4",
    "#74b9ff",
    "#fd79a8",
    "#ffeaa7",
    "#81ecec",
    "#ffffff",
]


def build_phrases():
    phrases = []
    cursor = 4
    for idx, duration in enumerate(PHRASE_DURATIONS):
        phrases.append(
            {
                "phrase_id": f"O{idx + 1:02d}",
                "start": cursor,
                "end": cursor + duration,
                "from": idx,
                "to": idx + 1,
                "color": PHRASE_COLORS[idx],
            }
        )
        cursor += duration
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
    usable_duration = max(0.35, duration_sec - 0.08)
    for speed in range(20, 201):
        acc = max(50, min(400, speed * 2))
        if travel_time(distance_cm, speed, acc) <= usable_duration:
            return speed, acc
    return 200, 400


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


def phrase_point_float(phrase, drone_idx, t):
    start = FORMATIONS[phrase["from"]][1][drone_idx]
    end = FORMATIONS[phrase["to"]][1][drone_idx]
    ease = smoothstep(t)
    base = mix_point(start, end, ease)
    ux, uy, nx, ny, rx, ry = unit_axes(start, end, base)
    phrase_idx = int(phrase["phrase_id"][1:]) - 1
    phase = 2 * math.pi * drone_idx / DRONE_COUNT + phrase_idx * 0.79
    rank = (drone_idx - 3) / 3
    alt = 1 if drone_idx % 2 == 0 else -1
    bump = math.sin(math.pi * t)
    late = bump * smoothstep(clamp((t - 0.40) / 0.60, 0, 1))
    amp = 16 + 4 * (phrase["end"] - phrase["start"])
    if phrase_idx in {2, 3, 9}:
        amp *= 0.12

    arc = amp * 0.35 * bump * math.sin(2 * math.pi * t + phase)
    along = amp * 0.18 * bump * rank
    radial = 0.0
    vertical = amp * 0.28 * bump * math.sin(2 * math.pi * t + phase)

    if phrase_idx in {0, 8, 13}:
        radial += amp * 0.65 * late
        arc += amp * 0.30 * bump * alt
    elif phrase_idx in {1, 11}:
        arc += amp * 0.60 * bump * alt
        vertical += amp * 0.45 * bump * alt
    elif phrase_idx in {2, 6, 14}:
        along -= amp * 0.50 * bump
        vertical += amp * 0.35 * bump * alt
    elif phrase_idx in {3, 9}:
        radial -= amp * 0.65 * bump
        arc += amp * 0.45 * bump * math.cos(2 * math.pi * t + phase)
    elif phrase_idx in {4, 7, 12}:
        arc += amp * 0.75 * bump * math.sin(2 * math.pi * t + phase)
        along += amp * 0.30 * bump * math.cos(3 * math.pi * t + phase)
    else:
        arc += amp * 0.45 * bump
        radial += amp * 0.28 * bump * math.sin(phase)

    return (
        base[0] + nx * arc + ux * along + rx * radial,
        base[1] + ny * arc + uy * along + ry * radial,
        base[2] + vertical,
    )


def phrase_point(phrase, drone_idx, t):
    return point3(phrase_point_float(phrase, drone_idx, t))


def max_travel_time_for_steps(phrase, step_count):
    previous_points = FORMATIONS[phrase["from"]][1]
    worst_time = 0.0
    for step_idx in range(step_count):
        t = (step_idx + 1) / step_count
        points = [phrase_point(phrase, idx, t) for idx in range(DRONE_COUNT)]
        for idx in range(DRONE_COUNT):
            worst_time = max(worst_time, travel_time(distance_3d(previous_points[idx], points[idx]), 200, 400))
        previous_points = points
    return worst_time


def phrase_step_count(phrase):
    duration = phrase["end"] - phrase["start"]
    for step_count in (3, 2, 1):
        step_duration = duration / step_count
        if max_travel_time_for_steps(phrase, step_count) <= step_duration - 0.06:
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
    accent = (255, 255, 255) if (tick_idx + drone_idx) % 4 == 0 else (120, 230, 255)
    phase = tick_idx / max(1, tick_count) + drone_idx / DRONE_COUNT
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * phase)
    return rgb_to_hex(scale_rgb(blend_rgb(base, accent, 0.22 + 0.36 * pulse), 0.58 + 0.42 * pulse))


def apply_phrase_lights(drone, drone_idx, phrase, duration_ms):
    step_ms = 100
    steps = max(1, int(duration_ms // step_ms))
    for tick_idx in range(steps):
        if (tick_idx + drone_idx) % 19 == 18:
            drone.TurnOffAll()
        else:
            drone.TurnOnAll(pulse_color(phrase["color"], drone_idx, tick_idx, steps))
        drone.delay(step_ms)
    remain = max(0, int(duration_ms) - steps * step_ms)
    if remain:
        drone.delay(remain)


def validate_static_formations():
    for name, points in FORMATIONS:
        best, pair = min_horizontal_distance(points)
        if best < SAFE_DISTANCE_CM:
            raise RuntimeError(f"formation {name} too tight: {best:.1f}cm pair={pair}")


def validate_planned_keypoints():
    validate_static_formations()
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
                best_pair = pair
                best_label = f"{phrase['phrase_id']}@{t:.2f}"
    if best < SAFE_DISTANCE_CM:
        raise RuntimeError(f"planned keypoint distance failed: {best:.1f}cm pair={best_pair} at {best_label}")


def build_drones():
    validate_planned_keypoints()
    ds = [pf.Drone(0, 0, pf.drone_config_6m, f"192.168.51.{51 + i}") for i in range(DRONE_COUNT)]
    start_points = FORMATIONS[0][1]
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
        next_points = [phrase_point(phrase, idx, 1.0) for idx in range(DRONE_COUNT)]
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
    print("Original phrase-motion v4 generated")
    print(f"project: {name}")
    print(f"preview: {name}.mp4")
    print(f"duration_sec: {t0 / float(timing_fps):.2f}")
    print(f"action_steps: {action_steps}")
    print(f"step_counts: {used_step_counts}")
    print(f"readback_min_distance_cm: {min_dist:.1f}, pair={min_pair}")


if __name__ == "__main__":
    main()
