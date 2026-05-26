#!/usr/bin/env python3
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve()


def find_repo_root(path):
    for parent in path.parents:
        if (parent / "src" / "pyfii").exists():
            return parent
    cwd = Path.cwd().resolve()
    if (cwd / "src" / "pyfii").exists():
        return cwd
    raise RuntimeError("Cannot find repo root from design.py")


REPO_ROOT = find_repo_root(HERE)
sys.path.insert(0, str(REPO_ROOT / "src"))

import numpy as np
import pyfii as pf
import warnings

N = 7
MUSIC = str(REPO_ROOT / "cannon_in_D.mp3")
OUT = Path(__file__).resolve().parents[1] / "output"

drones = [pf.Drone(0, 0, pf.drone_config_6m, f"192.168.51.{51+i}") for i in range(N)]


def clamp_xy(v):
    return max(10, min(550, int(round(v))))


def clamp_z(v):
    return max(80, min(240, int(round(v))))


def apply_light(drone, color, ticks):
    for tick in range(ticks):
        bright = int(100 + 155 * math.sin(tick * math.pi / max(1, ticks)))
        r = int(color[1:3], 16) * bright // 255
        g = int(color[3:5], 16) * bright // 255
        b = int(color[5:7], 16) * bright // 255
        drone.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}")
        drone.delay(100)


# === PYFII_AGENT_SEGMENT_START id=S01 locked=false ===
# Agent-generated S01 owns takeoff setup and formal choreography:
# 1. Design safe start_positions for all 7 drones.
# 2. Set drone.X/Y and call drone.takeoff(...) before formal inittime.
# 3. Schedule formal S01 movement in the 4.0-13.0s quality window.
# === PYFII_AGENT_SEGMENT_END S01 ===


# === PYFII_AGENT_SEGMENT_START id=S02 locked=false ===
# Agent-generated S02 continues from S01 exit_state in the 13.0-23.0s quality window.
# === PYFII_AGENT_SEGMENT_END S02 ===


# === PYFII_AGENT_SEGMENT_START id=S03 locked=false ===
# Agent-generated S03 continues from S02 exit_state in the 23.0-31.0s quality window.
# === PYFII_AGENT_SEGMENT_END S03 ===


# === PYFII_AGENT_SEGMENT_START id=S04 locked=false ===
# Agent-generated S04 continues from S03 exit_state in the 31.0-47.0s quality window.
# === PYFII_AGENT_SEGMENT_END S04 ===


# === PYFII_AGENT_SEGMENT_START id=S05 locked=false ===
# Agent-generated S05 continues from S04 exit_state in the 47.0-58.0s quality window.
# === PYFII_AGENT_SEGMENT_END S05 ===


# === PYFII_AGENT_SEGMENT_START id=S06 locked=false ===
# Agent-generated S06 continues from S05 exit_state in the 58.0-63.0s quality window.
# === PYFII_AGENT_SEGMENT_END S06 ===


# === PYFII_AGENT_SEGMENT_START id=LAND locked=false ===
# Agent-generated LAND handles safe landing in the 63.0-68.0s lifecycle window.
# === PYFII_AGENT_SEGMENT_END LAND ===


for drone in drones:
    drone.end()

os.makedirs(str(OUT), exist_ok=True)
pf.Fii(str(OUT), drones, music=MUSIC).save(field=6)

warnings.filterwarnings("ignore")
data, t0, music, field, dev = pf.read_fii(str(OUT), fps=60, ignore_acc=False)
all_x = [p[1] for d in data for p in d if p[1] > 0]
all_y = [p[2] for d in data for p in d if p[1] > 0]
md = 9999
mf = min(len(d) for d in data)
for t in range(0, mf, 60):
    for i in range(N):
        for j in range(i + 1, N):
            dd = np.sqrt((data[i][t][1] - data[j][t][1]) ** 2 + (data[i][t][2] - data[j][t][2]) ** 2)
            if 0 < dd < md:
                md = dd
xy_span = (max(all_x) - min(all_x), max(all_y) - min(all_y)) if all_x and all_y else (0, 0)
print(f"{N}d F400 {t0/60:.1f}s XY({xy_span[0]:.0f},{xy_span[1]:.0f}) minD={md:.1f}cm")

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    pf.show(data, t0, [MUSIC], field=6, device="F400", max_fps=60, show=False)
dw = [x for x in caught if "distance between" in str(x.message)]
aw = [x for x in caught if "completed" in str(x.message)]
print(f"dist:{len(dw)} act:{len(aw)}")

pf.show(data, t0, [MUSIC], field=6, device="F400", max_fps=60, save=str(OUT / "2d"), FPS=25)
print("2d saved")
pf.show(data, t0, [MUSIC], field=6, device="F400", max_fps=60, save=str(OUT / "3d"), FPS=25, ThreeD=True, imshow=[90, 0], d=(600, 450))
print("3d saved")
print("done")
