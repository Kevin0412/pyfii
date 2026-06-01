"""Agent 函数库 — DNTG 风格

用法: from function import *
"""

import math
import itertools

# ---------- 几何 ----------
def Distance(p1, p2):
    """2D/3D 距离 (cm)。缺省 z=0，避免 best_assign 误传 XY 时崩溃。"""
    a = _xyz(p1)
    b = _xyz(p2)
    return ((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2) ** 0.5

def _xyz(p, default_z=0):
    if len(p) < 2:
        raise ValueError(f"point must contain x/y: {p!r}")
    return (
        float(p[0]),
        float(p[1]),
        float(p[2]) if len(p) >= 3 else float(default_z),
    )

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
    """最优排列：遍历全排列找最小路径间距最大的分配。返回重排后的 targets 列表。

    starts/targets 可以是 2D 或 3D 点；返回值保持 target 原始维度。
    正确用法：targets = best_assign(prev, geo)，不要拆 perm/min_d。
    """
    import itertools
    n = len(starts)
    starts_xyz = [_xyz(p) for p in starts]
    targets_xyz = [_xyz(p) for p in targets]
    best_score, best = -1e9, targets
    for perm in itertools.permutations(range(n)):
        tt = [targets[i] for i in perm]
        tt_xyz = [targets_xyz[i] for i in perm]
        md = 1e9
        for ratio in [0.2, 0.4, 0.6, 0.8]:
            for i in range(n):
                for j in range(i+1, n):
                    ai = (starts_xyz[i][0]*ratio + tt_xyz[i][0]*(1-ratio),
                          starts_xyz[i][1]*ratio + tt_xyz[i][1]*(1-ratio))
                    aj = (starts_xyz[j][0]*ratio + tt_xyz[j][0]*(1-ratio),
                          starts_xyz[j][1]*ratio + tt_xyz[j][1]*(1-ratio))
                    d = ((ai[0]-aj[0])**2 + (ai[1]-aj[1])**2)**0.5
                    if d < md:
                        md = d
        score = md * 2000 - max(Distance(starts_xyz[i], tt_xyz[i]) for i in range(n)) * 0.01
        if score > best_score:
            best_score = score
            best = tt
    return best

def far_assign(starts, targets, min_path_cm=90, min_spacing_cm=140):
    """安全但鼓励远距离交换的分配。返回重排后的 targets 列表。

    best_assign 会倾向最短安全路径，适合承接和收束；S04/S05 等长段如果继续
    使用相似几何，很容易退化成小范围挪动。far_assign 在保持路径间距的前提下
    奖励更大的中位路径长度，用来制造展开、回卷、交换等大动作。
    """
    n = len(starts)
    starts_xyz = [_xyz(p) for p in starts]
    targets_xyz = [_xyz(p) for p in targets]
    best_score, best = -1e18, targets
    for perm in itertools.permutations(range(n)):
        tt = [targets[i] for i in perm]
        tt_xyz = [targets_xyz[i] for i in perm]
        min_path_spacing = 1e9
        for step in range(1, 50):
            ratio = step / 50
            for i in range(n):
                for j in range(i + 1, n):
                    ai = (
                        starts_xyz[i][0] * (1 - ratio) + tt_xyz[i][0] * ratio,
                        starts_xyz[i][1] * (1 - ratio) + tt_xyz[i][1] * ratio,
                    )
                    aj = (
                        starts_xyz[j][0] * (1 - ratio) + tt_xyz[j][0] * ratio,
                        starts_xyz[j][1] * (1 - ratio) + tt_xyz[j][1] * ratio,
                    )
                    d = ((ai[0] - aj[0]) ** 2 + (ai[1] - aj[1]) ** 2) ** 0.5
                    if d < min_path_spacing:
                        min_path_spacing = d
        path_lengths = [Distance(starts_xyz[i], tt_xyz[i]) for i in range(n)]
        median_path = sorted(path_lengths)[n // 2]
        max_path = max(path_lengths)
        short_penalty = sum(max(0, float(min_path_cm) - d) for d in path_lengths)
        spacing_penalty = max(0, float(min_spacing_cm) - min_path_spacing)
        safe_spacing = min(min_path_spacing, 120)
        score = (
            safe_spacing * 1200
            + median_path * 900
            + max_path * 80
            - short_penalty * 1000
            - spacing_penalty * 12000
        )
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

def wait_until(drones, target_s):
    """不用 inittime，靠 delay 把每架机自然等待到目标绝对秒。适合 S01 起飞后对齐。"""
    target_ms = int(round(float(target_s) * 1000))
    for d in drones:
        now_ms = max(int(getattr(d, "time", 0)), int(getattr(d, "_agent_motion_end_ms", 0)))
        d.delay(max(0, target_ms - now_ms))
    return target_ms / 1000
