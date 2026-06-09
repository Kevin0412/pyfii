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


def move_group(drones, targets, flying_ms, color="#ffffff", ticks=4, tail_ms=100):
    """同步 keyframe：每架机 move2 + 短灯光 + 执行等待。

    这是 agent 生成代码的首选动作原语。它把常见的 per-drone
    `move2 -> apply_light -> delay` 链封装在模板函数库里，减少模型在每段里
    重新推导时间语义。返回标准化后的 targets，可直接赋给 prev。
    """
    _assert_target_count(drones, targets)
    wait_ms = max(0, int(round(flying_ms)) - int(ticks) * 100 + int(tail_ms))
    normalized = []
    for i, drone in enumerate(drones):
        target = _target3(targets[i])
        move2(drone, target, flying_ms)
        apply_light(drone, _color_at(color, i), ticks)
        drone.delay(wait_ms)
        normalized.append(target)
    return normalized


def move_group_staggered(
    drones,
    targets,
    flying_ms,
    color="#ffffff",
    ticks=4,
    group_mod=3,
    stagger_ms=120,
    tail_ms=100,
):
    """卡农/错峰 keyframe：按 i % group_mod 给每架机轻微错峰后移动。

    用于 S03 这类分组先后启动的段落。错峰必须小而清晰，避免拖成等待：
    推荐 group_mod=2/3, stagger_ms=80-180。
    """
    _assert_target_count(drones, targets)
    group_mod = max(1, int(group_mod))
    stagger_ms = max(0, int(stagger_ms))
    wait_ms = max(0, int(round(flying_ms)) - int(ticks) * 100 + int(tail_ms))
    normalized = []
    for i, drone in enumerate(drones):
        stagger = (i % group_mod) * stagger_ms
        if stagger:
            drone.delay(stagger)
        target = _target3(targets[i])
        move2(drone, target, flying_ms)
        apply_light(drone, _color_at(color, i), ticks)
        drone.delay(wait_ms)
        normalized.append(target)
    return normalized


def pulse_group(drones, color="#ffffff", ticks=3):
    """全队短灯光脉冲。正式段只用于短提示，不用它凑长时间。"""
    for i, drone in enumerate(drones):
        apply_light(drone, _color_at(color, i), ticks)


def _assert_target_count(drones, targets):
    if len(targets) != len(drones):
        raise ValueError(f"targets count {len(targets)} != drones count {len(drones)}")


def _target3(point):
    x, y, z = _xyz(point, default_z=120)
    return (clamp_xy(x), clamp_xy(y), clamp_z(z))


def _color_at(color, index):
    if isinstance(color, (list, tuple)):
        if not color:
            return "#ffffff"
        return color[index % len(color)]
    return color

# ---------- 坐标裁剪 ----------
def clamp_xy(v):
    return max(0, min(560, int(round(v))))

def clamp_z(v):
    return max(80, min(250, int(round(v))))

# ---------- 安全几何原语 ----------
def geo_wide_v(n, center=(280, 280), scale=(230, 230), z_layers=(100, 160, 220)):
    """宽 V / 扇形母题。适合 S01/S02/S06 的主题引入和回忆。"""
    norms = [
        (-1.0, 0.95), (-0.72, 0.45), (-0.45, 0.02), (-0.18, -0.38),
        (0.0, -0.72),
        (0.18, -0.38), (0.45, 0.02), (0.72, 0.45), (1.0, 0.95),
    ]
    return _shape_points(norms, n, center, scale, z_layers)


def geo_arrow(n, center=(280, 280), scale=(230, 230), z_layers=(100, 160, 220)):
    """斜线推进/箭头母题。适合方向性推进和高潮前蓄力。"""
    norms = [
        (0.0, -1.0),
        (-0.28, -0.58), (0.28, -0.58),
        (-0.56, -0.18), (0.56, -0.18),
        (-0.84, 0.26), (0.84, 0.26),
        (-0.22, 0.82), (0.22, 0.82),
    ]
    return _shape_points(norms, n, center, scale, z_layers)


def geo_box(n, margin=60, z_layers=(100, 160, 220)):
    """边界框线/署名姿态。适合展开、回收、尾声。"""
    norms = [
        (0.0, 0.0), (0.5, 0.0), (1.0, 0.0),
        (1.0, 0.5), (1.0, 1.0), (0.5, 1.0),
        (0.0, 1.0), (0.0, 0.5), (0.5, 0.5),
    ]
    span = 560 - 2 * int(margin)
    points = []
    for idx, (nx, ny) in enumerate(_pick_norms(norms, n)):
        z = z_layers[idx % len(z_layers)]
        points.append((clamp_xy(margin + nx * span), clamp_xy(margin + ny * span), clamp_z(z)))
    return points


def geo_diagonal(n, reverse=False, margin=55, z_layers=(100, 160, 220)):
    """斜线推进母题。reverse=True 时反向回卷。"""
    points = []
    if n <= 1:
        return [(280, 280, clamp_z(z_layers[0]))]
    for i in range(n):
        ratio = i / (n - 1)
        if reverse:
            ratio = 1 - ratio
        x = margin + ratio * (560 - 2 * margin)
        y = margin + ratio * (560 - 2 * margin)
        z = z_layers[i % len(z_layers)]
        points.append((clamp_xy(x), clamp_xy(y), clamp_z(z)))
    return points


