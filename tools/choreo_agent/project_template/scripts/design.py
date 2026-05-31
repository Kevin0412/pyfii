#!/usr/bin/env python3
"""PyFii choreography — function-based segments. LLM edits function bodies only."""
import math, os, sys
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

N = 7
MUSIC = str(REPO_ROOT / "cannon_in_D.mp3")
OUT = Path(__file__).resolve().parents[1] / "output"

drones = [pf.Drone(0, 0, pf.drone_config_6m, f"192.168.51.{51+i}") for i in range(N)]

# ============================================================
# SEGMENT FUNCTIONS (LLM edits body between AGENT markers)
# ============================================================

def s01(drones: list):
    """S01: 4-13s 起飞+初始展开"""
    # === PYFII_AGENT_SEGMENT_START id=S01 locked=false ===
    prev = [(d.x, d.y, d.z) for d in drones]
    # LLM-generated code here
    return prev
    # === PYFII_AGENT_SEGMENT_END S01 ===

def s02(drones: list):
    """S02: 13-23s 展开推进"""
    # === PYFII_AGENT_SEGMENT_START id=S02 locked=false ===
    prev = [(d.x, d.y, d.z) for d in drones]
    # LLM-generated code here
    return prev
    # === PYFII_AGENT_SEGMENT_END S02 ===

def s03(drones: list):
    """S03: 23-31s"""
    # === PYFII_AGENT_SEGMENT_START id=S03 locked=false ===
    prev = [(d.x, d.y, d.z) for d in drones]
    return prev
    # === PYFII_AGENT_SEGMENT_END S03 ===

def s04(drones: list):
    """S04: 31-47s"""
    # === PYFII_AGENT_SEGMENT_START id=S04 locked=false ===
    prev = [(d.x, d.y, d.z) for d in drones]
    return prev
    # === PYFII_AGENT_SEGMENT_END S04 ===

def s05(drones: list):
    """S05: 47-58s"""
    # === PYFII_AGENT_SEGMENT_START id=S05 locked=false ===
    prev = [(d.x, d.y, d.z) for d in drones]
    return prev
    # === PYFII_AGENT_SEGMENT_END S05 ===

def s06(drones: list):
    """S06: 58-63s"""
    # === PYFII_AGENT_SEGMENT_START id=S06 locked=false ===
    prev = [(d.x, d.y, d.z) for d in drones]
    return prev
    # === PYFII_AGENT_SEGMENT_END S06 ===

def land(drones: list):
    """LAND: 63-68s 降落"""
    # === PYFII_AGENT_SEGMENT_START id=LAND locked=false ===
    for drone in drones:
        drone.land()
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
for drone in drones:
    drone.end()

os.makedirs(str(OUT), exist_ok=True)
try:
    fii = pf.Fii(str(OUT), drones, music=MUSIC)
    fii.save(field=6)
except Exception:
    print("Fii init/save failed (empty template — expected)")
    sys.exit(0)

try:
    data, t0, *_ = pf.read_fii(str(OUT), fps=60, ignore_acc=False)
except Exception:
    print("read_fii failed (empty template — expected)")
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
    print(f"7d F400 {t0/60:.1f}s XY({max(all_x)-min(all_x):.0f},{max(all_y)-min(all_y):.0f}) minD={md:.1f}cm")

with warnings.catch_warnings(record=True) as c:
    warnings.simplefilter("always")
    pf.show(data, t0, [MUSIC], field=6, device="F400", max_fps=60, show=False)
dw = [x for x in c if "distance between" in str(x.message)]
aw = [x for x in c if "completed" in str(x.message)]
print(f"dist:{len(dw)} act:{len(aw)}")
print("done")
