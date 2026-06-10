#!/usr/bin/env python3
"""PyFii choreography — function-based segments. LLM edits function bodies only."""
import json, math, os, sys
from pathlib import Path

HERE = Path(__file__).resolve()

def find_repo_root(path):
    for parent in path.parents:
        if (parent / "src" / "pyfii").exists():
            return parent
    raise RuntimeError("Cannot find repo root")

REPO_ROOT = find_repo_root(HERE)
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(HERE.parent))

import numpy as np
import pyfii as pf
import warnings
from function import *

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def load_drone_count(default=7):
    try:
        state = json.loads((PROJECT_ROOT / "state.json").read_text(encoding="utf-8"))
        return max(1, int(state.get("drone_count", default)))
    except Exception:
        return default

N = load_drone_count()
MUSIC = str(REPO_ROOT / "cannon_in_D.mp3")
OUT = PROJECT_ROOT / "output"

drones = [pf.Drone(0, 0, pf.drone_config_6m, f"192.168.51.{51+i}") for i in range(N)]

# ============================================================
# SEGMENT FUNCTIONS (LLM edits body between AGENT markers)
# ============================================================

def s01(drones: list):
    """S01: 4-13s 起飞+初始展开"""
    # === PYFII_AGENT_SEGMENT_START id=S01 locked=true ===
    start_positions = [
        (80, 80, 110), (80, 280, 110), (80, 480, 110),
        (280, 80, 110), (280, 280, 110), (280, 480, 110),
        (480, 80, 110), (480, 280, 110), (480, 480, 110)
    ]
    for d, pos in zip(drones, start_positions):
        d.X = d.x = pos[0]
        d.Y = d.y = pos[1]
        d.takeoff(1, pos[2])
    wait_until(drones, 4.0)

    prev = [(d.x, d.y, d.z) for d in drones]

    # Keyframe 1: 开场散开，混合高度层 100-240
    geo1 = [
        (150, 100, 100), (400, 150, 180), (100, 400, 240),
        (500, 450, 100), (200, 500, 180), (450, 200, 240),
        (300, 300, 150), (100, 200, 220), (500, 300, 120)
    ]
    targets1 = best_assign(prev, geo1)
    flying_ms = 2900
    ticks = 3
    delay_ms = flying_ms - ticks * 100 + 100  # 2700
    for i, d in enumerate(drones):
        move2(d, targets1[i], flying_ms)
        apply_light(d, "#FFD700", ticks)
        d.delay(delay_ms)
    prev = [(t[0], t[1], t[2]) for t in targets1]

    # Keyframe 2: 非对称交叉，高度层 100-240
    geo2 = [
        (250, 100, 220), (100, 300, 100), (450, 200, 180),
        (350, 450, 240), (50, 200, 130), (400, 400, 160),
        (200, 350, 200), (500, 100, 240), (300, 150, 100)
    ]
    targets2 = best_assign(prev, geo2)
    for i, d in enumerate(drones):
        move2(d, targets2[i], flying_ms)
        apply_light(d, "#FFFFFF", ticks)
        d.delay(delay_ms)
    prev = [(t[0], t[1], t[2]) for t in targets2]

    # Keyframe 3: 收束向两端扩散，高度层 100-240
    geo3 = [
        (100, 100, 200), (200, 200, 100), (300, 300, 240),
        (400, 400, 100), (500, 500, 200), (150, 350, 150),
        (350, 150, 180), (450, 250, 220), (250, 450, 120)
    ]
    targets3 = best_assign(prev, geo3)
    for i, d in enumerate(drones):
        move2(d, targets3[i], flying_ms)
        apply_light(d, "#FFD700", ticks)
        d.delay(delay_ms)
    prev = [(t[0], t[1], t[2]) for t in targets3]
    # === PYFII_AGENT_SEGMENT_END S01 ===

