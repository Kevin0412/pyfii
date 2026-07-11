#!/usr/bin/env python3
"""
flight_log_analysis.py — 真实飞行遥测 vs pyfii 运动模型 对照分析

用法:  python3 tools/flight_log_analysis.py
依赖:  numpy, matplotlib（CJK 字体 Noto Sans CJK 或回退英文）
输入:  flight_logs/<flight>/telemetry.csv（本地，未入仓库）
输出:  doc/images/fig1..11_*.png, doc/images/metrics.json

见 doc/flight_log_trajectory_analysis.md。
"""
import csv, os, json, math, collections
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
# register a CJK font so Chinese labels render (not tofu boxes)
for _fp in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/home/kevin0412/.local/share/fonts/NotoSansCJKSC-Regular.ttf"]:
    if os.path.exists(_fp):
        fm.fontManager.addfont(_fp)
        plt.rcParams["font.family"] = fm.FontProperties(fname=_fp).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

LOGDIR = "flight_logs"
OUT = "doc/images"
os.makedirs(OUT, exist_ok=True)
DEFAULT_POSE = np.array([22.0, 24.0, 4.0])

# ----------------------------------------------------------------------------
# 1. Load telemetry
# ----------------------------------------------------------------------------
def load(flight):
    p = os.path.join(LOGDIR, flight, "telemetry.csv")
    rows = list(csv.DictReader(open(p)))
    t = np.array([float(r["elapsed_ms"]) for r in rows]) / 1000.0
    x = np.array([float(r["x_cm"]) for r in rows])
    y = np.array([float(r["y_cm"]) for r in rows])
    z = np.array([float(r["z_cm"]) for r in rows])
    yaw = np.array([float(r["yaw_cdeg"]) for r in rows]) / 100.0
    mode = [r["flightmode"] for r in rows]
    return dict(t=t, x=x, y=y, z=z, yaw=yaw, mode=mode)

# ----------------------------------------------------------------------------
# 2. Faithful pyfii trapezoidal segment simulator
# ----------------------------------------------------------------------------
def sim_segment(P0, P1, vel, acc, fps=200):
    """Straight-line trapezoidal move P0->P1, full stop at P1. Matches read.py."""
    P0 = np.asarray(P0, float); P1 = np.asarray(P1, float)
    D = P1 - P0; R = float(np.linalg.norm(D))
    if R == 0:
        return [], 0.0
    u = D / R
    alenth = vel**2 / (2*acc)          # accel distance
    if R >= 2*alenth:                  # full trapezoid
        acctime = vel/acc
        total = 2*acctime + (R - 2*alenth)/vel
        sacc = alenth
    else:                              # triangle (never reaches vel)
        acctime = (R/acc)**0.5         # sqrt(2*(R/2)/acc)
        total = 2*acctime
        sacc = R/2
    dt = 1.0/fps
    pts = []
    t = 0.0
    while t < total:
        if t <= acctime:
            r = 0.5*acc*t*t
        elif t < total - acctime:
            r = sacc + vel*(t - acctime)
        else:
            r = R - 0.5*acc*(total - t)**2
        p = P0 + u*max(0.0, min(R, r))
        pts.append((t, p[0], p[1], p[2]))
        t += dt
    pts.append((total, P1[0], P1[1], P1[2]))
    return pts, total

def sim_route(cmds, start=(0,0,0), fps=200):
    """cmds: list of ('move', x,y,z, vel,acc) or ('hold', seconds).
    Returns global timeline arrays t,x,y,z and list of waypoint arrival (t, xyz)."""
    T=[]; X=[]; Y=[]; Z=[]; wpts=[]
    cur = np.array(start, float); tg = 0.0
    for c in cmds:
        if c[0] == 'move':
            _,x,y,z,vel,acc = c
            seg,dur = sim_segment(cur,(x,y,z),vel,acc,fps)
            for (tt,px,py,pz) in seg:
                T.append(tg+tt); X.append(px); Y.append(py); Z.append(pz)
            cur = np.array([x,y,z],float); tg += dur
            wpts.append((tg,x,y,z))
        elif c[0] == 'hold':
            dur = c[1]; dt=1.0/fps; tt=0.0
            while tt < dur:
                T.append(tg+tt); X.append(cur[0]); Y.append(cur[1]); Z.append(cur[2])
                tt += dt
            tg += dur
    return np.array(T),np.array(X),np.array(Y),np.array(Z),wpts

def summarize_action_handoffs(output_string, fii, lines, warns):
    """Collapse frame-level warnings into completed/interrupted action handoffs."""
    if "src" not in sys.path:
        sys.path.insert(0, "src")
    from pyfii.read import read_xml

    dots, _, _, _ = read_xml(output_string, list(fii))
    motion_dots = [
        dot for dot in dots
        if dot[-1] in ("move2", "move", "land", "moved")
    ]
    trace = np.array([[line[0] / 1000.0, *line[1:4]] for line in lines], float)
    t = trace[:, 0]
    pos = trace[:, 1:]
    dt = np.diff(t)
    speed = np.linalg.norm(np.diff(pos, axis=0), axis=1) / np.where(dt <= 0, np.nan, dt)

    events = []
    # motion_dots[0] is read_xml's initial-position marker, not a commanded action.
    for previous, incoming in zip(motion_dots[1:-1], motion_dots[2:]):
        if previous[-1] != "move2":
            continue
        command_time = float(incoming[0]) / 1000.0
        idx = max(0, int(np.searchsorted(t, command_time, side="right")) - 1)
        target = np.asarray(previous[1:4], float)
        target_remaining_at_command = float(np.linalg.norm(pos[idx] - target))
        incoming_speed = float(speed[max(0, idx - 1)])
        completed = target_remaining_at_command <= 0.05 and incoming_speed <= 0.05
        interrupted = not completed
        event = dict(
            action_start_s=round(float(previous[0]) / 1000.0, 3),
            command_time_s=round(command_time, 3),
            target_cm=[round(float(value), 3) for value in target],
            incoming_action=str(incoming[-1]),
            completed=completed,
            target_remaining_at_command_cm=round(target_remaining_at_command, 3),
            speed_at_command_cm_s=round(incoming_speed, 3),
        )
        if interrupted:
            stop_candidates = np.where((t[:-1] >= command_time) & (speed <= 0.01))[0]
            if len(stop_candidates):
                stop_idx = int(stop_candidates[0])
                stop_pos = pos[stop_idx]
                event.update(
                    stop_time_s=round(float(t[stop_idx]), 3),
                    braking_duration_s=round(float(t[stop_idx] - command_time), 3),
                    stop_position_cm=[round(float(value), 3) for value in stop_pos],
                    target_remaining_at_stop_cm=round(float(np.linalg.norm(stop_pos - target)), 3),
                )
        events.append(event)

    interrupted = [event for event in events if not event["completed"]]
    completed = [event for event in events if event["completed"]]
    return dict(
        handoff_count=len(events),
        completed_handoffs=len(completed),
        interrupted_handoffs=len(interrupted),
        warning_frame_count=sum("completed" in warning or "未完成" in warning for warning in warns),
        events=events,
    )


def drone_track(drone, fii):
    """Run pyfii's own command-timed trapezoid solver for a Drone program."""
    if "src" not in sys.path:
        sys.path.insert(0, "src")
    from pyfii.read import dots2line
    drone.end()
    lines, _, warns = dots2line(drone.outputString, fii=list(fii))
    handoffs = summarize_action_handoffs(drone.outputString, fii, lines, warns)
    return (
        np.array([l[0] for l in lines], float) / 1000.0,
        np.array([l[1] for l in lines], float),
        np.array([l[2] for l in lines], float),
        np.array([l[3] for l in lines], float),
        warns,
        handoffs,
    )

def pyfii_grid_track(vel_xy=120, acc_xy=300, alt=120):
    if "src" not in sys.path:
        sys.path.insert(0, "src")
    from pyfii.drone import Drone
    d = Drone(0, 0)
    d.takeoff(1, alt)
    d.delay(3000)
    d.VelXY(vel_xy, acc_xy)
    for row in range(4):
        yt = min(40 + row * 80, 320)
        xt = 320 if row % 2 == 0 else 40
        d.move2(xt, yt, alt)
        d.delay(2500)
    d.land()
    return drone_track(d, (0, 0))

def pyfii_complex_track():
    if "src" not in sys.path:
        sys.path.insert(0, "src")
    from pyfii.drone import Drone
    d = Drone(0, 0)
    d.takeoff(1, 120)
    d.delay(3000)
    d.VelXY(100, 400)
    for row in range(4):
        yt = min(40 + row * 80, 320)
        xt = 320 if row % 2 == 0 else 40
        d.move2(xt, yt, 120)
        d.delay(2500)

    # fly_spiral(): already airborne, so model the repeated Takeoff as a hold.
    d.delay(3000)
    d.VelXY(50, 400)
    d.move2(180, 180, 120)
    d.delay(3000)
    for i, r in enumerate([40, 80, 120, 160]):
        d.VelXY([50, 100, 150, 150][i], 400)
        for x, y in [(180+r, 180+r), (180-r, 180+r), (180-r, 180-r), (180+r, 180-r)]:
            d.move2(x, y, 120)
            d.delay(1500)

    # fly_z_stairs()
    d.VelXY(50, 400)
    # pyfii's Drone range rejects z=60, while the fwfii experiment used it.
    # Clamp the command-timed pyfii baseline to the closest representable height.
    d.move2(180, 180, 80)
    d.delay(2000)
    for z in [80, 120, 160, 200]:
        d.move2(180, 180, z)
        d.delay(2000)

    # fly_rectangle()
    d.VelXY(150, 400)
    d.move2(300, 300, 100)
    d.delay(3000)
    for x, y, z in [(300,300,100), (40,300,100), (40,40,100), (300,40,100), (40,40,100)]:
        d.move2(x, y, z)
        d.delay(2000)
    d.land()
    return drone_track(d, (0, 0))

