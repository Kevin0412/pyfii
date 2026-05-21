#!/usr/bin/env python3
# === PYFII_AGENT_EXAMPLE: 标准段模板 ===
# 展示: 几何定义 + 排列搜索 + 灯效 + 验证
import sys, math, os, itertools
from pathlib import Path

# --- 固定头部 (由 TUI 管理，agent 不修改) ---
N = 7
REPO_ROOT = Path(__file__).resolve().parents[3]  # tools/choreo_agent/../../
sys.path.insert(0, str(REPO_ROOT / "src"))
import pyfii as pf

OUT = REPO_ROOT / "agent_projects" / "my_project" / "output"
MUSIC = str(REPO_ROOT / "agent_projects" / "my_project" / "music.mp3")

drones = [pf.Drone(0, 0, pf.drone_config_6m, f"192.168.51.{51+i}") for i in range(N)]

def clamp_xy(v):
    return max(10, min(550, int(round(v))))
def clamp_z(v):
    return max(80, min(240, int(round(v))))
def apply_light(drone, color, ticks):
    for tick in range(ticks):
        bright = int(100 + 155 * math.sin(tick * math.pi / ticks))
        r = int(color[1:3], 16) * bright // 255
        g = int(color[3:5], 16) * bright // 255
        b = int(color[5:7], 16) * bright // 255
        drone.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}")
        drone.delay(100)

def best_assign(starts, targets):
    best_score, best = -1e9, None
    for perm in itertools.permutations(range(N)):
        tt = [targets[i] for i in perm]
        md = 1e9
        for ratio in [0.2, 0.4, 0.6, 0.8]:
            for i in range(N):
                for j in range(i+1, N):
                    ai = tuple(starts[i][k]*ratio + tt[i][k]*(1-ratio) for k in range(2))
                    aj = tuple(starts[j][k]*ratio + tt[j][k]*(1-ratio) for k in range(2))
                    d = math.hypot(ai[0]-aj[0], ai[1]-aj[1])
                    if d < md: md = d
        score = md * 2000 - max(math.dist(starts[i], tt[i]) for i in range(N)) * 0.01
        if score > best_score:
            best_score = score
            best = tt
    return best

# --- 固定头部结束 ---

# 起始散布
S = [(60,120),(180,60),(350,60),(500,160),(500,380),(350,480),(160,480)]
for i, drone in enumerate(drones):
    drone.X = drone.x = S[i][0]; drone.Y = drone.y = S[i][1]
    drone.takeoff(1, 110)

# === AGENT_SEGMENT_START S01 locked=false ===
# intent: 初始展开，安全几何引导
# start_time: 4.0
# end_time: 14.0

geo = [
    [(S[i][0]+20*math.sin(i), S[i][1]+20*math.cos(i), 120) for i in range(N)],
    [(280+140*math.cos(2*math.pi*i/N), 280+140*math.sin(2*math.pi*i/N), 135) for i in range(N)],
    [(80+i*120, 180, 150) if i<4 else (90+(i-3)*120, 390, 160) for i in range(N)],
]

colors = ["#2255aa", "#3388cc", "#44aadd"]
for i, drone in enumerate(drones):
    drone.intime(4)
    drone.VelXY(200, 400)
    drone.VelZ(200, 400)

prev = [(d.x, d.y, 110) for drone in drones]
for gi in range(len(geo)):
    targets = geo[gi] if gi == 0 else best_assign(prev, geo[gi])
    for i, drone in enumerate(drones):
        dist_cm = math.dist((prev[i][0], prev[i][1]),
                          (targets[i][0], targets[i][1]))
        speed = min(200, max(150, int(dist_cm / 2.0)))
        drone.VelXY(spd, spd*2); drone.VelZ(spd, spd*2)
        drone.move2(clamp_xy(targets[i][0]), clamp_xy(targets[i][1]), clamp_z(targets[i][2]+20*math.sin(i)))
        light(d, colors[gi], 15)
        d.delay(1500)
    prev = targets

# === AGENT_SEGMENT_END S01 ===

for drone in drones: drone.end()
os.makedirs(str(OUT), exist_ok=True)
pf.Fii(str(OUT), drones, music=MUSIC).save(field=6)

# 验证
import numpy as np, warnings; warnings.filterwarnings('ignore')
data, t0, music, field, dev = pf.read_fii(str(OUT), fps=60, ignore_acc=False)
with warnings.catch_warnings(record=True) as c:
    warnings.simplefilter('always')
    pf.show(data, t0, [MUSIC], field=field, device=dev, max_fps=60, show=False)
dw = [x for x in c if 'distance between' in str(x.message)]
aw = [x for x in c if 'completed' in str(x.message)]
print(f"dist:{len(dw)} act:{len(aw)}")
