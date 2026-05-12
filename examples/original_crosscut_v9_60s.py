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


OUTPUT_DIR = REPO_ROOT / "output" / "original_crosscut_v9_60s"
PROJECT_NAME = "original_crosscut_v9_60s"
PROJECT_PATH = OUTPUT_DIR / PROJECT_NAME
DRONE_COUNT = 7
LAND_TIME_SEC = 60
TIMING_FPS = 120
DESIGN_MIN_DISTANCE_CM = F400_SAFE_DISTANCE_CM
MAX_2S_SEGMENT_DISTANCE_CM = 285.0


PHRASE_STATES = [
    (
        4,
        "broken seed",
        [
            (92, 110, 130),
            (180, 155, 172),
            (272, 118, 150),
            (370, 160, 190),
            (470, 115, 145),
            (250, 300, 165),
            (330, 410, 120),
        ],
    ),
    (
        6,
        "diagonal counter-cut",
        [
            (112, 440, 186),
            (202, 350, 126),
            (286, 272, 205),
            (368, 188, 142),
            (455, 92, 184),
            (455, 445, 128),
            (95, 92, 162),
        ],
    ),
    (
        8,
        "center gate",
        [
            (280, 90, 174),
            (280, 185, 132),
            (280, 292, 208),
            (280, 395, 146),
            (280, 490, 188),
            (98, 300, 130),
            (462, 300, 202),
        ],
    ),
    (
        10,
        "corner exchange",
        [
            (82, 84, 186),
            (180, 470, 136),
            (300, 106, 212),
            (470, 212, 146),
            (420, 465, 190),
            (96, 330, 156),
            (300, 300, 122),
        ],
    ),
    (
        12,
        "vertical ladder",
        [
            (114, 250, 122),
            (170, 250, 176),
            (226, 250, 130),
            (282, 250, 206),
            (338, 250, 150),
            (394, 250, 190),
            (450, 250, 132),
        ],
    ),
    (
        14,
        "scatter pins",
        [
            (95, 440, 156),
            (145, 120, 212),
            (235, 360, 126),
            (315, 150, 186),
            (390, 430, 146),
            (465, 250, 202),
            (265, 270, 160),
        ],
    ),
    (
        16,
        "low-high sweep",
        [
            (85, 280, 206),
            (165, 390, 150),
            (245, 490, 186),
            (315, 70, 132),
            (395, 170, 212),
            (475, 280, 150),
            (280, 285, 176),
        ],
    ),
    (
        18,
        "compression knot",
        [
            (215, 230, 146),
            (260, 190, 192),
            (315, 225, 126),
            (350, 285, 206),
            (285, 335, 150),
            (230, 300, 186),
            (410, 410, 166),
        ],
    ),
    (
        20,
        "exploded corners",
        [
            (70, 70, 136),
            (70, 490, 202),
            (490, 70, 182),
            (490, 490, 146),
            (280, 90, 216),
            (95, 280, 150),
            (465, 285, 192),
        ],
    ),
    (
        22,
        "zigzag counterflow",
        [
            (95, 170, 206),
            (165, 390, 136),
            (235, 150, 186),
            (305, 410, 146),
            (375, 130, 212),
            (445, 390, 156),
            (280, 270, 122),
        ],
    ),
    (
        24,
        "split trios",
        [
            (155, 160, 160),
            (210, 115, 206),
            (270, 160, 130),
            (390, 400, 190),
            (445, 445, 140),
            (500, 400, 212),
            (320, 280, 152),
        ],
    ),
    (
        27,
        "x-cross",
        [
            (95, 95, 212),
            (175, 175, 140),
            (255, 255, 186),
            (335, 335, 130),
            (455, 455, 206),
            (455, 95, 156),
            (95, 455, 190),
        ],
    ),
    (
        29,
        "burst split",
        [
            (280, 70, 146),
            (105, 180, 202),
            (455, 180, 126),
            (150, 380, 186),
            (410, 380, 150),
            (280, 500, 216),
            (280, 285, 160),
        ],
    ),
    (
        31,
        "asymmetric fan break",
        [
            (80, 260, 190),
            (160, 165, 136),
            (245, 115, 206),
            (335, 135, 150),
            (430, 220, 186),
            (485, 340, 126),
            (260, 410, 212),
        ],
    ),
    (
        33,
        "reverse diagonal rake",
        [
            (80, 420, 140),
            (165, 345, 206),
            (250, 270, 150),
            (335, 195, 190),
            (420, 120, 130),
            (470, 455, 216),
            (115, 95, 172),
        ],
    ),
    (
        35,
        "loose star",
        [
            (280, 90, 190),
            (385, 170, 136),
            (470, 300, 206),
            (375, 430, 150),
            (220, 445, 186),
            (95, 310, 126),
            (170, 165, 216),
        ],
    ),
    (
        37,
        "crosscut exit",
        [
            (110, 120, 132),
            (450, 120, 186),
            (110, 450, 212),
            (450, 450, 146),
            (280, 280, 202),
            (180, 300, 150),
            (380, 300, 170),
        ],
    ),
    (
        39,
        "inside-out slash",
        [
            (260, 105, 214),
            (340, 130, 138),
            (430, 230, 190),
            (390, 390, 128),
            (235, 455, 204),
            (100, 335, 154),
            (135, 175, 178),
        ],
    ),
    (
        41,
        "two-way hinge",
        [
            (92, 235, 144),
            (170, 120, 208),
            (258, 235, 158),
            (348, 120, 190),
            (468, 235, 134),
            (390, 455, 214),
            (220, 405, 176),
        ],
    ),
    (
        43,
        "wide scissors",
        [
            (92, 470, 204),
            (165, 300, 136),
            (242, 115, 188),
            (322, 475, 152),
            (405, 300, 214),
            (482, 112, 144),
            (282, 290, 176),
        ],
    ),
    (
        45,
        "offset column snap",
        [
            (190, 92, 154),
            (245, 182, 212),
            (190, 270, 132),
            (245, 362, 188),
            (190, 455, 144),
            (410, 165, 206),
            (410, 365, 166),
        ],
    ),
    (
        47,
        "opposed shelves",
        [
            (82, 150, 220),
            (178, 220, 156),
            (275, 150, 196),
            (372, 220, 132),
            (468, 150, 182),
            (178, 420, 142),
            (382, 420, 212),
        ],
    ),
    (
        49,
        "pinwheel break",
        [
            (145, 145, 150),
            (280, 88, 214),
            (420, 145, 168),
            (472, 280, 206),
            (415, 420, 136),
            (280, 472, 190),
            (135, 405, 176),
        ],
    ),
    (
        51,
        "center punch",
        [
            (280, 180, 132),
            (225, 230, 188),
            (335, 230, 218),
            (205, 322, 150),
            (355, 322, 204),
            (280, 382, 160),
            (470, 470, 186),
        ],
    ),
    (
        53,
        "last diagonal swap",
        [
            (92, 95, 206),
            (178, 470, 142),
            (278, 112, 190),
            (360, 455, 132),
            (470, 100, 214),
            (455, 355, 154),
            (110, 312, 178),
        ],
    ),
    (
        55,
        "final wide rake",
        [
            (90, 345, 138),
            (160, 235, 210),
            (232, 345, 154),
            (305, 235, 196),
            (378, 345, 128),
            (450, 235, 218),
            (280, 470, 170),
        ],
    ),
    (
        57,
        "settle mark",
        [
            (110, 120, 132),
            (450, 120, 186),
            (110, 450, 212),
            (450, 450, 146),
            (280, 280, 202),
            (180, 300, 150),
            (380, 300, 170),
        ],
    ),
]