def pyfii_swarm_tracks(kind):
    if "src" not in sys.path:
        sys.path.insert(0, "src")
    from pyfii.drone import Drone
    f1 = Drone(40, 40)
    f2 = Drone(320, 40)
    f1.takeoff(1, 100); f2.takeoff(1, 170)
    for f in (f1, f2):
        f.VelXY(150, 300)
    f1.delay(4000); f2.delay(4000)

    def dual_move(x1, y1, z1, x2, y2, z2, hold):
        f1.move2(x1, y1, z1); f2.move2(x2, y2, z2)
        f1.delay(hold); f2.delay(hold)

    if kind == "171502":
        moves = [
            (40,320,100, 320,320,170, 4000),
            (320,40,100, 40,40,170, 4000),
            (180,180,100, 180,180,180, 3000),
            (40,320,100, 320,40,180, 3000),
            (320,40,120, 40,320,190, 4000),
            (180,180,130, 180,180,200, 3000),
        ]
        for m in moves:
            dual_move(*m)
        f1.delay(4000); f2.delay(4000)  # yaw
        dual_move(40,40,120, 320,320,180, 3000)
        dual_move(40,40,100, 320,40,170, 2000)
    else:
        moves = [
            (40,320,100, 320,320,170, 4000),
            (320,40,100, 40,40,170, 3000),
            (180,180,100, 180,180,180, 3500),
            (40,320,100, 320,40,180, 3500),
            (320,40,120, 40,320,190, 4000),
            (180,180,130, 180,180,200, 3000),
        ]
        for m in moves:
            dual_move(*m)
        f1.delay(4000); f2.delay(4000)  # yaw
        dual_move(40,40,120, 320,320,200, 2000)
        f1.VelXY(200, 400)
        f1.move2(180, 180, 120)
        f2.move2(320, 40, 120)
        f1.delay(3500); f2.delay(3500)
        f1.delay(6000); f2.delay(6000)  # flip window; position not modeled
        dual_move(40,40,120, 320,40,180, 3000)
    f1.land(); f2.land()
    return drone_track(f1, (40, 40)), drone_track(f2, (320, 40))

def paired_distance_from_tracks(track_a, track_b, step=0.2):
    ta, xa, ya, za = track_a[:4]
    tb, xb, yb, zb = track_b[:4]
    lo = max(float(np.min(ta)), float(np.min(tb)))
    hi = min(float(np.max(ta)), float(np.max(tb)))
    tt = np.arange(lo, hi, step)
    if len(tt) == 0:
        return tt, np.array([]), np.array([]), np.array([])
    ax = np.interp(tt, ta, xa); ay = np.interp(tt, ta, ya); az = np.interp(tt, ta, za)
    bx = np.interp(tt, tb, xb); by = np.interp(tt, tb, yb); bz = np.interp(tt, tb, zb)
    xy = np.hypot(ax - bx, ay - by)
    dz = np.abs(az - bz)
    d3 = np.hypot(xy, dz)
    return tt, xy, dz, d3

def first_separated_time_arrays(t, xy, dz):
    idx = np.where((xy > 100) | (dz > 30))[0]
    return float(t[idx[0]]) if len(idx) else None

def summarize_safety_arrays(t, xy, dz, d3):
    """Safety summary for an ideal pyfii two-drone baseline."""
    start = first_separated_time_arrays(t, xy, dz)
    if start is None:
        return dict(effective_start_s=None, samples=0)
    m = t >= start
    tt, xxy, ddz, dd3 = t[m], xy[m], dz[m], d3[m]
    if len(tt) == 0:
        return dict(effective_start_s=round(start, 2), samples=0)
    margins = np.maximum(xxy - 40.0, ddz - 50.0)
    min_xy_idx = int(np.argmin(xxy))
    min_dz_idx = int(np.argmin(ddz))
    min_3d_idx = int(np.argmin(dd3))
    low_dz = xxy[ddz < 50]
    low_xy = ddz[xxy < 40]
    return dict(
        effective_start_s=round(float(start), 2),
        window_s=[round(float(tt[0]), 2), round(float(tt[-1]), 2)],
        samples=int(len(tt)),
        violations=int(np.sum((xxy < 40) & (ddz < 50))),
        min_margin_cm=round(float(np.min(margins)), 1),
        min_xy_cm=round(float(xxy[min_xy_idx]), 1),
        min_xy_at_s=round(float(tt[min_xy_idx]), 2),
        dz_at_min_xy_cm=round(float(ddz[min_xy_idx]), 1),
        min_dz_cm=round(float(ddz[min_dz_idx]), 1),
        xy_at_min_dz_cm=round(float(xxy[min_dz_idx]), 1),
        min_3d_cm=round(float(dd3[min_3d_idx]), 1),
        min_xy_when_dz_lt_50_cm=round(float(np.min(low_dz)), 1) if len(low_dz) else None,
        min_dz_when_xy_lt_40_cm=round(float(np.min(low_xy)), 1) if len(low_xy) else None,
    )

# ----------------------------------------------------------------------------
# 3. Reconstruct routes from trajectory_collect.py
# ----------------------------------------------------------------------------
# pyfii rule: takeoff & land use vel=200, acc=400 (hardcoded in read.py)
TO_V, TO_A = 200, 400

def route_grid(vel_xy, acc_xy, alt=120):
    c = [('move',0,0,alt,TO_V,TO_A), ('hold',3.0)]
    last=(0,0)
    for row in range(4):
        yt = min(40+row*80, 320); xt = 320 if row%2==0 else 40
        c += [('move',xt,yt,alt,vel_xy,acc_xy), ('hold',2.5)]
        last=(xt,yt)
    c += [('move',last[0],last[1],0,TO_V,TO_A)]   # land (pyfii: vel200 acc400)
    return c

def route_spiral(acc, alt=120, center=(180,180)):
    c = [('move',center[0],center[1],alt,50,acc), ('hold',3.0)]
    speeds=[50,100,150,150]
    for i,r in enumerate([40,80,120,160]):
        v=speeds[i]
        for cx,cy in [(center[0]+r,center[1]+r),(center[0]-r,center[1]+r),
                      (center[0]-r,center[1]-r),(center[0]+r,center[1]-r)]:
            c += [('move',cx,cy,alt,v,acc), ('hold',1.5)]
    return c

def route_zstairs(acc):
    # slow horizontal 50; pyfii ignores VelZ so uses 50 for vertical too
    c = [('move',180,180,60,TO_V,TO_A), ('hold',2.0)]
    for z in [80,120,160,200]:
        c += [('move',180,180,z,50,acc), ('hold',2.0)]
    return c

def route_rectangle(acc, alt=100):
    c = [('move',300,300,alt,150,acc), ('hold',3.0)]  # takeoff handled as move up before; approx
    for x,y in [(300,300),(40,300),(40,40),(300,40),(40,40)]:
        c += [('move',x,y,alt,150,acc), ('hold',2.0)]
    return c

# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def speed_series(t,x,y,z):
    dt=np.diff(t)
    v=np.sqrt(np.diff(x)**2+np.diff(y)**2+np.diff(z)**2)/np.where(dt==0,1e-9,dt)
    return t[1:], v

def xy_speed_series(t, x, y):
    dt = np.diff(t)
    v = np.hypot(np.diff(x), np.diff(y)) / np.where(dt == 0, 1e-9, dt)
    return t[1:], v

def clean_glitches(x,y,z,thresh=60):
    """flag samples whose jump from previous > thresh cm (localization glitches)"""
    d=np.sqrt(np.diff(x)**2+np.diff(y)**2+np.diff(z)**2)
    flags=np.zeros(len(x),bool)
    flags[1:]=d>thresh
    return flags

def load_by_uav(flight):
    """Load one flight directory and split rows by uavid."""
    p = os.path.join(LOGDIR, flight, "telemetry.csv")
    rows = list(csv.DictReader(open(p)))
    out = {}
    for uid in sorted({r["uavid"] for r in rows}):
        rr = [r for r in rows if r["uavid"] == uid]
        out[uid] = dict(
            t=np.array([float(r["elapsed_ms"]) for r in rr]) / 1000.0,
            ms=np.array([int(float(r["elapsed_ms"])) for r in rr]),
            x=np.array([float(r["x_cm"]) for r in rr]),
            y=np.array([float(r["y_cm"]) for r in rr]),
            z=np.array([float(r["z_cm"]) for r in rr]),
            yaw=np.array([float(r["yaw_cdeg"]) for r in rr]) / 100.0,
            mode=np.array([r["flightmode"] for r in rr], dtype=object),
            status=np.array([r["fcstatus"] for r in rr], dtype=object),
            rows=rr,
        )
    return out

def coord_valid(d, loose=False):
    """Telemetry positions that are plausible for the 360cm mat plus overshoot."""
    low_y = -250 if loose else -100
    return (
        (d["x"] >= -100) & (d["x"] <= 500) &
        (d["y"] >= low_y) & (d["y"] <= 500) &
        (d["z"] >= -20) & (d["z"] <= 260)
    )

def default_pose_mask(d, radius=3.0):
    pos = np.column_stack([d["x"], d["y"], d["z"]])
    return np.linalg.norm(pos - DEFAULT_POSE, axis=1) <= radius

def physical_track_mask(d, *, allow_flip=False, loose=False):
    """Samples usable as physical trajectory after AprilTag localization cleaning."""
    mode_ok = (d["mode"] == "GUIDED") | ((d["mode"] == "FLIP") if allow_flip else False)
    status_ok = d["status"] == "Good"
    # AprilTag loss often returns the boot/default pose near (22,24,4) while the
    # script is already airborne; keep it for quality analysis, drop it from motion.
    default_airborne = default_pose_mask(d) & (d["t"] > 2.0)
    jump = clean_glitches(d["x"], d["y"], d["z"], 80)
    return mode_ok & status_ok & coord_valid(d, loose=loose) & ~default_airborne & ~jump