def s02(drones: list):
    """S02: 13-23s 展开推进"""
    # === PYFII_AGENT_SEGMENT_START id=S02 locked=true ===
    auto_init(drones)
    prev = [(d.x, d.y, d.z) for d in drones]

    # ---- keyframe 1 (3000ms) ----
    geo1 = [
        (500, 500, 100), (100, 100, 240), (500, 100, 120), (100, 500, 220),
        (500, 300, 180), (300, 100, 240), (100, 300, 140), (300, 500, 200),
        (400, 400, 100)
    ]
    targets = far_assign(prev, geo1, min_path_cm=150)
    for d, t in zip(drones, targets):
        move2(d, t, 3200)
        apply_light(d, "#ff8800", 1)
        d.delay(3200)
    prev = [(t[0], t[1], t[2]) for t in targets]

    # ---- keyframe 2 (3000ms) ----
    geo2 = [
        (100, 100, 180), (500, 500, 240), (100, 500, 120), (500, 100, 220),
        (200, 100, 100), (300, 500, 240), (500, 300, 160), (100, 300, 200),
        (400, 400, 240)
    ]
    targets = far_assign(prev, geo2, min_path_cm=150)
    for d, t in zip(drones, targets):
        move2(d, t, 3200)
        apply_light(d, "#00ff88", 1)
        d.delay(3200)
    prev = [(t[0], t[1], t[2]) for t in targets]

    # ---- keyframe 3 (3000ms) ----
    geo3 = [
        (500, 100, 100), (100, 500, 240), (500, 500, 180), (100, 100, 120),
        (200, 400, 220), (400, 200, 140), (300, 300, 240), (500, 200, 160),
        (200, 100, 200)
    ]
    targets = far_assign(prev, geo3, min_path_cm=150)
    for d, t in zip(drones, targets):
        move2(d, t, 3200)
        apply_light(d, "#4466ff", 1)
        d.delay(3200)
    prev = [(t[0], t[1], t[2]) for t in targets]
    # === PYFII_AGENT_SEGMENT_END S02 ===

def s03(drones: list):
    """S03: 23-31s"""
    # === PYFII_AGENT_SEGMENT_START id=S03 locked=true ===
    auto_init(drones)
    prev = [(d.x, d.y, d.z) for d in drones]

    # Keyframe 1: 分组对角穿梭，混合高度
    geo1 = [
        (100, 100, 100),
        (500, 100, 240),
        (100, 500, 170),
        (500, 500, 100),
        (300, 100, 240),
        (100, 300, 170),
        (500, 300, 100),
        (300, 500, 240),
        (300, 300, 170)
    ]
    targets1 = best_assign(prev, geo1)
    for i, d in enumerate(drones):
        move2(d, targets1[i], 3000)
        apply_light(d, "#FF6600", 15)
        d.delay(3000 - 15 * 100)
    prev = [(t[0], t[1], t[2]) for t in targets1]

    # Keyframe 2: 二次交换，拉远拉深
    geo2 = [
        (100, 500, 240),
        (500, 100, 100),
        (300, 100, 240),
        (500, 500, 170),
        (100, 100, 170),
        (500, 300, 240),
        (100, 300, 100),
        (300, 500, 100),
        (300, 300, 240)
    ]
    targets2 = best_assign(prev, geo2)
    for i, d in enumerate(drones):
        move2(d, targets2[i], 3000)
        apply_light(d, "#00BFFF", 15)
        d.delay(3000 - 15 * 100)
    prev = [(t[0], t[1], t[2]) for t in targets2]

    # Keyframe 3: 收束，交错高度完成S03
    geo3 = [
        (250, 150, 100),
        (150, 350, 240),
        (450, 250, 170),
        (350, 450, 100),
        (150, 200, 240),
        (400, 150, 170),
        (200, 450, 100),
        (450, 400, 240),
        (300, 300, 200)
    ]
    targets3 = best_assign(prev, geo3)
    for i, d in enumerate(drones):
        move2(d, targets3[i], 2000)
        apply_light(d, "#FFFFFF", 10)
        d.delay(2000 - 10 * 100)
    prev = [(t[0], t[1], t[2]) for t in targets3]
    # === PYFII_AGENT_SEGMENT_END S03 ===