def clamp(value, low, high):
    return max(low, min(high, value))


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


def interpolated_path_min(start_points, target_points, samples=40):
    best = 10**9
    best_pair = (0, 0)
    best_ratio = 0.0
    for step in range(samples + 1):
        ratio = step / float(samples)
        frame_points = []
        for idx in range(DRONE_COUNT):
            frame_points.append(
                tuple(
                    start_points[idx][axis] * (1 - ratio) + target_points[idx][axis] * ratio
                    for axis in range(3)
                )
            )
        dist, pair = min_horizontal_distance(frame_points)
        if dist < best:
            best = dist
            best_pair = pair
            best_ratio = ratio
    return best, best_pair, best_ratio


def segment_cross_energy(start_points, target_points):
    energy = 0.0
    for i in range(DRONE_COUNT):
        xi = target_points[i][0] - start_points[i][0]
        yi = target_points[i][1] - start_points[i][1]
        for j in range(i + 1, DRONE_COUNT):
            xj = target_points[j][0] - start_points[j][0]
            yj = target_points[j][1] - start_points[j][1]
            energy += abs(xi * yj - yi * xj) / 10000.0
    return energy


def choose_targets(start_points, raw_targets):
    best = None
    best_targets = None
    fallback = None
    fallback_targets = None
    for perm in itertools.permutations(range(DRONE_COUNT)):
        target_points = [raw_targets[idx] for idx in perm]
        path_min, pair, ratio = interpolated_path_min(start_points, target_points)
        distances = [math.dist(start_points[idx], target_points[idx]) for idx in range(DRONE_COUNT)]
        mean_distance = sum(distances) / len(distances)
        max_distance = max(distances)
        cross_energy = segment_cross_energy(start_points, target_points)
        safe_band = min(path_min, 96.0)
        score = safe_band * 10000 + mean_distance * 24 + cross_energy * 16 - max_distance * 2
        candidate = (score, path_min, mean_distance, -max_distance, cross_energy, perm, pair, ratio)
        if fallback is None or candidate > fallback:
            fallback = candidate
            fallback_targets = target_points
        if max_distance > MAX_2S_SEGMENT_DISTANCE_CM:
            continue
        if best is None or candidate > best:
            best = candidate
            best_targets = target_points
    if best is None:
        return fallback_targets, fallback
    return best_targets, best