def break_on_bad_samples(d, thresh=70, loose=False):
    flags = clean_glitches(d["x"], d["y"], d["z"], thresh) | ~coord_valid(d, loose=loose)
    return np.where(flags, np.nan, d["x"]), np.where(flags, np.nan, d["y"]), np.where(flags, np.nan, d["z"])

def speed_samples(d):
    dt = np.diff(d["t"])
    dt = np.where(dt <= 0, np.nan, dt)
    v = np.sqrt(np.diff(d["x"])**2 + np.diff(d["y"])**2 + np.diff(d["z"])**2) / dt
    return d["t"][1:], v

def first_xy_motion_time(t, x, y, *, z=None, min_t=0.0, min_z=None, threshold=20.0):
    """First sample time after sustained horizontal motion is visible."""
    dt = np.diff(t)
    vxy = np.hypot(np.diff(x), np.diff(y)) / np.where(dt <= 0, np.nan, dt)
    ok = (t[1:] >= min_t) & (vxy >= threshold)
    if z is not None and min_z is not None:
        ok &= z[1:] >= min_z
    idx = np.where(ok)[0]
    return float(t[idx[0] + 1]) if len(idx) else None

def first_event_time(d, mask):
    idx = np.where(mask)[0]
    return round(float(d["t"][idx[0]]), 3) if len(idx) else None


def trapezoid_distance(distance, vel, acc, elapsed):
    """Distance traveled by pyfii's stop-to-stop trapezoid at elapsed seconds."""
    elapsed = np.asarray(elapsed, float)
    accel_distance = vel**2 / (2 * acc)
    if distance >= 2 * accel_distance:
        accel_time = vel / acc
        total_time = distance / vel + vel / acc
        elapsed = np.clip(elapsed, 0.0, total_time)
        traveled = np.where(
            elapsed <= accel_time,
            0.5 * acc * elapsed**2,
            np.where(
                elapsed < total_time - accel_time,
                accel_distance + vel * (elapsed - accel_time),
                distance - 0.5 * acc * (total_time - elapsed)**2,
            ),
        )
    else:
        accel_time = math.sqrt(distance / acc)
        total_time = 2 * accel_time
        elapsed = np.clip(elapsed, 0.0, total_time)
        traveled = np.where(
            elapsed <= accel_time,
            0.5 * acc * elapsed**2,
            distance - 0.5 * acc * (total_time - elapsed)**2,
        )
    return np.clip(traveled, 0.0, distance), float(total_time)


def analyze_ideal_horizontal_action(d, spec, vel, acc, time_scale=1.0):
    """Action-aligned error for one pyfii-completed, pure-horizontal move2."""
    name, start, target, command_s, next_command_s = spec
    start = np.asarray(start, float)
    target = np.asarray(target, float)
    delta = target - start
    distance = float(np.linalg.norm(delta))
    direction = delta / distance
    pos = np.column_stack([d["x"], d["y"], d["z"]])
    valid = physical_track_mask(d, loose=True)
    dt = np.diff(d["t"])
    step = np.diff(pos, axis=0)
    along_speed = (step @ direction) / np.where(dt <= 0, np.nan, dt)
    xy_speed = np.linalg.norm(step[:, :2], axis=1) / np.where(dt <= 0, np.nan, dt)
    pair_valid = valid[:-1] & valid[1:] & (np.linalg.norm(step, axis=1) <= 80)

    starts = np.where(
        pair_valid & (d["t"][:-1] >= command_s) &
        (d["t"][:-1] <= next_command_s + 0.8) & (along_speed > 15)
    )[0]
    if not len(starts):
        raise ValueError(f"cannot locate ideal action start: {name}")
    start_idx = int(starts[0])
    real_start_s = float(d["t"][start_idx])

    local = valid & (d["t"] >= real_start_s) & (d["t"] <= next_command_s + 0.8)
    candidates = np.where(local)[0]
    target_distance = np.linalg.norm(pos - target, axis=1)
    near_target_cm = max(15.0, 0.06 * distance)
    stop_candidates = np.where(
        local[:-1] & pair_valid & (target_distance[:-1] <= near_target_cm) &
        ((xy_speed <= 15.0) | (along_speed <= 0.0))
    )[0]
    if len(stop_candidates):
        end_idx = int(stop_candidates[0])
        end_detection = "first near-target low-speed/turn sample"
    else:
        end_idx = int(candidates[np.argmin(target_distance[candidates])])
        end_detection = "closest valid target sample fallback"
    real_end_s = float(d["t"][end_idx])

    _, model_duration = trapezoid_distance(distance, vel, acc, np.array([0.0]))
    # Compare the whole observed action. If the model arrives first, it remains
    # at the target while the real aircraft finishes the same action.
    model_window = valid & (d["t"] >= real_start_s) & (d["t"] <= real_end_s)
    model_idx = np.where(model_window)[0]
    model_elapsed = (d["t"][model_idx] - real_start_s) / time_scale
    modeled_distance, _ = trapezoid_distance(distance, vel, acc, model_elapsed)
    modeled_pos = start + modeled_distance[:, None] * direction
    position_residual = np.linalg.norm(pos[model_idx] - modeled_pos, axis=1)

    move_idx = np.where(valid & (d["t"] >= real_start_s) & (d["t"] <= real_end_s))[0]
    relative = pos[move_idx] - start
    progress = relative @ direction
    cross_track = np.linalg.norm(relative - progress[:, None] * direction, axis=1)
    speed_window = pair_valid & (d["t"][1:] >= real_start_s) & (d["t"][1:] <= real_end_s)

    return dict(
        action=name,
        start_cm=[float(value) for value in start],
        target_cm=[float(value) for value in target],
        distance_cm=round(distance, 1),
        real_start_s=round(real_start_s, 3),
        real_end_s=round(real_end_s, 3),
        end_detection=end_detection,
        end_neighborhood_cm=round(near_target_cm, 1),
        command_time_s=round(float(command_s), 3),
        next_command_time_s=round(float(next_command_s), 3),
        time_budget_s=round(float(next_command_s - command_s), 3),
        model_duration_s=round(model_duration, 3),
        model_completion_margin_s=round(float(next_command_s - command_s - model_duration), 3),
        real_duration_s=round(real_end_s - real_start_s, 3),
        duration_error_s=round(real_end_s - real_start_s - model_duration, 3),
        duration_ratio=round((real_end_s - real_start_s) / model_duration, 3),
        endpoint_error_3d_cm=round(float(target_distance[end_idx]), 1),
        cross_track_median_cm=round(float(np.median(cross_track)), 1),
        cross_track_p90_cm=round(float(np.percentile(cross_track, 90)), 1),
        observed_xy_speed_p90_cm_s=round(float(np.percentile(xy_speed[speed_window], 90)), 1),
        position_residual_median_cm=round(float(np.median(position_residual)), 1),
        position_residual_p90_cm=round(float(np.percentile(position_residual, 90)), 1),
        position_residual_rmse_cm=round(float(np.sqrt(np.mean(position_residual**2))), 1),
        _position_residual=position_residual,
        _elapsed_s=d["t"][move_idx] - real_start_s,
        _progress_cm=progress,
    )

def yaw_delta_deg(d, t0=32, t1=38):
    m = (d["t"] >= t0) & (d["t"] <= t1)
    if int(np.sum(m)) < 2:
        return None
    y = np.unwrap(np.deg2rad(d["yaw"][m])) * 180 / math.pi
    return round(float(y[-1] - y[0]), 1)

def summary_one_uav(d):
    default = default_pose_mask(d)
    ts, v = speed_samples(d)
    plausible = coord_valid(d)
    return dict(
        n=int(len(d["t"])),
        duration_s=round(float(d["t"][-1] - d["t"][0]), 2) if len(d["t"]) else 0,
        mode_counts=dict(collections.Counter(map(str, d["mode"]))),
        status_counts=dict(collections.Counter(map(str, d["status"]))),
        default_pose_samples=int(np.sum(default)),
        implausible_coord_samples=int(np.sum(~plausible)),
        speed_gt_250_samples=int(np.sum(v > 250)),
        max_sample_speed_cm_s=round(float(np.nanmax(v)), 1) if len(v) else 0,
        x_range=[round(float(np.nanmin(d["x"])), 1), round(float(np.nanmax(d["x"])), 1)],
        y_range=[round(float(np.nanmin(d["y"])), 1), round(float(np.nanmax(d["y"])), 1)],
        z_range=[round(float(np.nanmin(d["z"])), 1), round(float(np.nanmax(d["z"])), 1)],
    )

def paired_samples(flight, uid_a="98101", uid_b="98102"):
    by = load_by_uav(flight)
    if uid_a not in by or uid_b not in by:
        return []
    rows_by_ms = collections.defaultdict(dict)
    for uid in (uid_a, uid_b):
        for r in by[uid]["rows"]:
            rows_by_ms[int(float(r["elapsed_ms"]))][uid] = r
    pairs = []
    for ms in sorted(rows_by_ms):
        dd = rows_by_ms[ms]
        if uid_a not in dd or uid_b not in dd:
            continue
        a, b = dd[uid_a], dd[uid_b]
        pa = tuple(float(a[k]) for k in ("x_cm", "y_cm", "z_cm"))
        pb = tuple(float(b[k]) for k in ("x_cm", "y_cm", "z_cm"))
        xy = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
        dz = abs(pa[2] - pb[2])
        d3 = math.hypot(xy, dz)
        valid = (
            all(-100 <= v <= 500 for v in pa[:2]) and all(-100 <= v <= 500 for v in pb[:2]) and
            -20 <= pa[2] <= 260 and -20 <= pb[2] <= 260
        )
        pairs.append(dict(
            t=ms / 1000.0, xy=xy, dz=dz, d3=d3, valid=valid,
            mode_a=a["flightmode"], mode_b=b["flightmode"],
            status_a=a["fcstatus"], status_b=b["fcstatus"],
            default_a=math.dist(pa, tuple(DEFAULT_POSE)) <= 3.0,
            default_b=math.dist(pb, tuple(DEFAULT_POSE)) <= 3.0,
            pa=pa, pb=pb,
        ))
    return pairs

