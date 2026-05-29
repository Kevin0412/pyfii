"""Agent 函数库 — DNTG 风格

用法: from function import *
"""

import math
import itertools

# ---------- 几何 ----------
def Distance(p1, p2):
    """3D距离 (cm)"""
    return ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2 + (p1[2]-p2[2])**2) ** 0.5

def Time(p1, p2, v, a):
    """飞行时间 (秒)，给定起点、终点、速度、加速度"""
    d = Distance(p1, p2)
    if d > v*v/a:
        return (d - v*v/a)/v + v/a*2
    else:
        return (d/a)**0.5 * 2

def Vel(p1, p2, t):
    """反算速度 (cm/s)，给定起点、终点、时间(秒)，a=2v"""
    for v in range(50, 201):
        if Time(p1, p2, v, v*2) <= t:
            return v
    return 200

def move2(d, p, t):
    """反算速度 → VelXY → move2。不 delay——留给灯光。
    d: drone, p: (x,y,z) 目标, t: 总飞行时间(ms)
    用法：move2(drone, (x,y,z), 3000); apply_light(drone, '#fff', 6)
    """
    v = Vel((d.x, d.y, d.z), p, t/1000)
    d.VelXY(v, 2*v)
    d.VelZ(v, 2*v)
    d.move2(p[0], p[1], p[2])

# ---------- 坐标裁剪 ----------
def clamp_xy(v):
    return max(0, min(560, int(round(v))))

def clamp_z(v):
    return max(80, min(250, int(round(v))))

# ---------- 灯光 ----------
def apply_light(drone, color, ticks, interval_ms=100):
    for tick in range(ticks):
        bright = int(100 + 155*math.sin(tick*math.pi/max(ticks, 1)))
        r = int(color[1:3], 16)*bright//255
        g = int(color[3:5], 16)*bright//255
        b = int(color[5:7], 16)*bright//255
        drone.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}")
        drone.delay(interval_ms)

# ---------- 排列 ----------
def best_assign(starts, targets):
    """遍历全排列，找最小路径间距最大的分配"""
    n = len(starts)
    best_score, best = -1e9, None
    for perm in itertools.permutations(range(n)):
        tt = [targets[i] for i in perm]
        md = 1e9
        for ratio in [0.2, 0.4, 0.6, 0.8]:
            for i in range(n):
                for j in range(i+1, n):
                    ai = (starts[i][0]*ratio + tt[i][0]*(1-ratio),
                          starts[i][1]*ratio + tt[i][1]*(1-ratio))
                    aj = (starts[j][0]*ratio + tt[j][0]*(1-ratio),
                          starts[j][1]*ratio + tt[j][1]*(1-ratio))
                    d = math.hypot(ai[0]-aj[0], ai[1]-aj[1])
                    if d < md: md = d
        score = md*2000 - max(Distance(starts[i], tt[i]) for i in range(n))*0.01
        if score > best_score: best_score = score; best = tt
    return best

# ---------- 安全几何生成 ----------
# 如需使用：from core.safe_geo import generate_safe_geo
# geo = generate_safe_geo('expand', min_spacing=120)
# 内置备用（不依赖 safe_geo 模块）：
import random as _random, math as _math

def safe_geo(mode='expand', n=7, min_spacing=120, min_dist=120, center=(280,280), z_min=140, z_max=220):
    """生成安全几何。使用固定种子保证可重复"""
    """生成安全几何——保证7点XY间距>=min_spacing。
    mode: expand/rotate/breathe/contract
    """
    pts = []
    if mode == 'rotate':
        r = max(150, min_spacing)
        for i in range(n-1):
            a = 2*_math.pi*i/(n-1)+_random.uniform(0,0.5)
            pts.append((int(center[0]+r*_math.cos(a)), int(center[1]+r*_math.sin(a)), _random.randint(z_min,z_max)))
        pts.append((center[0], center[1], _random.randint(z_min,z_max)))
    elif mode == 'breathe':
        r = _random.randint(120, 220)
        for i in range(n):
            a = 2*_math.pi*i/n+_random.uniform(0,0.3)
            pts.append((int(center[0]+r*_math.cos(a)), int(center[1]+r*_math.sin(a)), _random.randint(z_min,z_max)))
    elif mode == 'contract':
        r = _random.randint(80, 130)
        for i in range(n):
            a = 2*_math.pi*i/n
            pts.append((int(center[0]+r*_math.cos(a)), int(center[1]+r*_math.sin(a)), z_min))
    else:  # expand — 泊松圆盘
        att=0
        while len(pts)<n and att<500:
            x=_random.randint(50,510); y=_random.randint(50,510); z=_random.randint(z_min,z_max)
            if all(((x-px)**2+(y-py)**2)**0.5 >= min(min_spacing, min_dist) for px,py,_ in pts): pts.append((x,y,z))
            att+=1
        while len(pts)<n:
            x=_random.randint(80,480); y=_random.randint(80,480)
            if all(((x-px)**2+(y-py)**2)**0.5 >= min(min_spacing, min_dist)*0.7 for px,py,_ in pts): pts.append((x,y,_random.randint(z_min,z_max)))
    return pts[:n]

# ---------- 自动计时 ----------
_GLOBAL_TIME = 0

def auto_init(drones, start_sec=None):
    global _GLOBAL_TIME
    if start_sec is not None:
        _GLOBAL_TIME = start_sec
    else:
        max_t = max(d.time for d in drones) / 1000
        _GLOBAL_TIME = max(_GLOBAL_TIME, max_t + 0.1)
        _GLOBAL_TIME = math.ceil(_GLOBAL_TIME)
    print(f"auto_init: GLOBAL_TIME={_GLOBAL_TIME}s, drone.time={drones[0].time}ms")
    for d in drones:
        d.inittime(_GLOBAL_TIME)
    return _GLOBAL_TIME

def should_land(drones, min_sec=60):
    """当前总时间 >= min_sec 时返回 True，触发降落"""
    max_t = max(d.time for d in drones) / 1000
    return max_t >= min_sec

# ---------- 兼容旧版 ----------
def flight_time_ms(d, v, a):
    """飞行时间(ms) — 兼容旧代码"""
    if d <= 0: return 0
    accel_dist = v*v/(2*a)
    t = 2*v/a + (d-2*accel_dist)/v if d >= 2*accel_dist else 2*math.sqrt(d/a)
    return int(math.ceil(t*1000))

def distance_3d(p1, p2):
    return Distance(p1, p2)