def assign_states():
    assigned = []
    assignment_report = []
    time_sec, name, points = PHRASE_STATES[0]
    assigned.append((time_sec, name, [tuple(point) for point in points]))
    for time_sec, name, raw_points in PHRASE_STATES[1:]:
        targets, score = choose_targets(assigned[-1][2], [tuple(point) for point in raw_points])
        assigned.append((time_sec, name, targets))
        assignment_report.append((time_sec, name, score))
    return assigned, assignment_report


def travel_time(distance_cm, speed_cm_s, acc_cm_s2):
    if distance_cm <= 0:
        return 0.0
    accel_distance = speed_cm_s * speed_cm_s / (2 * acc_cm_s2)
    if distance_cm >= 2 * accel_distance:
        return 2 * speed_cm_s / acc_cm_s2 + (distance_cm - 2 * accel_distance) / speed_cm_s
    return 2 * math.sqrt(distance_cm / acc_cm_s2)


def speed_for_segment(distance_cm, duration_sec):
    usable_duration = max(0.35, duration_sec - 0.05)
    best = None
    for speed in range(20, 201):
        for acc in range(50, 401, 5):
            t = travel_time(distance_cm, speed, acc)
            if t <= usable_duration:
                score = (usable_duration - t, speed)
                if best is None or score < best[0]:
                    best = (score, speed, acc, t)
    if best is not None:
        return best[1], best[2], best[3]
    return 200, 400, travel_time(distance_cm, 200, 400)


def validate_planned_path(states):
    best = 10**9
    best_info = None
    for time_sec, name, points in states:
        dist, pair = min_horizontal_distance(points)
        if dist < best:
            best = dist
            best_info = (time_sec, name, pair, "state", 0.0)
    for (start_time, start_name, start_points), (end_time, end_name, target_points) in zip(states, states[1:]):
        dist, pair, ratio = interpolated_path_min(start_points, target_points, samples=80)
        if dist < best:
            best = dist
            best_info = ((start_time, end_time), f"{start_name} -> {end_name}", pair, "transition", ratio)
    if best < DESIGN_MIN_DISTANCE_CM:
        raise RuntimeError(
            f"planned path distance failed: {best:.1f}cm pair={best_info[2]} at {best_info[0]}"
        )
    return best, best_info


def hex_to_rgb(color):
    color = str(color).lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def rgb_to_hex(rgb):
    return "#" + "".join("%02x" % int(round(clamp(channel, 0, 255))) for channel in rgb)