def first_separated_time(pairs):
    for p in pairs:
        if p["xy"] > 100 or p["dz"] > 30:
            return p["t"]
    return None

def safety_margin(p):
    # Safe iff same-height pairs have XY>=40 OR close-XY pairs have Z separation>=50.
    return max(p["xy"] - 40.0, p["dz"] - 50.0)

def summarize_safety(pairs, require_good=True):
    start = first_separated_time(pairs)
    if start is None:
        return dict(effective_start_s=None, samples=0)
    ps = [
        p for p in pairs
        if p["t"] >= start and p["valid"] and p["mode_a"] != "FLIP" and p["mode_b"] != "FLIP"
        and not (p["t"] > 2.0 and (p["default_a"] or p["default_b"]))
    ]
    if require_good:
        ps = [p for p in ps if p["mode_a"] == "GUIDED" and p["mode_b"] == "GUIDED" and p["status_a"] == "Good" and p["status_b"] == "Good"]
    if not ps:
        return dict(effective_start_s=round(start, 2), samples=0)
    margins = [safety_margin(p) for p in ps]
    violations = [p for p in ps if p["xy"] < 40 and p["dz"] < 50]
    low_dz = [p for p in ps if p["dz"] < 50]
    low_xy = [p for p in ps if p["xy"] < 40]
    min_xy = min(ps, key=lambda p: p["xy"])
    min_dz = min(ps, key=lambda p: p["dz"])
    min_3d = min(ps, key=lambda p: p["d3"])
    return dict(
        effective_start_s=round(start, 2),
        window_s=[round(ps[0]["t"], 2), round(ps[-1]["t"], 2)],
        samples=len(ps),
        violations=len(violations),
        min_margin_cm=round(float(min(margins)), 1),
        min_xy_cm=round(float(min_xy["xy"]), 1),
        min_xy_at_s=round(float(min_xy["t"]), 2),
        dz_at_min_xy_cm=round(float(min_xy["dz"]), 1),
        min_dz_cm=round(float(min_dz["dz"]), 1),
        xy_at_min_dz_cm=round(float(min_dz["xy"]), 1),
        min_3d_cm=round(float(min_3d["d3"]), 1),
        min_xy_when_dz_lt_50_cm=round(float(min(p["xy"] for p in low_dz)), 1) if low_dz else None,
        min_dz_when_xy_lt_40_cm=round(float(min(p["dz"] for p in low_xy)), 1) if low_xy else None,
    )

def repeat_distance(a, b, tmin=10, tmax=65):
    da, db = load_by_uav(a)["98101"], load_by_uav(b)["98101"]
    va = physical_track_mask(da, loose=True)
    vb = physical_track_mask(db, loose=True)
    lo = max(float(np.nanmin(da["t"][va])), float(np.nanmin(db["t"][vb])), tmin)
    hi = min(float(np.nanmax(da["t"][va])), float(np.nanmax(db["t"][vb])), tmax)
    tt = np.arange(lo, hi, 0.2)
    if len(tt) == 0:
        return {}
    ax = np.interp(tt, da["t"][va], da["x"][va]); ay = np.interp(tt, da["t"][va], da["y"][va]); az = np.interp(tt, da["t"][va], da["z"][va])
    bx = np.interp(tt, db["t"][vb], db["x"][vb]); byy = np.interp(tt, db["t"][vb], db["y"][vb]); bz = np.interp(tt, db["t"][vb], db["z"][vb])
    dxy = np.hypot(ax - bx, ay - byy)
    d3 = np.sqrt(dxy*dxy + (az - bz)**2)
    return dict(
        window_s=[round(lo, 1), round(hi, 1)],
        median_xy_cm=round(float(np.median(dxy)), 1),
        p90_xy_cm=round(float(np.percentile(dxy, 90)), 1),
        median_3d_cm=round(float(np.median(d3)), 1),
        p90_3d_cm=round(float(np.percentile(d3, 90)), 1),
        max_3d_cm=round(float(np.max(d3)), 1),
    )

def compare_uav_prefix(a, b, uid, tmin, tmax):
    da, db = load_by_uav(a)[uid], load_by_uav(b)[uid]
    va = physical_track_mask(da, loose=True)
    vb = physical_track_mask(db, loose=True)
    if not np.any(va) or not np.any(vb):
        return dict(samples=0)
    lo = max(float(np.nanmin(da["t"][va])), float(np.nanmin(db["t"][vb])), float(tmin))
    hi = min(float(np.nanmax(da["t"][va])), float(np.nanmax(db["t"][vb])), float(tmax))
    tt = np.arange(lo, hi, 0.2)
    if len(tt) == 0:
        return dict(samples=0, window_s=[round(lo, 2), round(hi, 2)])
    ax = np.interp(tt, da["t"][va], da["x"][va])
    ay = np.interp(tt, da["t"][va], da["y"][va])
    az = np.interp(tt, da["t"][va], da["z"][va])
    bx = np.interp(tt, db["t"][vb], db["x"][vb])
    by = np.interp(tt, db["t"][vb], db["y"][vb])
    bz = np.interp(tt, db["t"][vb], db["z"][vb])
    dxy = np.hypot(ax - bx, ay - by)
    d3 = np.hypot(dxy, az - bz)
    return dict(
        window_s=[round(lo, 2), round(hi, 2)],
        samples=int(len(tt)),
        median_xy_cm=round(float(np.median(dxy)), 1),
        p90_xy_cm=round(float(np.percentile(dxy, 90)), 1),
        median_3d_cm=round(float(np.median(d3)), 1),
        p90_3d_cm=round(float(np.percentile(d3, 90)), 1),
    )

print("Loaded modules OK")


import matplotlib.pyplot as plt

plt.rcParams.update({"figure.dpi":120,"font.size":10,"axes.grid":True,
                     "grid.alpha":0.3,"axes.axisbelow":True})
C_REAL="#e8543f"; C_MODEL="#2b6cb0"; C_CMD="#111"
metrics={}

# ============================================================ GRID (162500)
g = load("flight_20260709_162500")
cmds = route_grid(120,300,alt=120)
mt,mx,my,mz,wp = sim_route(cmds, start=(0,0,0))
gct,gcx,gcy,gcz,gcmd_warns,grid_handoffs = pyfii_grid_track(120,300,alt=120)
corners=[(320,40),(40,120),(320,200),(40,280)]
gl = clean_glitches(g['x'],g['y'],g['z'],60)

# Align by the first sustained horizontal motion. The inferred offset is used
# only to locate corresponding action handoffs, not as a global clock fit.
i_to=np.argmax(g['z']>25); t0_real=g['t'][i_to]
i_to_model=np.argmax(gcz>25); t0_model=gct[i_to_model]
grid_z_time_offset=t0_real-t0_model
grid_xy_time_real = first_xy_motion_time(g["t"], g["x"], g["y"], z=g["z"], min_t=4.5, min_z=80, threshold=20)
grid_xy_time_model = first_xy_motion_time(gct, gcx, gcy, threshold=20)
grid_xy_time_offset = (
    grid_xy_time_real - grid_xy_time_model
    if grid_xy_time_real is not None and grid_xy_time_model is not None
    else grid_z_time_offset
)

grid_interrupted_events = [
    event for event in grid_handoffs["events"]
    if not event["completed"]
]
gd = load_by_uav("flight_20260709_162500")["98101"]
grid_valid = (
    ((gd["mode"] == "GUIDED") | (gd["mode"] == "LAND")) &
    (gd["status"] == "Good") & coord_valid(gd) & ~default_pose_mask(gd) &
    ~clean_glitches(gd["x"], gd["y"], gd["z"], 80)
)
grid_turns = []
for corner, event in zip(corners, grid_interrupted_events):
    expected_stop = event["stop_time_s"] + grid_xy_time_offset
    local = grid_valid & (gd["t"] >= expected_stop - 0.8) & (gd["t"] <= expected_stop + 0.8)
    candidates = np.where(local)[0]
    distance = np.hypot(gd["x"] - corner[0], gd["y"] - corner[1])
    turn_idx = int(candidates[np.argmin(distance[candidates])])

    raw_step = np.linalg.norm(np.diff(np.column_stack([gd["x"], gd["y"], gd["z"]]), axis=0), axis=1)
    speed_t, speed_xy = xy_speed_series(gd["t"], gd["x"], gd["y"])
    speed_local = (speed_t >= expected_stop - 0.8) & (speed_t <= expected_stop + 0.8)
    pair_valid = grid_valid[1:] & grid_valid[:-1] & (raw_step > 0.01) & (raw_step <= 80)
    localization_contaminated = bool(np.any(speed_local & ((raw_step <= 0.01) | (raw_step > 80))))
    usable_speed = speed_xy[speed_local & pair_valid]
    min_speed = None if localization_contaminated or not len(usable_speed) else float(np.min(usable_speed))

    grid_turns.append(dict(
        target_cm=[float(corner[0]), float(corner[1]), 120.0],
        model_stop_time_s=event["stop_time_s"],
        expected_real_stop_s=round(float(expected_stop), 3),
        real_turn_time_s=round(float(gd["t"][turn_idx]), 3),
        min_observed_xy_speed_cm_s=round(min_speed, 1) if min_speed is not None else None,
        localization_contaminated=localization_contaminated,
    ))

# --- Fig 1: XY top view ---
fig,ax=plt.subplots(figsize=(7.2,6.6))
ax.plot(mx,my,'-',color=C_MODEL,lw=2.2,label="pyfii 几何基线 (直线到航点)",zorder=3)
ax.plot(gcx,gcy,'--',color="#1a202c",lw=1.5,label="pyfii 提前打断基线 (制动后换段)",zorder=3)
# Real path: keep only physically interpretable samples so post-land AprilTag
# failures do not draw lines through unrelated coordinates.
xr=g['x'].copy(); yr=g['y'].copy()
seg_x=np.where(grid_valid,np.asarray(gd["x"]),np.nan)
seg_y=np.where(grid_valid,np.asarray(gd["y"]),np.nan)
ax.plot(seg_x,seg_y,'-',color=C_REAL,lw=2.2,label="真实飞行",zorder=4)
ax.scatter([c[0] for c in corners],[c[1] for c in corners],s=140,marker='*',
           color=C_CMD,zorder=5,label="指令航点")
