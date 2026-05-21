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


# === PYFII_AGENT_SEGMENT_START id=S01 locked=true ===
# === PYFII_AGENT_SEGMENT_START id=S01 locked=true ===
# start_time: 0.0
# end_time: 14.0
# intent: 散布起飞 + 从散布进入有序

S = [(60,120),(180,60),(350,60),(500,160),(500,380),(350,480),(160,480)]

# TAKE-OFF (0-4s)
for i, drone in enumerate(drones):
    drone.X = drone.x = S[i][0]
    drone.Y = drone.y = S[i][1]
    drone.takeoff(1, 110)

# GEOMETRIES
import math as m
N = 7
geo = [
    # 环 r=140, z=135
    [(280+140*m.cos(2*m.pi*i/N), 280+140*m.sin(2*m.pi*i/N), 135) for i in range(N)],
    # 双排: 上排前4, 下排后3
    [(80+120*i, 180, 155) if i < 4 else (90+120*(i-3), 390, 165) for i in range(N)],
    # 四角 + 中心附近
    [(80,80,170),(480,80,170),(80,480,170),(480,480,170),(280,280,175),(200,200,160),(360,360,160)]
]
perms = [
    (4,5,6,0,1,2,3),
    (0,1,3,6,5,4,2),
    (0,5,1,3,6,2,4)
]
colors = ["#2255aa", "#33aa33", "#aa3333"]

# 几何时间预算
geo_starts = [4.0, 8.0, 11.5]           # 秒
offsets    = [200, 200, 0]              # 机间排队延迟 (ms)
ticks_list = [8, 5, 5]                 # 灯光步数 (每步100ms)

prev = [(drone.x, drone.y, 110) for drone in drones]

for gi in range(len(geo)):
    start_t = geo_starts[gi]
    off = offsets[gi]
    ticks = ticks_list[gi]
    perm = perms[gi]

    # 统一设置初始时间和速度
    for drone in drones:
        drone.inittime(start_t)
        drone.VelXY(200, 400)
        drone.VelZ(200, 400)

    # 逐机安排
    for i, drone in enumerate(drones):
        tx, ty, tz = geo[gi][perm[i]]
        drone.delay(i * off)                      # 排队偏移
        drone.move2(clamp_xy(tx), clamp_xy(ty), clamp_z(tz))
        apply_light(drone, colors[gi], ticks)     # 灯光 + 延迟

    # 更新上一帧位置
    prev = [(geo[gi][perm[i]][0], geo[gi][perm[i]][1], geo[gi][perm[i]][2]) for i in range(N)]

# === PYFII_AGENT_SEGMENT_END S01 ===
# === PYFII_AGENT_SEGMENT_END S01 ===

# === PYFII_AGENT_SEGMENT_START id=S02 locked=false ===
# === PYFII_AGENT_SEGMENT_START id=S02 locked=false ===
# === PYFII_AGENT_SEGMENT_START id=S02 locked=false ===
# === PYFII_AGENT_SEGMENT_START id=S02 locked=false ===
# === PYFII_AGENT_SEGMENT_START id=S02 locked=false ===
# === PYFII_AGENT_SEGMENT_START id=S02 locked=false ===
# === PYFII_AGENT_SEGMENT_START id=S02 locked=false ===
# === PYFII_AGENT_SEGMENT_START id=S02 locked=false ===
# === PYFII_AGENT_SEGMENT_START id=S02 locked=false ===
# === PYFII_AGENT_SEGMENT_START id=S02 locked=false ===
# start_time: 14.0
# end_time: 24.0
# intent: 从四角展开，对角线向大环展开，再收为三排。暖色灯光，排队错峰，全时动作。

import math as m

N = 7

prev = [(80,80,170), (420,80,170), (80,420,170), (420,420,170), (280,280,175), (200,200,160), (350,350,160)]

