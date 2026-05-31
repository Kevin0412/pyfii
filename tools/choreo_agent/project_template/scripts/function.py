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

def move2(d, p, t, T=100):
    """封装：反算速度 → 设VelXY/VelZ → d.move2(x,y,z,timestamp) → delay(t_ms)
    
    原理：
    1. 根据距离 p 和时间 t 反算速度 v
    2. d.VelXY(v, v*2); d.VelZ(v, v*2) 设速度/加速度
    3. d.move2(p[0], p[1], p[2]) 执行飞行
    4. d.delay(t_ms) 等待完成
    
    耗时 = t_ms（不额外加 delay）
    注意：同一时刻只能一个动作，错峰用 drone.delay(i * stagger)
    
    d: drone, p: (x,y,z) 目标, t: 总时间(ms), T: 留给灯光的时间(ms)
    """
    v = Vel((d.x, d.y, d.z), p, (t-T)/1000)
    d.VelXY(v, 2*v)
    d.VelZ(v, 2*v)
    d.move2(p[0], p[1], p[2])
    d.delay(t)

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

# ---------- 兼容旧版 ----------
def flight_time_ms(d, v, a):
    """飞行时间(ms) — 兼容旧代码"""
    if d <= 0: return 0
    accel_dist = v*v/(2*a)
    t = 2*v/a + (d-2*accel_dist)/v if d >= 2*accel_dist else 2*math.sqrt(d/a)
    return int(math.ceil(t*1000))

def distance_3d(p1, p2):
    return Distance(p1, p2)


# ---------- 自动计时 ----------
def auto_init(drones, start_time: float = None):
    """设置段起始时间。不传则 max+1"""
    if start_time is not None:
        t = start_time
    else:
        t = max(d.init_time for d in drones) + 1
    for d in drones:
        d.inittime(t)