annotation_offsets = [(-52, 10), (10, 10), (-52, 10), (10, -18)]
for idx, ((cx,cy), turn, offset) in enumerate(zip(corners, grid_turns, annotation_offsets), start=1):
    ax.annotate(
        f"打断 {idx}",
        (cx,cy), xytext=offset, textcoords="offset points", fontsize=8, color=C_CMD,
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.72, pad=1.0),
    )
ax.scatter([22],[24],s=60,color='green',zorder=6,label="真实起点(22,24)≠(0,0)")
ax.set_xlabel("X (cm)"); ax.set_ylabel("Y (cm)")
ax.set_title("网格航线 俯视图：pyfii 模型 vs 真实飞行 (162500)")
ax.legend(loc="upper left",fontsize=8.5); ax.set_aspect('equal')
ax.set_xlim(-20,360); ax.set_ylim(-20,360)
plt.tight_layout(); plt.savefig(f"{OUT}/fig1_grid_completion_conditions.png"); plt.close()

# --- Fig 2: Z vs time (align takeoff) ---
fig,ax=plt.subplots(figsize=(8,3.6))
ax.plot(gct+grid_z_time_offset, gcz,color=C_MODEL,lw=2,label="pyfii 指令时序基线 Z")
ax.plot(g['t'], g['z'], color=C_REAL,lw=2,label="真实 Z")
ax.scatter(g['t'][gl],g['z'][gl],s=25,color='orange',zorder=5,label="定位跳变")
ax.set_xlabel("时间 (s)"); ax.set_ylabel("Z 高度 (cm)")
ax.set_title("高度剖面：起飞—巡航—降落 (162500)")
ax.legend(fontsize=8.5); plt.tight_layout()
plt.savefig(f"{OUT}/fig2_grid_z.png"); plt.close()

# --- Fig 3: horizontal speed vs time ---
gcts,gcv = xy_speed_series(gct,gcx,gcy)
real_xy_motion_start = grid_xy_time_real if grid_xy_time_real is not None else 3.5
speed_ok = (
    ((gd["mode"] == "GUIDED") | (gd["mode"] == "LAND")) &
    (gd["status"] == "Good") &
    coord_valid(gd) &
    (gd["t"] >= real_xy_motion_start) &
    ~default_pose_mask(gd) &
    ~clean_glitches(gd["x"], gd["y"], gd["z"], 80)
)
sx = np.where(speed_ok, gd["x"], np.nan)
sy = np.where(speed_ok, gd["y"], np.nan)
sz = np.where(speed_ok, gd["z"], np.nan)
rts,rv_clean = xy_speed_series(gd["t"], sx, sy)
rv_clean[rv_clean > 220] = np.nan
# The third handoff overlaps an AprilTag freeze/jump, so it is excluded from
# the evidence about whether the aircraft reached zero horizontal speed.
third_stop = grid_turns[2]["expected_real_stop_s"]
third_bad = (rts >= third_stop - 1.2) & (rts <= third_stop + 0.8)
rv_clean[third_bad] = np.nan
fig,ax=plt.subplots(figsize=(8,3.6))
ax.plot(gcts+grid_xy_time_offset,gcv,color=C_MODEL,lw=1.8,label="pyfii 非理想基线 (梯形+打断制动)")
ax.plot(rts,rv_clean,color=C_REAL,lw=1.8,label="真实水平速度 (平滑)")
for idx, event in enumerate(grid_interrupted_events):
    ax.axvspan(
        event["command_time_s"] + grid_xy_time_offset,
        event["stop_time_s"] + grid_xy_time_offset,
        color="#d69e2e", alpha=0.18,
        label="pyfii 强制制动窗口" if idx == 0 else None,
    )
ax.axvspan(third_stop - 1.2, third_stop + 0.8, color="#718096", alpha=0.14,
           label="AprilTag 停帧/跳变：不判定速度")
ax.axhline(120,ls='--',color='gray',lw=1,label="配置 MaxVelXY=120")
ax.set_ylim(0,220); ax.set_xlabel("时间 (s)"); ax.set_ylabel("速度 (cm/s)")
ax.set_title("非理想动作：pyfii 打断制动与真实转向减速 (162500)")
ax.legend(fontsize=8.5,ncol=2); plt.tight_layout()
plt.savefig(f"{OUT}/fig3_grid_action_speed.png"); plt.close()

# grid metrics: this run is outside ideal-model error fitting; keep only the
# interruption classification and observable deceleration evidence.
metrics['grid']=dict(model_dur=float(mt[-1]),real_dur=float(g['t'][-1]),
    command_timed_model_dur=float(gct[-1]),
    command_time_offset=round(float(grid_z_time_offset),3),
    command_z_time_offset=round(float(grid_z_time_offset),3),
    command_xy_time_offset=round(float(grid_xy_time_offset),3),
    real_first_xy_motion_s=round(float(grid_xy_time_real),3) if grid_xy_time_real is not None else None,
    model_first_xy_motion_s=round(float(grid_xy_time_model),3) if grid_xy_time_model is not None else None,
    command_timed_warning_frame_count=len(gcmd_warns),
    completed_handoffs=grid_handoffs["completed_handoffs"],
    interrupted_handoffs=grid_handoffs["interrupted_handoffs"],
    excluded_from_model_error=True,
    exclusion_reason="all four horizontal moves are interrupted under pyfii timing",
    turn_events=grid_turns,
    n_glitch=int(gl.sum()),start_offset_cm=round(float(np.hypot(22,24)),1))

# ============================================================ COMPLEX (162913)
c = load("flight_20260709_162913")
cl = clean_glitches(c['x'],c['y'],c['z'],70)
# full route: grid -> spiral -> zstairs -> rectangle  (acc 400; grid vel100)
cmds2 = (route_grid(100,400,alt=120)+route_spiral(400)+route_zstairs(400)+route_rectangle(400))
mt2,mx2,my2,mz2,wp2 = sim_route(cmds2,start=(0,0,0))
ct2,cx2,cy2,cz2,cwarns2,complex_handoffs = pyfii_complex_track()

# --- Fig 4: complex XY path ---
fig,ax=plt.subplots(figsize=(7.4,6.8))
ax.plot(mx2,my2,'-',color=C_MODEL,lw=1.4,alpha=0.85,label="pyfii 几何基线(全程)")
ax.plot(cx2,cy2,'--',color="#1a202c",lw=1.1,alpha=0.75,label="pyfii 指令时序基线")
xr=np.where(cl,np.nan,c['x']); yr=np.where(cl,np.nan,c['y'])
ax.plot(xr,yr,'-',color=C_REAL,lw=1.6,label="真实飞行(全程)")
ax.set_xlabel("X (cm)"); ax.set_ylabel("Y (cm)")
ax.set_title("复合航线 俯视图：网格+螺旋+阶梯+矩形 (162913)")
ax.legend(fontsize=9); ax.set_aspect('equal')
plt.tight_layout(); plt.savefig(f"{OUT}/fig4_complex_xy.png"); plt.close()

# --- Fig 5: z-stairs vertical speed (VelZ ignored) -- real data only, avoid timeline mismatch ---
vz=np.abs(np.diff(c['z'])/np.diff(c['t']))
fig,ax=plt.subplots(2,1,figsize=(8,5.4),sharex=True)
ax[0].axvspan(50,59,color='gold',alpha=0.15,label="阶梯高度段")
ax[0].plot(c['t'],c['z'],color=C_REAL,lw=1.6,label="真实 Z")
ax[0].set_ylabel("Z (cm)"); ax[0].legend(fontsize=8.5,loc="upper left")
ax[0].set_title("复合航线 高度与垂直速度：真实数据 (162913)")
ax[1].axvspan(50,59,color='gold',alpha=0.15)
ax[1].plot(c['t'][1:],vz,color=C_REAL,lw=1.2,label="真实 |vZ|")
ax[1].axhline(60,ls='--',color='green',lw=1.2,label="配置 MaxVelZ=60")
ax[1].axhline(50,ls='-',color=C_MODEL,lw=1.2,label="pyfii 用 VelXY=50 建模垂直")
ax[1].axhline(30,ls=':',color='purple',lw=1.2,label="slow VelZ=30")
ax[1].set_ylabel("|vZ| (cm/s)"); ax[1].set_xlabel("时间 (s)")
ax[1].set_ylim(0,160); ax[1].legend(fontsize=8,ncol=2,loc="upper left")
ax[1].annotate("起飞/降落定位跳变尖峰",(6,150),(15,140),fontsize=8,
               arrowprops=dict(arrowstyle="->",color='gray'))
plt.tight_layout(); plt.savefig(f"{OUT}/fig5_zstairs.png"); plt.close()

# --- Fig 6: glitch / noise characterization ---
allv=[]
fig,ax=plt.subplots(figsize=(8,3.6))
for f,name,col in [("flight_20260709_162500","162500 grid","#e8543f"),
                   ("flight_20260709_162913","162913 complex","#2b6cb0"),
                   ("flight_20260709_163106","163106 complex","#38a169")]:
    d=load(f); ts,v=speed_series(d['t'],d['x'],d['y'],d['z']); allv.append(v)
    ax.plot(ts,v,lw=1.1,color=col,alpha=0.8,label=name)
ax.axhline(200,ls='--',color='gray',label="物理上限≈200cm/s")
ax.set_yscale('log'); ax.set_xlabel("时间 (s)"); ax.set_ylabel("采样间速度 (cm/s, log)")
ax.set_title("真实数据中的定位跳变：单帧速度尖峰 (>1000cm/s 物理不可能)")
ax.legend(fontsize=8.5,ncol=2); plt.tight_layout()
plt.savefig(f"{OUT}/fig6_glitches.png"); plt.close()