def blend_rgb(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def phrase_color(state_index, drone_idx):
    palette = ["#00d2d3", "#ff9f43", "#ee5253", "#10ac84", "#54a0ff", "#f368e0", "#feca57"]
    base = hex_to_rgb(palette[(state_index + drone_idx * 2) % len(palette)])
    accent = hex_to_rgb(palette[(state_index * 2 + drone_idx + 3) % len(palette)])
    pulse = 0.34 + 0.16 * math.sin(state_index * 0.9 + drone_idx * 1.7)
    return rgb_to_hex(blend_rgb(base, accent, pulse))


def signed_turn_balance(states):
    clockwise = 0
    counterclockwise = 0
    flat = 0
    for drone_idx in range(DRONE_COUNT):
        area = 0.0
        points = [state[2][drone_idx] for state in states]
        for a, b in zip(points, points[1:]):
            area += a[0] * b[1] - b[0] * a[1]
        if area > 800:
            counterclockwise += 1
        elif area < -800:
            clockwise += 1
        else:
            flat += 1
    return clockwise, counterclockwise, flat


def build_drones():
    states, assignment_report = assign_states()
    planned_min, planned_info = validate_planned_path(states)
    ds = [pf.Drone(0, 0, pf.drone_config_6m, f"192.168.51.{51 + i}") for i in range(DRONE_COUNT)]

    start_points = states[0][2]
    for drone_idx, (drone, point) in enumerate(zip(ds, start_points)):
        drone.X = drone.x = point[0]
        drone.Y = drone.y = point[1]
        drone.takeoff(1, point[2])
        drone.inittime(states[0][0])
        drone.TurnOnAll(phrase_color(0, drone_idx))

    timing_report = []
    move_distances = []
    for state_index, ((start_time, _, start_points), (end_time, _, target_points)) in enumerate(
        zip(states, states[1:]),
        start=1,
    ):
        duration = end_time - start_time
        for drone_idx, drone in enumerate(ds):
            distance = math.dist(start_points[drone_idx], target_points[drone_idx])
            speed, acc, estimated = speed_for_segment(distance, duration)
            drone.inittime(start_time)
            drone.VelXY(speed, acc)
            drone.VelZ(speed, acc)
            drone.move2(*target_points[drone_idx])
            drone.TurnOnAll(phrase_color(state_index, drone_idx))
            move_distances.append(distance)
            timing_report.append((start_time, end_time, drone_idx + 1, distance, speed, acc, estimated))

    for drone in ds:
        drone.inittime(LAND_TIME_SEC)
        drone.TurnOnAll("#ffffff")
        drone.land()
        drone.end()
    return ds, states, assignment_report, planned_min, planned_info, timing_report, move_distances


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


def fail_on_pyfii_warnings(stage, warning_items):
    messages = [str(item.message) for item in warning_items]
    unsafe = [msg for msg in messages if "distance between" in msg or "action isn't completed" in msg]
    if unsafe:
        raise RuntimeError(f"PyFii unsafe warnings during {stage}: " + "; ".join(unsafe[:5]))
    return messages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--music", default="")
    parser.add_argument("--preview-fps", type=int, default=20)
    parser.add_argument("--timing-fps", type=int, default=TIMING_FPS)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ds, states, assignment_report, planned_min, planned_info, timing_report, move_distances = build_drones()
    name = str(PROJECT_PATH)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        project = pf.Fii(name, ds, music=args.music)
        project.save()
    fail_on_pyfii_warnings("save", caught)

    timing_fps = max(60, args.timing_fps)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        data, t0, music, field, device = pf.read_fii(name, fps=timing_fps)
    fail_on_pyfii_warnings("read_fii", caught)

    min_dist, min_pair, min_sec = readback_min_distance(data, timing_fps)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        pf.show(data, t0, music, field=field, device=device, save=name, FPS=max(10, args.preview_fps), max_fps=timing_fps)
    fail_on_pyfii_warnings("show", caught)

    longest_hover = max(max(0.0, end - start - estimated) for start, end, _, _, _, _, estimated in timing_report)
    mean_distance = sum(move_distances) / len(move_distances)
    max_distance = max(move_distances)
    cw, ccw, flat = signed_turn_balance(states)
    weakest_assignment = min(assignment_report, key=lambda item: item[2][1])
    print("Original crosscut v9 generated")
    print(f"project: {name}")
    print(f"preview: {name}.mp4")
    print(f"duration_sec: {t0 / float(timing_fps):.2f}")
    print(f"phrase_count: {len(states)}")
    print(f"planned_min_distance_cm: {planned_min:.1f}, info={planned_info}")
    print(f"readback_min_distance_cm: {min_dist:.1f}, pair={min_pair}, sec={min_sec:.2f}")
    print(f"mean_segment_distance_cm: {mean_distance:.1f}")
    print(f"max_segment_distance_cm: {max_distance:.1f}")
    print(f"longest_computed_hover_sec: {longest_hover:.2f}")
    print(f"signed_turn_balance: clockwise={cw}, counterclockwise={ccw}, flat={flat}")
    print(
        "weakest_transition: "
        f"t={weakest_assignment[0]} {weakest_assignment[1]}, "
        f"path_min={weakest_assignment[2][1]:.1f}cm"
    )


if __name__ == "__main__":
    main()
