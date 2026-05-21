#!/usr/bin/env python3
import sys, math, os, itertools
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO_ROOT / "src"))
import pyfii as pf

N = 7
MUSIC = str(REPO_ROOT / "cannon_in_D.mp3")
OUT = REPO_ROOT / "tools" / "choreo_agent" / "agent_projects" / "cannon_in_d" / "output"

drones = [pf.Drone(0, 0, pf.drone_config_6m, f"192.168.51.{51+i}") for i in range(N)]

def clamp_xy(v): return max(0, min(560, int(round(v))))
def clamp_z(v): return max(80, min(250, int(round(v))))

def apply_light(drone, color, ticks):
    for tick in range(ticks):
        bright = int(100 + 155 * math.sin(tick * math.pi / ticks))
        r = int(color[1:3], 16) * bright // 255
        g = int(color[3:5], 16) * bright // 255
        b = int(color[5:7], 16) * bright // 255
        drone.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}")
        drone.delay(100)

# 散布起飞
S = [(60,120),(180,60),(350,60),(500,160),(500,380),(350,480),(160,480)]
for i, drone in enumerate(drones):
    drone.X = drone.x = S[i][0]
    drone.Y = drone.y = S[i][1]
    drone.takeoff(1, 110)

# === PYFII_AGENT_SEGMENT_START id=S01 locked=false ===
print("S01 placeholder")
# === PYFII_AGENT_SEGMENT_END S01 ===

# === PYFII_AGENT_SEGMENT_START id=S02 locked=false ===
print("S02 placeholder")
# === PYFII_AGENT_SEGMENT_END S02 ===

for drone in drones: drone.end()
os.makedirs(str(OUT), exist_ok=True)
pf.Fii(str(OUT), drones, music=MUSIC).save(field=6)

import numpy as np, warnings; warnings.filterwarnings('ignore')
data, t0, music, field, dev = pf.read_fii(str(OUT), fps=60, ignore_acc=False)
all_x = [p[1] for d in data for p in d if p[1] > 0]
all_y = [p[2] for d in data for p in d if p[1] > 0]
md = 9999; mf = min(len(d) for d in data)
for t in range(0, mf, 60):
    for i in range(N):
        for j in range(i+1, N):
            dd = np.sqrt((data[i][t][1]-data[j][t][1])**2 + (data[i][t][2]-data[j][t][2])**2)
            if 0 < dd < md: md = dd
print(f"{N}d F400 {t0/60:.1f}s XY({max(all_x)-min(all_x):.0f},{max(all_y)-min(all_y):.0f}) minD={md:.1f}cm")
with warnings.catch_warnings(record=True) as c:
    warnings.simplefilter('always')
    pf.show(data, t0, [MUSIC], field=6, device='F400', max_fps=60, show=False)
dw = [x for x in c if 'distance between' in str(x.message)]
aw = [x for x in c if 'completed' in str(x.message)]
print(f"dist:{len(dw)} act:{len(aw)}")
print("done")