# complex metrics
allv=np.concatenate(allv)
metrics['complex']=dict(model_dur=float(mt2[-1]),real_dur=float(c['t'][-1]),
    command_timed_model_dur=float(ct2[-1]),
    command_timed_warning_frame_count=len(cwarns2),
    completed_handoffs=complex_handoffs["completed_handoffs"],
    interrupted_handoffs=complex_handoffs["interrupted_handoffs"],
    command_timed_note="fwfii z-stairs starts at z=60; pyfii Drone range rejects 60, so command baseline clamps it to 80",
    n_glitch_162913=int(cl.sum()),
    glitch_pct=round(100*float(cl.sum())/len(cl),1),
    vz_max_real=round(float(np.nanmax(vz)),0))
metrics['noise']=dict(
    frac_speed_gt_250=round(100*float(np.mean(allv>250)),1),
    max_speed_spike=round(float(np.nanmax(allv)),0))

# z-stairs real vertical climb rate: isolate the staircase window (x,y near 180, z rising)
zwin=(c['t'][1:]>50)&(c['t'][1:]<59)
climb=vz[zwin & (vz>12) & (vz<80)]   # active-climb frames, drop glitches
metrics['vertical']=dict(
    real_climb_cm_s=[round(float(np.percentile(climb,25)),0),
                     round(float(np.median(climb)),0),
                     round(float(np.percentile(climb,75)),0)] if len(climb) else [],
    pyfii_vertical_vel=50.0,   # z-stairs sets VelXY=50; pyfii uses it for vertical (VelZ ignored)
    config_MaxVelZ=[30,60],
    note="pyfii ignores VelZ/AccZ -> vertical moves use last VelXY; here 50 vs real ~25-44")

# ============================================================ UPDATED LOGS: CLEANING, SWARM, REPEATABILITY
all_flights = sorted(
    d for d in os.listdir(LOGDIR)
    if os.path.exists(os.path.join(LOGDIR, d, "telemetry.csv"))
)
swarm_flights = [
    f for f in all_flights
    if os.path.exists(os.path.join(LOGDIR, f, "swarm_dance.py"))
]
repeat_flights = [
    "flight_20260709_162913",
    "flight_20260709_163106",
    "flight_20260709_180602",
]

def cleaning_counts(d):
    default_airborne = default_pose_mask(d) & (d["t"] > 2.0)
    jump = clean_glitches(d["x"], d["y"], d["z"], 80)
    physical = physical_track_mask(d, loose=True)
    return dict(
        raw_samples=int(len(d["t"])),
        physical_samples=int(np.sum(physical)),
        dropped_samples=int(len(d["t"]) - np.sum(physical)),
        default_pose_after_2s=int(np.sum(default_airborne)),
        implausible_coord=int(np.sum(~coord_valid(d, loose=True))),
        single_frame_jump=int(np.sum(jump)),
        non_good_status=int(np.sum(d["status"] != "Good")),
        non_guided_mode=int(np.sum(d["mode"] != "GUIDED")),
    )

inventory = {}
cleaning = {}
for flight in all_flights:
    inventory[flight] = {}
    cleaning[flight] = {}
    for uid, d in load_by_uav(flight).items():
        inventory[flight][uid] = summary_one_uav(d)
        cleaning[flight][uid] = cleaning_counts(d)
metrics["log_inventory"] = inventory
metrics["cleaning"] = cleaning

failure_prefix = {}
for flight in ["flight_20260709_173818", "flight_20260709_173926", "flight_20260709_175805"]:
    failure_prefix[flight] = {}
    for uid, d in load_by_uav(flight).items():
        implausible = ~coord_valid(d)
        critical = (
            (d["mode"] == "FLIP") |
            (d["status"] == "Dead Battery") |
            (d["status"] == "N/A") |
            implausible
        )
        failure_prefix[flight][uid] = dict(
            first_critical_s=first_event_time(d, critical),
            first_flip_s=first_event_time(d, d["mode"] == "FLIP"),
            first_dead_battery_s=first_event_time(d, d["status"] == "Dead Battery"),
            first_non_good_s=first_event_time(d, d["status"] != "Good"),
            first_implausible_s=first_event_time(d, implausible),
            first_land_s=first_event_time(d, d["mode"] == "LAND"),
        )
metrics["failure_prefix"] = failure_prefix

# --- Fig 7: cleaned swarm XY paths (normal duet + later light/flip run) ---
swarm_command_tracks = {
    "flight_20260709_171502": pyfii_swarm_tracks("171502"),
    "flight_20260709_175214": pyfii_swarm_tracks("175214"),
}
metrics["swarm_pyfii_action_handoffs"] = {
    flight: {
        "98101": {
            "completed": tracks[0][5]["completed_handoffs"],
            "interrupted": tracks[0][5]["interrupted_handoffs"],
            "warning_frames": tracks[0][5]["warning_frame_count"],
        },
        "98102": {
            "completed": tracks[1][5]["completed_handoffs"],
            "interrupted": tracks[1][5]["interrupted_handoffs"],
            "warning_frames": tracks[1][5]["warning_frame_count"],
        },
    }
    for flight, tracks in swarm_command_tracks.items()
}

# Ideal-model error uses only pyfii-completed, pure-horizontal actions whose
# real start/end can be identified independently. Interrupted and 3D actions are
# intentionally excluded from every residual and calibration metric.
ideal_specs = {
    "动作1": ("动作1", (40, 40, 100), (40, 320, 100), 11.0, 15.0),
    "动作2": ("动作2", (40, 320, 100), (320, 40, 100), 15.0, 19.0),
    "动作3": ("动作3", (320, 40, 100), (180, 180, 100), 19.0, 22.0),
}
# The first move is identical and ideal-complete in four runs. Failures in
# 173926/175805 do not contaminate the selected physical window of 98101.
ideal_action_cases = [
    ("flight_20260709_171502", "171502-动作1", ideal_specs["动作1"]),
    ("flight_20260709_173926", "173926-动作1", ideal_specs["动作1"]),
    ("flight_20260709_175214", "175214-动作1", ideal_specs["动作1"]),
    ("flight_20260709_175805", "175805-动作1", ideal_specs["动作1"]),
    ("flight_20260709_171502", "171502-动作2", ideal_specs["动作2"]),
    ("flight_20260709_171502", "171502-动作3", ideal_specs["动作3"]),
]
ideal_data = {
    flight: load_by_uav(flight)["98101"]
    for flight in {case[0] for case in ideal_action_cases}
}

def analyze_ideal_case(case, time_scale=1.0):
    flight, sample, spec = case
    result = analyze_ideal_horizontal_action(
        ideal_data[flight], spec, 150, 300, time_scale=time_scale
    )
    result["flight"] = flight.removeprefix("flight_20260709_")
    result["sample"] = sample
    return result

ideal_raw = [analyze_ideal_case(case) for case in ideal_action_cases]
model_durations = np.array([item["model_duration_s"] for item in ideal_raw], float)
real_durations = np.array([item["real_duration_s"] for item in ideal_raw], float)
time_scale = float(np.dot(model_durations, real_durations) / np.dot(model_durations, model_durations))
ideal_scaled = [analyze_ideal_case(case, time_scale=time_scale) for case in ideal_action_cases]
raw_position_residual = np.concatenate([item.pop("_position_residual") for item in ideal_raw])
scaled_position_residual = np.concatenate([item.pop("_position_residual") for item in ideal_scaled])
ideal_progress = [
    (item.pop("_elapsed_s"), item.pop("_progress_cm"))
    for item in ideal_raw
]
for item in ideal_scaled:
    item.pop("_elapsed_s")
    item.pop("_progress_cm")
for raw, scaled in zip(ideal_raw, ideal_scaled):
    raw["scaled_model_duration_s"] = round(raw["model_duration_s"] * time_scale, 3)
    raw["scaled_duration_error_s"] = round(
        raw["real_duration_s"] - raw["scaled_model_duration_s"], 3
    )
    raw["scaled_completion_margin_s"] = round(
        raw["time_budget_s"] - raw["scaled_model_duration_s"], 3
    )
    raw["scaled_position_residual_median_cm"] = scaled["position_residual_median_cm"]
    raw["scaled_position_residual_p90_cm"] = scaled["position_residual_p90_cm"]
    raw["scaled_position_residual_rmse_cm"] = scaled["position_residual_rmse_cm"]

flight_ids = np.array([item["flight"] for item in ideal_raw])
leave_one_flight_errors = []
leave_one_flight_scales = {}
for flight in sorted(set(flight_ids)):
    keep = flight_ids != flight
    left_out = ~keep
    loo_scale = float(
        np.dot(model_durations[keep], real_durations[keep]) /
        np.dot(model_durations[keep], model_durations[keep])
    )
    leave_one_flight_scales[flight] = round(loo_scale, 3)
    leave_one_flight_errors.extend(
        model_durations[left_out] * loo_scale - real_durations[left_out]
    )