# ── 几何定义 ──
# Geo1: 对角线内收 (14.0-15.5)
geo1 = [
    (120, 120, 155),   # d0
    (440, 120, 155),   # d1
    (120, 440, 155),   # d2
    (440, 440, 155),   # d3
    (280, 280, 175),   # d4
    (160, 280, 155),   # d5
    (400, 280, 155),   # d6
]

# Geo2: 大环 r=200 z=160 (17.0-19.5)
geo2 = [
    (480, 280, 160),   # 右
    (405, 436, 160),   # 右上
    (235, 475, 160),   # 上偏左
    (100, 367, 160),   # 左上
    (100, 193, 160),   # 左下
    (235,  85, 160),   # 下偏左
    (405, 124, 160),   # 右下
]

# Geo3: 三排 2-3-2 (20.8-23.0)
geo3 = [
    (130, 100, 170),
    (430, 100, 170),
    (130, 280, 170),
    (280, 280, 180),
    (430, 280, 170),
    (130, 460, 170),
    (430, 460, 170),
]

geos = [geo1, geo2, geo3]

# ── 排列（通过 best_assign 离线计算） ──
perms = [
    (0, 1, 2, 3, 4, 5, 6),          # prev → geo1
    (4, 6, 3, 1, 0, 5, 2),          # geo1 → geo2
    (4, 6, 5, 2, 0, 3, 1),          # geo2 → geo3
]

# ── 灯光与时间参数 ──
# 确保灯光时间 >= 最远飞行时间 (200cm/s, 400cm/s²)
# geo1 最远 86cm → flight_time=0.86s → 12ticks=1.2s ✓
# geo2 最远 380cm → flight_time=2.38s → 24ticks=2.4s ✓
# geo3 最远 376cm → flight_time=2.36s → 24ticks=2.4s ✓
colors = ["#ff6633", "#ffa500", "#dd2244"]
ticks_list = [12, 24, 24]
offsets = [100, 80, 80]                  # 排队偏移 (ms)
geo_starts = [14.0, 17.0, 20.8]         # 秒

for gi in range(3):
    st = geo_starts[gi]
    off = offsets[gi]
    ticks = ticks_list[gi]
    color = colors[gi]
    geo = geos[gi]
    perm = perms[gi]

    # 统一速度
    for drone in drones:
        drone.inittime(st)
        drone.VelXY(200, 400)
        drone.VelZ(200, 400)

    # 逐机安排目标 + 排队 + 灯光
    for i, drone in enumerate(drones):
        tx, ty, tz = geo[perm[i]]
        drone.delay(i * off)
        drone.move2(clamp_xy(tx), clamp_xy(ty), clamp_z(tz))
        apply_light(drone, color, ticks)

    # 更新 prev 用于下一几何
    prev = [(geo[perm[i]][0], geo[perm[i]][1], geo[perm[i]][2]) for i in range(N)]

# 时间验证：
# geo1: 14.0 + 排队0.6s + 灯光1.2s = 15.8s
# geo2: 17.0 + 排队0.48s + 灯光2.4s = 19.88s
# geo3: 20.8 + 排队0.48s + 灯光2.4s = 23.68s < 24.0 ✓
# 段间隔 > 0.5s ✓
# === PYFII_AGENT_SEGMENT_END S02 ===
# === PYFII_AGENT_SEGMENT_END S02 ===
# === PYFII_AGENT_SEGMENT_END S02 ===
# === PYFII_AGENT_SEGMENT_END S02 ===
# === PYFII_AGENT_SEGMENT_END S02 ===
# === PYFII_AGENT_SEGMENT_END S02 ===
# === PYFII_AGENT_SEGMENT_END S02 ===
# === PYFII_AGENT_SEGMENT_END S02 ===
# === PYFII_AGENT_SEGMENT_END S02 ===
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
pf.show(data,t0,[MUSIC],field=6,device="F400",max_fps=60,save=str(OUT/"2d"),FPS=25)
print("2d saved")
pf.show(data,t0,[MUSIC],field=6,device="F400",max_fps=60,save=str(OUT/"3d"),FPS=25,ThreeD=True,imshow=[90,0],d=(600,450))
print("3d saved")
print("done")
