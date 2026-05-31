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

def move2(d, p, t_ms, T=100):
    """反算速度 → VelXY/VelZ → d.move2。不 delay。
    
    原理：
    1. v = Vel(start, p, (t_ms-T)/1000)
    2. d.VelXY(v, 2v); d.VelZ(v, 2v)
    3. d.move2(p[0], p[1], p[2])
    
    不调用 d.delay()；但会记录预计飞行完成时间，供 auto_init 防止下一段提前开始。
    """
    start_ms = int(getattr(d, "time", 0))
    v = Vel((d.x, d.y, d.z), p, (t_ms - T) / 1000)
    d.VelXY(v, 2 * v)
    d.VelZ(v, 2 * v)
    d.move2(p[0], p[1], p[2])
    end_ms = start_ms + max(0, int(round(t_ms)))
    d._agent_motion_end_ms = max(int(getattr(d, "_agent_motion_end_ms", 0)), end_ms)

# ---------- 坐标裁剪 ----------
def clamp_xy(v):
    return max(0, min(560, int(round(v))))

def clamp_z(v):
    return max(80, min(250, int(round(v))))

# ---------- 排列 ----------
def best_assign(starts, targets):
    """最优排列：遍历全排列找最小路径间距最大的分配。返回 targets 列表。"""
    import itertools
    n = len(starts)
    best_score, best = -1e9, targets
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
                    d = ((ai[0]-aj[0])**2 + (ai[1]-aj[1])**2)**0.5
                    if d < md:
                        md = d
        score = md * 2000 - max(Distance(starts[i], tt[i]) for i in range(n)) * 0.01
        if score > best_score:
            best_score = score
            best = tt
    return best

# ---------- 灯光 ----------
def apply_light(drone, color_hex: str, ticks: int, interval_ms: int = 100):
    """灯光：ticks 次 TurnOnAll，每次 interval_ms。总耗时 ticks*interval_ms。"""
    for _ in range(ticks):
        drone.TurnOnAll(color_hex)
        drone.delay(interval_ms)

# ---------- 自动计时 ----------
def auto_init(drones):
    """把所有无人机时间游标切到当前最大游标/未完成移动之后的整数秒。"""
    latest_ms = max(
        max(int(getattr(d, "time", 0)), int(getattr(d, "_agent_motion_end_ms", 0)))
        for d in drones
    )
    t = math.ceil(latest_ms / 1000)
    for d in drones:
        d.inittime(t)
    return t
