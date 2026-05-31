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
# ---- 最小基线（所有段为空时有合法 takeoff/hold） ----
for i, drone in enumerate(drones):
    drone.X = drone.x = 280
    drone.Y = drone.y = 280
    drone.takeoff(1, 110)
    drone.delay(3000)


# === PYFII_AGENT_SEGMENT_START id=S01 locked=false ===
# start_time: 4.0
# end_time: 13.0
# intent: 从起飞后的散布状态开始，生成明亮、庄严、渐进的开场正式编舞；动作必须在段首 1 秒内开始，在段尾最后 1 秒内完成收束，中间不能有超过 1 秒整体悬停；要求安全、连贯、几何丰富，起飞布局与 S01 动作一起设计。

# === PYFII_AGENT_SEGMENT_END S01 ===

# === PYFII_AGENT_SEGMENT_START id=S02 locked=false ===
# start_time: 13.0
# end_time: 23.0
# intent: 承接 S01 出口位置，形成更开阔的流动展开和方向性推进；几何语言可包含弧线、V 形、扇形和前后景深，不要重复上一段队形。

# === PYFII_AGENT_SEGMENT_END S02 ===

# === PYFII_AGENT_SEGMENT_START id=S03 locked=false ===
# start_time: 23.0
# end_time: 31.0
# intent: 承接上一段出口位置，做排队错峰、交错穿梭或分组呼应的 canon 式推进；保持安全线距，避免中心对穿。

# === PYFII_AGENT_SEGMENT_END S03 ===

# === PYFII_AGENT_SEGMENT_START id=S04 locked=false ===
# start_time: 31.0
# end_time: 47.0
# intent: 进入更舒展的中段，使用星芒、波浪、框线或非圆几何变化；动作要有层次和呼吸，但不能退化为刚性圆、双排或小范围抖动。

# === PYFII_AGENT_SEGMENT_END S04 ===

# === PYFII_AGENT_SEGMENT_START id=S05 locked=false ===
# start_time: 47.0
# end_time: 58.0
# intent: 高潮段，做全场尺度的展开、爆发、回卷或分组交换；视觉要明亮有力，安全优先但不能缩成保守小动作。

# === PYFII_AGENT_SEGMENT_END S05 ===

# === PYFII_AGENT_SEGMENT_START id=S06 locked=false ===
# start_time: 58.0
# end_time: 63.0
# intent: 尾声署名和收束段，承接高潮出口位置，形成清晰、优雅、可识别的结束姿态；仍需在短时间内保持连贯真实运动。

# === PYFII_AGENT_SEGMENT_END S06 ===

# === PYFII_AGENT_SEGMENT_START id=LAND locked=false ===
# start_time: 63.0
# end_time: 68.0
# intent: 降落段：安全平滑降落。起飞和降落不计入正式编舞连续性硬门，但仍要通过执行和安全验证。

# === PYFII_AGENT_SEGMENT_END LAND ===


for drone in drones:
    drone.end()

os.makedirs(str(OUT), exist_ok=True)
pf.Fii(str(OUT), drones, music=MUSIC).save(field=6)

data, t0, *_ = pf.read_fii(str(OUT), fps=60, ignore_acc=False)
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