metrics["ideal_model_error"] = {
    "flights": sorted(set(flight_ids)),
    "uavid": "98101",
    "selection": "pyfii-completed, pure-horizontal move2, independently observable real action boundary",
    "position_residual_definition": "per-action start-time aligned 3D error from the scripted start over the observed action; model holds at target after arrival",
    "action_end_definition": "first near-target sample with observed low speed or turn; closest-target fallback only",
    "fit_method": "least-squares duration time scale through the origin",
    "telemetry_rate_hz_approx": 5,
    "completion_margin_uncertainty_s": 0.2,
    "selected_action_count": len(ideal_raw),
    "unique_motion_count": len(ideal_specs),
    "repeated_action1_count": 4,
    "selected_window_notes": {
        "173926": "selected action precedes 98101 FLIP localization failure",
        "175805": "selected 98101 action is physically valid; failed 98102 is not used",
    },
    "excluded_from_fit": [
        "takeoff",
        "moves with vertical displacement",
        "moves without an independently observable boundary",
        "all interrupted moves",
    ],
    "configured_vel_cm_s": 150,
    "configured_acc_cm_s2": 300,
    "min_model_completion_margin_s": round(float(min(
        item["model_completion_margin_s"] for item in ideal_raw
    )), 3),
    "selected_actions": ideal_raw,
    "scaled_marginal_action_count": sum(
        abs(item["scaled_completion_margin_s"]) <= 0.2 for item in ideal_raw
    ),
    "duration_time_scale": round(time_scale, 3),
    "duration_rmse_s": round(float(np.sqrt(np.mean((real_durations - model_durations)**2))), 3),
    "scaled_duration_rmse_s": round(float(np.sqrt(np.mean((real_durations - model_durations * time_scale)**2))), 3),
    "leave_one_flight_scales": leave_one_flight_scales,
    "leave_one_flight_max_abs_duration_error_s": round(float(np.max(np.abs(leave_one_flight_errors))), 3),
    "equivalent_vel_cm_s": round(150 / time_scale, 1),
    "equivalent_acc_cm_s2": round(300 / time_scale**2, 1),
    "cross_track_p90_median_cm": round(float(np.median([item["cross_track_p90_cm"] for item in ideal_raw])), 1),
    "raw_position_residual_median_cm": round(float(np.median(raw_position_residual)), 1),
    "raw_position_residual_p90_cm": round(float(np.percentile(raw_position_residual, 90)), 1),
    "raw_position_residual_rmse_cm": round(float(np.sqrt(np.mean(raw_position_residual**2))), 1),
    "scaled_position_residual_median_cm": round(float(np.median(scaled_position_residual)), 1),
    "scaled_position_residual_p90_cm": round(float(np.percentile(scaled_position_residual, 90)), 1),
    "scaled_position_residual_rmse_cm": round(float(np.sqrt(np.mean(scaled_position_residual**2))), 1),
}
metrics["nonideal_condition"] = {
    "flight": "flight_20260709_162500",
    "interrupted_handoffs": grid_handoffs["interrupted_handoffs"],
    "warning_frames": grid_handoffs["warning_frame_count"],
    "excluded_from_model_error": True,
    "reason": "outside pyfii ideal completion scope",
}

# --- Fig 11: ideal-model timing, residual, and trapezoid-integral fit only ---
condition_fig = plt.figure(figsize=(13.5, 8.0))
condition_grid = condition_fig.add_gridspec(2, 3, height_ratios=[1.0, 0.95])
duration_ax = condition_fig.add_subplot(condition_grid[0, :2])
residual_ax = condition_fig.add_subplot(condition_grid[0, 2])
action_x = np.arange(len(ideal_raw))
width = 0.25
duration_ax.bar(action_x - width, model_durations, width=width, color=C_MODEL, label="pyfii 原始时长")
duration_ax.bar(action_x, model_durations * time_scale, width=width, color="#d69e2e",
                label=f"时间缩放 {time_scale:.2f}x")
duration_ax.bar(action_x + width, real_durations, width=width, color=C_REAL, label="真实时长")
duration_ax.set_xticks(action_x)
duration_ax.set_xticklabels([item["sample"] for item in ideal_raw], rotation=25, ha="right", fontsize=8)
duration_ax.set_ylabel("动作时长 (s)")
duration_ax.set_title("仅完整纯水平动作：梯形时长")
duration_ax.legend(fontsize=8)

raw_median = [item["position_residual_median_cm"] for item in ideal_raw]
scaled_median = [item["scaled_position_residual_median_cm"] for item in ideal_raw]
cross_p90 = [item["cross_track_p90_cm"] for item in ideal_raw]
residual_ax.bar(action_x - width / 2, raw_median, width=width, color=C_MODEL,
                label="原始残差中位数")
residual_ax.bar(action_x + width / 2, scaled_median, width=width, color="#d69e2e",
                label="缩放后残差中位数")
residual_ax.plot(action_x, cross_p90, "o--", color="#2f855a", lw=1.2,
                 label="横向误差 P90")
residual_ax.set_xticks(action_x)
residual_ax.set_xticklabels([item["sample"] for item in ideal_raw], rotation=35, ha="right", fontsize=7)
residual_ax.set_ylabel("位置误差 (cm)")
residual_ax.set_title("动作起步对齐后的误差")
residual_ax.legend(fontsize=7.5)

fit_groups = [
    ("动作1复飞：280 cm", [0, 1, 2, 3]),
    ("动作2：396 cm", [4]),
    ("动作3：198 cm", [5]),
]
repeat_colors = ["#e8543f", "#805ad5", "#319795", "#dd6b20"]
for idx, (title, sample_indices) in enumerate(fit_groups):
    fit_ax = condition_fig.add_subplot(condition_grid[1, idx])
    item = ideal_raw[sample_indices[0]]
    max_duration = max(ideal_raw[sample_idx]["real_duration_s"] for sample_idx in sample_indices)
    fit_t = np.linspace(0.0, max_duration, 300)
    raw_fit, _ = trapezoid_distance(item["distance_cm"], 150, 300, fit_t)
    scaled_fit, _ = trapezoid_distance(
        item["distance_cm"], 150, 300, fit_t / time_scale
    )
    fit_ax.plot(fit_t, raw_fit, "--", lw=1.5, color=C_MODEL,
                label="原始梯形积分")
    fit_ax.plot(fit_t, scaled_fit, "-", lw=1.5, color="#d69e2e",
                label="时间缩放后")
    for color_idx, sample_idx in enumerate(sample_indices):
        real_elapsed, real_progress = ideal_progress[sample_idx]
        sample = ideal_raw[sample_idx]
        color = repeat_colors[color_idx] if len(sample_indices) > 1 else C_REAL
        label = sample["flight"] if len(sample_indices) > 1 else "真实沿程位置"
        fit_ax.plot(real_elapsed, real_progress, "o-", ms=3.0, lw=1.1,
                    color=color, alpha=0.9, label=label)
    fit_ax.set_xlabel("动作内时间 (s)")
    fit_ax.set_ylabel("沿程位移 (cm)")
    fit_ax.set_title(title)
    fit_ax.legend(fontsize=7 if idx == 0 else 7.5)
condition_fig.tight_layout()
condition_fig.savefig(f"{OUT}/fig11_ideal_model_error.png"); plt.close(condition_fig)

metrics["swarm_pyfii_baseline_safety"] = {}
for flight, tracks in swarm_command_tracks.items():
    itt, ixy, idz, id3 = paired_distance_from_tracks(*tracks)
    metrics["swarm_pyfii_baseline_safety"][flight] = summarize_safety_arrays(itt, ixy, idz, id3)
fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), sharex=True, sharey=True)
for ax, flight, title in zip(
    axes,
    ["flight_20260709_171502", "flight_20260709_175214"],
    ["171502 双机安全版：真实 vs pyfii基线", "175214 灯光+空翻版：真实 vs pyfii基线"],
):
    by = load_by_uav(flight)
    for uid, col, name in [("98101", "#e8543f", "98101"), ("98102", "#2b6cb0", "98102")]:
        d = by[uid]
        m = physical_track_mask(d, allow_flip=False, loose=True)
        ax.plot(np.where(m, d["x"], np.nan), np.where(m, d["y"], np.nan),
                lw=2.0, color=col, label=name)
        dp = default_pose_mask(d) & (d["t"] > 2.0)
        if np.any(dp):
            ax.scatter(d["x"][dp], d["y"][dp], s=10, color="0.55", alpha=0.35, marker="x")
    for track, col in zip(swarm_command_tracks[flight], ["#e8543f", "#2b6cb0"]):
        it, ix, iy, iz = track[:4]
        ax.plot(ix, iy, "--", lw=1.4, color=col, alpha=0.65, label="pyfii基线")
    ax.scatter([40, 320], [40, 40], s=55, c=["#e8543f", "#2b6cb0"], marker="s", label="脚本起点")
    ax.set_title(title)
    ax.set_xlabel("X (cm)")
    ax.set_ylabel("Y (cm)")
    ax.set_aspect("equal")
    ax.set_xlim(-20, 360); ax.set_ylim(-20, 360)
    ax.legend(fontsize=8, loc="upper right")
plt.tight_layout()
plt.savefig(f"{OUT}/fig7_swarm_clean_xy.png"); plt.close()

# --- Fig 8: real separation after cleaning ---
fig, axes = plt.subplots(2, 1, figsize=(9, 6.4), sharex=False)
for ax, flight, title in zip(
    axes,
    ["flight_20260709_171502", "flight_20260709_175214"],
    ["171502 双机间距（Good/GUIDED/非默认位姿）", "175214 双机间距（Good/GUIDED/非默认位姿）"],
):
    pairs = paired_samples(flight)
    start = first_separated_time(pairs) or 0.0
    ps = [
        p for p in pairs
        if p["t"] >= start and p["valid"] and p["mode_a"] == "GUIDED" and p["mode_b"] == "GUIDED"
        and p["status_a"] == "Good" and p["status_b"] == "Good"
        and not (p["t"] > 2.0 and (p["default_a"] or p["default_b"]))
    ]
    t = [p["t"] for p in ps]
    xy = [p["xy"] for p in ps]
    dz = [p["dz"] for p in ps]
    ax.plot(t, xy, color="#2b6cb0", lw=1.8, label="XY 距离")
    ax.plot(t, dz, color="#e8543f", lw=1.8, label="Z 差")
    itt, ixy, idz, _ = paired_distance_from_tracks(*swarm_command_tracks[flight])
    ideal_start = first_separated_time_arrays(itt, ixy, idz)
    if ideal_start is not None:
        aligned_t = itt + (start - ideal_start)
        ax.plot(aligned_t, ixy, "--", color="#2b6cb0", lw=1.0, alpha=0.65, label="pyfii XY")
        ax.plot(aligned_t, idz, "--", color="#e8543f", lw=1.0, alpha=0.65, label="pyfii Z差")
    ax.axhline(40, color="#2b6cb0", ls=":", lw=1, label="XY 阈值 40")
    ax.axhline(50, color="#e8543f", ls=":", lw=1, label="Z 阈值 50")
    ax.axvline(start, color="0.35", ls="--", lw=1, label="有效编队窗口起点")
    ax.set_ylim(0, 330)
    ax.set_ylabel("cm")
    ax.set_title(title)
    ax.legend(fontsize=8, ncol=3, loc="upper right")