def geo_wave(n, center_y=280, amplitude=170, margin=55, z_layers=(100, 160, 220)):
    """波浪/呼吸母题。适合抒情中段和高度层变化。"""
    points = []
    if n <= 1:
        return [(280, clamp_xy(center_y), clamp_z(z_layers[0]))]
    for i in range(n):
        ratio = i / (n - 1)
        x = margin + ratio * (560 - 2 * margin)
        y = center_y + math.sin(ratio * math.pi * 2) * amplitude
        z = z_layers[(i * 2) % len(z_layers)]
        points.append((clamp_xy(x), clamp_xy(y), clamp_z(z)))
    return points


def geo_grid(n, margin=65, z_layers=(100, 160, 220)):
    """安全分散网格。适合起飞布局或失败修复时重建大间距。"""
    cols = max(1, math.ceil(math.sqrt(n)))
    rows = max(1, math.ceil(n / cols))
    span = 560 - 2 * int(margin)
    points = []
    for i in range(n):
        col = i % cols
        row = i // cols
        x = margin + (span * col / max(1, cols - 1))
        y = margin + (span * row / max(1, rows - 1))
        z = z_layers[i % len(z_layers)]
        points.append((clamp_xy(x), clamp_xy(y), clamp_z(z)))
    return points


def _shape_points(norms, n, center, scale, z_layers):
    cx, cy = center
    sx, sy = scale
    points = []
    for idx, (nx, ny) in enumerate(_pick_norms(norms, n)):
        z = z_layers[idx % len(z_layers)]
        points.append((clamp_xy(cx + nx * sx), clamp_xy(cy + ny * sy), clamp_z(z)))
    return points


def _pick_norms(norms, n):
    if n <= len(norms):
        if n == len(norms):
            return list(norms)
        selected = []
        used = set()
        for i in range(n):
            raw = round(i * (len(norms) - 1) / max(1, n - 1))
            while raw in used and raw + 1 < len(norms):
                raw += 1
            used.add(raw)
            selected.append(norms[raw])
        return selected
    extra = geo_grid(n - len(norms), margin=120)
    extra_norms = [((x - 280) / 230, (y - 280) / 230) for x, y, _z in extra]
    return list(norms) + extra_norms

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
    target_items = list(targets)
    best_score, best = -1e9, targets

    def evaluate(perm):
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
        return md * 2000 - max(Distance(starts_xyz[i], tt_xyz[i]) for i in range(n)) * 0.01

    for perm in _assignment_permutations(n, starts_xyz, targets_xyz, evaluate):
        score = evaluate(perm)
        if score > best_score:
            best_score = score
            best = [target_items[i] for i in perm]
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
    target_items = list(targets)
    best_score, best = -1e18, targets

    def evaluate(perm):
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
        return score

    for perm in _assignment_permutations(n, starts_xyz, targets_xyz, evaluate):
        score = evaluate(perm)
        if score > best_score:
            best_score = score
            best = [target_items[i] for i in perm]
    return best


def _assignment_permutations(n, starts_xyz, targets_xyz, evaluate):
    """Full search for small N; deterministic local search for 9+ drones."""
    if n <= 8:
        yield from itertools.permutations(range(n))
        return

    seen = set()
    seeds = _assignment_seeds(n, starts_xyz, targets_xyz)
    for seed in seeds:
        best = _improve_assignment(seed, evaluate)
        if best not in seen:
            seen.add(best)
            yield best


def _assignment_seeds(n, starts_xyz, targets_xyz):
    base = tuple(range(n))
    seeds = [base, tuple(reversed(base))]
    seeds.extend(base[k:] + base[:k] for k in range(1, n))

    start_order = _angle_order(starts_xyz)
    target_order = _angle_order(targets_xyz)
    for shift in range(n):
        perm = [0] * n
        for pos, start_i in enumerate(start_order):
            perm[start_i] = target_order[(pos + shift) % n]
        seeds.append(tuple(perm))

    seeds.append(_greedy_assignment(starts_xyz, targets_xyz, prefer_far=False))
    seeds.append(_greedy_assignment(starts_xyz, targets_xyz, prefer_far=True))
    return seeds


def _improve_assignment(seed, evaluate, max_passes=4):
    best = tuple(seed)
    best_score = evaluate(best)
    n = len(best)
    for _ in range(max_passes):
        improved = False
        for i in range(n):
            for j in range(i + 1, n):
                candidate = list(best)
                candidate[i], candidate[j] = candidate[j], candidate[i]
                candidate = tuple(candidate)
                score = evaluate(candidate)
                if score > best_score:
                    best = candidate
                    best_score = score
                    improved = True
        if not improved:
            break
    return best


def _angle_order(points):
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    return [
        i for i, _ in sorted(
            enumerate(points),
            key=lambda item: math.atan2(item[1][1] - cy, item[1][0] - cx),
        )
    ]


def _greedy_assignment(starts_xyz, targets_xyz, prefer_far=False):
    remaining = set(range(len(targets_xyz)))
    perm = []
    for start in starts_xyz:
        chooser = max if prefer_far else min
        target_i = chooser(
            remaining,
            key=lambda idx: Distance(start, targets_xyz[idx]),
        )
        remaining.remove(target_i)
        perm.append(target_i)
    return tuple(perm)

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