def s04(drones: list):
    """S04: 31-47s"""
    # === PYFII_AGENT_SEGMENT_START id=S04 locked=true ===
    auto_init(drones)
    prev = [(d.x, d.y, d.z) for d in drones]

    # colors
    c1 = "#FF6600"
    c2 = "#66FF00"
    c3 = "#0066FF"
    c4 = "#FF00FF"
    c5 = "#FFFF00"

    # Keyframe 1: radial spread to corners and edges
    geo1 = [
        (50,50,220),
        (50,510,100),
        (510,50,160),
        (510,510,240),
        (200,200,100),
        (200,360,220),
        (360,200,120),
        (360,360,240),
        (280,280,180)
    ]
    targets1 = far_assign(prev, geo1, min_path_cm=90)
    for i,d in enumerate(drones):
        t = targets1[i]
        move2(d, t, 3000)
        apply_light(d, c1, 10)
        d.delay(2100)
    prev = [(t[0],t[1],t[2]) for t in targets1]

    # Keyframe 2: wave lines - three rows with alternating Z
    geo2 = [
        (100,100,200),
        (250,100,120),
        (400,100,240),
        (100,300,100),
        (250,300,240),
        (400,300,120),
        (100,500,220),
        (250,500,100),
        (400,500,200)
    ]
    targets2 = far_assign(prev, geo2, min_path_cm=90)
    for i,d in enumerate(drones):
        t = targets2[i]
        move2(d, t, 3000)
        apply_light(d, c2, 10)
        d.delay(2100)
    prev = [(t[0],t[1],t[2]) for t in targets2]

    # Keyframe 3: diamond shape + 2 high points
    geo3 = [
        (280,280,200),
        (100,280,100),
        (460,280,100),
        (280,100,240),
        (280,460,240),
        (50,50,180),
        (50,510,180),
        (510,50,180),
        (510,510,180)
    ]
    targets3 = far_assign(prev, geo3, min_path_cm=90)
    for i,d in enumerate(drones):
        t = targets3[i]
        move2(d, t, 3000)
        apply_light(d, c3, 10)
        d.delay(2100)
    prev = [(t[0],t[1],t[2]) for t in targets3]

    # Keyframe 4: zigzag lines
    geo4 = [
        (150,50,220),
        (300,50,100),
        (450,50,240),
        (150,200,120),
        (300,200,220),
        (450,200,100),
        (150,350,240),
        (300,350,120),
        (450,350,220)
    ]
    targets4 = far_assign(prev, geo4, min_path_cm=90)
    for i,d in enumerate(drones):
        t = targets4[i]
        move2(d, t, 3000)
        apply_light(d, c4, 10)
        d.delay(2100)
    prev = [(t[0],t[1],t[2]) for t in targets4]

    # Keyframe 5: spiral / alternating heights
    geo5 = [
        (200,200,100),
        (250,150,240),
        (300,300,100),
        (400,200,240),
        (450,400,100),
        (350,500,240),
        (200,450,100),
        (100,400,240),
        (100,250,100)
    ]
    targets5 = far_assign(prev, geo5, min_path_cm=90)
    for i,d in enumerate(drones):
        t = targets5[i]
        move2(d, t, 3000)
        apply_light(d, c5, 10)
        d.delay(2100)
    prev = [(t[0],t[1],t[2]) for t in targets5]
    # === PYFII_AGENT_SEGMENT_END S04 ===

def s05(drones: list):
    """S05: 47-58s"""
    # === PYFII_AGENT_SEGMENT_START id=S05 locked=true ===
    auto_init(drones)
    prev = [(d.x, d.y, d.z) for d in drones]

    # Keyframe 1: 爆发展开，全场大尺度分散
    geo1 = [
        (50, 50, 220),
        (50, 550, 100),
        (550, 50, 100),
        (550, 550, 220),
        (50, 300, 160),
        (550, 300, 160),
        (300, 50, 160),
        (300, 550, 160),
        (450, 450, 80)
    ]
    targets1 = far_assign(prev, geo1, min_path_cm=220)
    flying_ms1 = 3500
    ticks1 = 3  # 300ms
    color1 = "#FFAA00"
    for i, d in enumerate(drones):
        t = targets1[i]
        move2(d, t, flying_ms1)
        apply_light(d, color1, ticks1)
        d.delay(max(0, flying_ms1 - ticks1 * 100 + 100))
    prev = [t for t in targets1]

    # Keyframe 2: 分组交叉，上下左右交换，Z层错落
    geo2 = [
        (500, 500, 80),
        (500, 100, 220),
        (100, 500, 220),
        (100, 100, 80),
        (400, 300, 150),
        (200, 300, 150),
        (300, 400, 150),
        (300, 200, 150),
        (300, 300, 200)
    ]
    targets2 = far_assign(prev, geo2, min_path_cm=220)
    flying_ms2 = 3600
    ticks2 = 3
    color2 = "#FF5500"
    for i, d in enumerate(drones):
        t = targets2[i]
        move2(d, t, flying_ms2)
        apply_light(d, color2, ticks2)
        d.delay(max(0, flying_ms2 - ticks2 * 100 + 100))
    prev = [t for t in targets2]

    # Keyframe 3: 收束成三角钻石阵，保持高度变化
    geo3 = [
        (280, 300, 220),
        (200, 160, 100),
        (400, 160, 100),
        (200, 440, 100),
        (400, 440, 100),
        (280, 220, 160),
        (280, 380, 160),
        (180, 300, 160),
        (380, 300, 160)
    ]
    targets3 = far_assign(prev, geo3, min_path_cm=90)
    flying_ms3 = 3500
    ticks3 = 3
    color3 = "#FFFF00"
    for i, d in enumerate(drones):
        t = targets3[i]
        move2(d, t, flying_ms3)
        apply_light(d, color3, ticks3)
        d.delay(max(0, flying_ms3 - ticks3 * 100 + 100))
    prev = [t for t in targets3]
    # === PYFII_AGENT_SEGMENT_END S05 ===

