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

def load_music(default=str(REPO_ROOT / "cannon_in_D.mp3")):
    """音乐路径来自 state.json（音乐工作流写入）；缺失时回退 cannon。"""
    try:
        state = json.loads((PROJECT_ROOT / "state.json").read_text(encoding="utf-8"))
        mp = state.get("music_path")
        if mp:
            p = (PROJECT_ROOT / mp).resolve()
            if p.exists():
                return str(p)
    except Exception:
        pass
    return default

MUSIC = load_music()
OUT = PROJECT_ROOT / "output"

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
    pass  # LAND body filled by agent
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