axes[-1].set_xlabel("时间 (s)")
plt.tight_layout()
plt.savefig(f"{OUT}/fig8_swarm_separation.png"); plt.close()

swarm_metrics = {}
for flight in swarm_flights:
    pairs = paired_samples(flight)
    swarm_metrics[flight] = dict(
        safety_clean_good=summarize_safety(pairs, require_good=True),
        safety_clean_all_status=summarize_safety(pairs, require_good=False),
    )
metrics["swarm_safety"] = swarm_metrics
metrics["failure_prefix_analysis"] = {
    "note": "Failure logs are segmented by first critical event; prefixes are compared to the successful 175214 light+flip run where the script family is comparable but not byte-identical.",
    "prefix_safety": {
        "flight_20260709_173818": swarm_metrics["flight_20260709_173818"]["safety_clean_good"],
        "flight_20260709_173926_pre_flip": swarm_metrics["flight_20260709_173926"]["safety_clean_good"],
        "flight_20260709_175805_pre_battery": swarm_metrics["flight_20260709_175805"]["safety_clean_good"],
    },
    "prefix_vs_success_175214": {
        "173926_98101_pre_flip": compare_uav_prefix(
            "flight_20260709_173926", "flight_20260709_175214", "98101", 10.0, 41.9
        ),
        "173926_98102_pre_flip": compare_uav_prefix(
            "flight_20260709_173926", "flight_20260709_175214", "98102", 10.0, 41.9
        ),
        "175805_98101_same_prefix": compare_uav_prefix(
            "flight_20260709_175805", "flight_20260709_175214", "98101", 10.0, 41.9
        ),
        "175805_98102_before_battery": compare_uav_prefix(
            "flight_20260709_175805", "flight_20260709_175214", "98102", 10.0, 12.48
        ),
    },
}

# --- Fig 9: repeatability of the complex route, after AprilTag cleaning ---
def interp_track(flight, uid="98101"):
    d = load_by_uav(flight)[uid]
    m = physical_track_mask(d, loose=True)
    return d["t"][m], d["x"][m], d["y"][m], d["z"][m]

fig, axes = plt.subplots(1, 2, figsize=(12, 5.2))
colors = {
    "flight_20260709_162913": "#2b6cb0",
    "flight_20260709_163106": "#38a169",
    "flight_20260709_180602": "#805ad5",
}
labels = {
    "flight_20260709_162913": "162913",
    "flight_20260709_163106": "163106",
    "flight_20260709_180602": "180602",
}
tracks = {}
for flight in repeat_flights:
    t, x, y, z = interp_track(flight)
    tracks[flight] = (t, x, y, z)
    axes[0].plot(x, y, lw=1.6, color=colors[flight], label=labels[flight])
axes[0].set_title("复合航线三次复飞：清洗后 XY")
axes[0].set_xlabel("X (cm)"); axes[0].set_ylabel("Y (cm)")
axes[0].set_aspect("equal"); axes[0].legend(fontsize=8)
for a, b in [
    ("flight_20260709_162913", "flight_20260709_163106"),
    ("flight_20260709_162913", "flight_20260709_180602"),
    ("flight_20260709_163106", "flight_20260709_180602"),
]:
    ta, xa, ya, za = tracks[a]
    tb, xb, yb, zb = tracks[b]
    lo = max(float(ta.min()), float(tb.min()), 10.0)
    hi = min(float(ta.max()), float(tb.max()), 65.0)
    tt = np.arange(lo, hi, 0.2)
    if len(tt) == 0:
        continue
    d3 = np.sqrt(
        (np.interp(tt, ta, xa) - np.interp(tt, tb, xb))**2 +
        (np.interp(tt, ta, ya) - np.interp(tt, tb, yb))**2 +
        (np.interp(tt, ta, za) - np.interp(tt, tb, zb))**2
    )
    axes[1].plot(tt, d3, lw=1.4, label=f"{labels[a]} vs {labels[b]}")

axes[1].set_title("相同程序复飞之间的 3D 轨迹差")
axes[1].set_xlabel("时间 (s)"); axes[1].set_ylabel("距离 (cm)")
axes[1].set_ylim(0, 90); axes[1].legend(fontsize=8)
plt.tight_layout()
plt.savefig(f"{OUT}/fig9_repeatability_only.png"); plt.close()

metrics["repeatability_clean"] = {
    f"{a}_vs_{b}": repeat_distance(a, b)
    for a, b in [
        ("flight_20260709_162913", "flight_20260709_163106"),
        ("flight_20260709_162913", "flight_20260709_180602"),
        ("flight_20260709_163106", "flight_20260709_180602"),
    ]
}
# --- Fig 10: cleaning flags by log/uav ---
fig, ax = plt.subplots(figsize=(11.5, 5.6))
labels_bar = []
vals_default = []
vals_status = []
vals_implausible = []
vals_jump = []
for flight in all_flights:
    short = flight.replace("flight_20260709_", "")
    for uid, d in load_by_uav(flight).items():
        labels_bar.append(f"{short}-{uid[-1]}")
        vals_default.append(int(np.sum(default_pose_mask(d) & (d["t"] > 2.0))))
        vals_status.append(int(np.sum((d["status"] != "Good") | (d["mode"] == "N/A"))))
        vals_implausible.append(int(np.sum(~coord_valid(d, loose=True))))
        vals_jump.append(int(np.sum(clean_glitches(d["x"], d["y"], d["z"], 80))))
x = np.arange(len(labels_bar))
w = 0.2
ax.bar(x - 1.5*w, vals_default, width=w, color="#718096", label="默认位姿")
ax.bar(x - 0.5*w, vals_status, width=w, color="#d69e2e", label="状态异常")
ax.bar(x + 0.5*w, vals_implausible, width=w, color="#e53e3e", label="坐标越界")
ax.bar(x + 1.5*w, vals_jump, width=w, color="#805ad5", label="单帧跳变")
ax.set_xticks(x); ax.set_xticklabels(labels_bar, rotation=55, ha="right", fontsize=8)
ax.set_ylabel("样本数（标记可重叠）")
ax.set_title("AprilTag 定位清洗标记：默认位姿/状态异常/越界/跳变")
ax.legend(fontsize=8, ncol=4)
plt.tight_layout()
plt.savefig(f"{OUT}/fig10_cleaning_quality.png"); plt.close()

metrics["yaw_rotation"] = {
    flight: {
        uid: yaw_delta_deg(d)
        for uid, d in load_by_uav(flight).items()
    }
    for flight in swarm_flights
}

metrics["flight_quality_summary"] = {
    "flight_20260709_173818": "abort/connection sample only: 98101 stayed N/A, no usable duet trajectory",
    "flight_20260709_173926": "98101 FLIP telemetry becomes implausible (x/y/z thousands of cm); useful as flip/localization failure sample",
    "flight_20260709_175214": "successful light+flip run; clean duet window has no safety-rule violation",
    "flight_20260709_175805": "98102 reports Dead Battery for most samples; clean 98101 windows remain usable, but the run is not normal duet dynamics",
    "gpsstatus": "NO_GPS is expected for the AprilTag mat positioning system; fcstatus/default pose are the relevant quality signals",
}

# ----------------------------------------------------------------------------
# 7. 指令语义实测：喂 pyfii 自身求解器，验证 §2.2 / §3.4 的数字（不依赖 flight_logs）
# ----------------------------------------------------------------------------
def verify_command_semantics():
    import sys, math
    sys.path.insert(0, "src")
    try:
        from pyfii.drone import Drone
        from pyfii.read import dots2line
    except Exception as e:
        print("跳过语义实测（无法导入 pyfii）:", e); return {}

    # (a) 网格触发多少个独立“动作未完成”事件
    d = Drone(0, 0); d.takeoff(1, 120); d.delay(3000); d.VelXY(120, 300)
    for row in range(4):
        yt = min(40+row*80, 320); xt = 320 if row % 2 == 0 else 40
        d.move2(xt, yt, 120); d.delay(2500)
    d.land()
    grid_result = drone_track(d, (0, 0))
    grid_completion = grid_result[5]

    # (b) 纯垂直 move2：pyfii 垂直速率是否恒等于 VelXY
    def climb_secs(velxy):
        dd = Drone(180, 180); dd.takeoff(1, 80); dd.delay(2000)
        dd.VelXY(velxy, 400); dd.move2(180, 180, 200); dd.delay(8000)
        dd.land(); dd.end()
        lines, _, _ = dots2line(dd.outputString, fii=[180, 180])
        t0 = t1 = None
        for l in lines:
            t, z = l[0], l[3]
            if t0 is None and z > 80.5: t0 = t
            if t1 is None and z >= 199.5: t1 = t; break
        return round((t1-t0)/1000, 2) if t0 and t1 else None
    vert = {v: climb_secs(v) for v in (150, 50, 30)}

    print(
        "\n[语义实测] 网格 medium: 独立动作打断 =",
        grid_completion["interrupted_handoffs"],
        "个；逐帧 warning =",
        grid_completion["warning_frame_count"],
        "条",
    )
    print("[语义实测] 纯垂直升120cm 用时(s) 随 VelXY:", vert, "-> 垂直速率=VelXY")
    return dict(
        grid_interrupted_handoffs=grid_completion["interrupted_handoffs"],
        grid_action_warning_frames=grid_completion["warning_frame_count"],
        pure_vertical_climb_s=vert,
    )

metrics['command_semantics'] = verify_command_semantics()

json.dump(metrics,open(f"{OUT}/metrics.json","w"),ensure_ascii=False,indent=2)
print(json.dumps(metrics,ensure_ascii=False,indent=2))
print("\nFIGS:",sorted(os.listdir(OUT)))