def s06(drones: list):
    """S06: 58-63s"""
    # === PYFII_AGENT_SEGMENT_START id=S06 locked=true ===
    auto_init(drones)
    prev = [(d.x, d.y, d.z) for d in drones]

    geo = [
        (80, 280, 80),
        (480, 280, 240),
        (80, 80, 160),
        (480, 480, 100),
        (280, 80, 220),
        (280, 480, 160),
        (80, 480, 220),
        (480, 80, 100),
        (280, 280, 200)
    ]

    targets = far_assign(prev, geo, min_path_cm=220)

    for i, d in enumerate(drones):
        tx, ty, tz = targets[i]
        mx = clamp_xy((prev[i][0] + tx) // 2)
        my = clamp_xy((prev[i][1] + ty) // 2)
        mz = clamp_z((prev[i][2] + tz) // 2)

        move2(d, (mx, my, mz), 2500)
        apply_light(d, '#FFD700', 1)
        d.delay(max(0, 2500 - 100))

        move2(d, (tx, ty, tz), 2500)
        apply_light(d, '#FFD700', 2)
        d.delay(max(0, 2500 - 200))

    prev = [(t[0], t[1], t[2]) for t in targets]
    # === PYFII_AGENT_SEGMENT_END S06 ===

def land(drones: list):
    """LAND: 63-68s 降落"""
    # === PYFII_AGENT_SEGMENT_START id=LAND locked=true ===
    auto_init(drones)
    for d in drones:
        apply_light(d, "#ffffff", 3)
        d.land()
    # === PYFII_AGENT_SEGMENT_END LAND ===

# ============================================================
# MAIN EXECUTION
# ============================================================
s01(drones)
s02(drones)
s03(drones)
s04(drones)
s05(drones)
s06(drones)
land(drones)

# ============================================================
# FIXED FOOTER
# ============================================================
# Only save Fii if drones have actual actions
has_actions = any(len(getattr(d, 'action_list', [])) > 0 or bool(getattr(d, 'light_actions', {})) for d in drones)
if has_actions:
    for drone in drones:
        drone.end()
    os.makedirs(str(OUT), exist_ok=True)
    try:
        fii = pf.Fii(str(OUT), drones, music=MUSIC)
        fii.save(field=6)
        data, t0, *_ = pf.read_fii(str(OUT), fps=60, ignore_acc=False)
    except Exception:
        print("Fii save/read failed")
        sys.exit(1)
else:
    print("empty template — no drone actions")
    sys.exit(0)


mf = min(len(d) for d in data)
all_x = [p[1] for d in data for p in d if p[1] > 0]
all_y = [p[2] for d in data for p in d if p[1] > 0]
md = 1e9
for t in range(0, mf, 60):
    for i in range(N):
        for j in range(i+1, N):
            dd = ((data[i][t][1]-data[j][t][1])**2 + (data[i][t][2]-data[j][t][2])**2)**0.5
            if 0 < dd < md:
                md = dd
if all_x and all_y:
    print(f"{N}d F400 {t0/60:.1f}s XY({max(all_x)-min(all_x):.0f},{max(all_y)-min(all_y):.0f}) minD={md:.1f}cm")

with warnings.catch_warnings(record=True) as c:
    warnings.simplefilter("always")
    pf.show(data, t0, [MUSIC], field=6, device="F400", max_fps=60, show=False)
dw = [x for x in c if "distance between" in str(x.message)]
aw = [x for x in c if "completed" in str(x.message)]
print(f"dist:{len(dw)} act:{len(aw)}")
print("done")
