"""Agent 函数库 — DNTG 风格

用法: from function import *
"""

import math
import itertools

__all__ = [
    "Distance",
    "Time",
    "Vel",
    "move2",
    "move_group",
    "move_group_staggered",
    "pulse_group",
    "custom_points",
    "jitter_points",
    "active_min_path_cm",
    "clamp_xy",
    "clamp_z",
    "best_assign",
    "far_assign",
    "apply_light",
    "auto_init",
    "wait_until",
]

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


def move_group(drones, targets, flying_ms, color="#ffffff", ticks=4, tail_ms=0):
    """同步 keyframe 兜底：每架机 move2 + 短灯光 + 执行等待。

    它适合 smoke 或临时修复，但会隐藏 per-drone 节奏和灯光细节。
    正式段应优先展开 `move2 -> apply_light -> delay` loop。
    返回标准化后的 targets，可直接赋给 prev。
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
    tail_ms=0,
):
    """卡农/错峰 keyframe 兜底：按 i % group_mod 给每架机轻微错峰后移动。

    正式段更推荐在 per-drone loop 中显式写错峰、灯光和等待细节。
    错峰必须小而清晰，避免拖成等待：推荐 group_mod=2/3, stagger_ms=80-180。
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


def active_min_path_cm(flying_ms):
    """按 move2 名义时长估算最低路径长度，减少早停后靠 delay 的低活动。

    function.py 的 move2 会选择能完成该路径的速度；如果路径太短，底层最低
    速度仍会让真实飞行提前结束。长 keyframe 搭配 far_assign 时，用这个值
    作为 min_path_cm，可以让动作更接近名义 flying_ms。
    """
    try:
        seconds = float(flying_ms) / 1000.0
    except (TypeError, ValueError):
        seconds = 3.0
    return int(max(90, min(280, round((seconds - 0.4) * 50))))

# ---------- 坐标裁剪 ----------
def clamp_xy(v):
    return max(0, min(560, int(round(v))))

def clamp_z(v):
    return max(80, min(250, int(round(v))))

# ---------- 手写几何辅助 ----------
def custom_points(points, n=None, min_xy_cm=90):
    """标准化手写坐标表，并在运行时检查 keyframe 内 XY 间距。

    这是正式编舞的主路径：agent 应先写出有叙事意图的坐标表，再用
    `best_assign(prev, geo)` 或 `far_assign(prev, geo, ...)` 做安全路径分配。
    """
    normalized = [_target3(point) for point in points]
    if n is not None and len(normalized) != int(n):
        raise ValueError(f"custom_points count {len(normalized)} != expected {int(n)}")
    if len(normalized) >= 2:
        min_xy = _min_xy_spacing(normalized)
        if min_xy < float(min_xy_cm):
            raise ValueError(f"custom_points min_xy {min_xy:.1f}cm < {float(min_xy_cm):.1f}cm")
    return normalized


def jitter_points(points, xy=18, z=12, seed=0, min_xy_cm=70):
    """给一组已安全的手写点加入确定性微扰，避免过于机械的对称。

    如果微扰后破坏间距，则返回原始标准化点表。不要用它替代手写构图；
    它只负责把已经设计好的几何稍微打散。
    """
    base = [_target3(point) for point in points]
    jittered = []
    for i, (x, y, z_value) in enumerate(base):
        phase = (i + 1) * (float(seed) + 3.17)
        dx = math.sin(phase * 1.618) * float(xy)
        dy = math.cos(phase * 2.414) * float(xy)
        dz = math.sin(phase * 0.917) * float(z)
        jittered.append((clamp_xy(x + dx), clamp_xy(y + dy), clamp_z(z_value + dz)))
    try:
        return custom_points(jittered, n=len(base), min_xy_cm=min_xy_cm)
    except ValueError:
        return base


def _min_xy_spacing(points):
    md = 1e9
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            d = ((points[i][0] - points[j][0]) ** 2 + (points[i][1] - points[j][1]) ** 2) ** 0.5
            if d < md:
                md = d
    return md


# ---------- 已下线几何模板 ----------
# geo_* 模板曾用于快速生成安全队形，但 9 机测试证明它们会诱导模型退化成
# 重复套模板。它们保留在文件中仅作历史参考/对照，不通过 `from function import *`
# 导出；preflight 也会拒绝 final segment 直接调用 geo_*。
def geo_wide_v(
    n,
    center=(280, 280),
    scale=(230, 230),
    z_layers=(100, 160, 220),
    reverse=False,
    spread=1.0,
):
    """宽 V / 扇形母题。reverse=True 时倒 V；spread 调整展开幅度。"""
    norms = [
        (-1.0, 0.95), (-0.72, 0.45), (-0.45, 0.02), (-0.18, -0.38),
        (0.0, -0.72),
        (0.18, -0.38), (0.45, 0.02), (0.72, 0.45), (1.0, 0.95),
    ]
    if reverse:
        norms = [(nx, -ny) for nx, ny in norms]
    return _shape_points(norms, n, center, _spread_scale(scale, spread), z_layers)


def geo_arrow(
    n,
    center=(280, 280),
    scale=(230, 230),
    z_layers=(100, 160, 220),
    reverse=False,
    spread=1.0,
):
    """斜线推进/箭头母题。reverse=True 时箭头反向；spread 调整展开幅度。"""
    norms = [
        (0.0, -1.0),
        (-0.28, -0.58), (0.28, -0.58),
        (-0.56, -0.18), (0.56, -0.18),
        (-0.84, 0.26), (0.84, 0.26),
        (-0.22, 0.82), (0.22, 0.82),
    ]
    if reverse:
        norms = [(nx, -ny) for nx, ny in norms]
    return _shape_points(norms, n, center, _spread_scale(scale, spread), z_layers)


def geo_box(
    n,
    margin=60,
    z_layers=(100, 160, 220),
    reverse=False,
    spread=1.0,
    center=None,
    width=None,
    height=None,
):
    """边界框线/署名姿态。可用 center/width/height 指定安全矩形。"""
    norms = [
        (0.0, 0.0), (0.5, 0.0), (1.0, 0.0),
        (1.0, 0.5), (1.0, 1.0), (0.5, 1.0),
        (0.0, 1.0), (0.0, 0.5), (0.5, 0.5),
    ]
    if reverse:
        norms = list(reversed(norms))
    if center is not None or width is not None or height is not None:
        cx, cy = center if center is not None else (280, 280)
        value = _safe_spread(spread)
        w = max(220, min(520, float(width if width is not None else 440) * value))
        h = max(220, min(520, float(height if height is not None else 440) * value))
        points = []
        for idx, (nx, ny) in enumerate(_pick_norms(norms, n)):
            z = z_layers[idx % len(z_layers)]
            x = float(cx) + (nx - 0.5) * w
            y = float(cy) + (ny - 0.5) * h
            points.append((clamp_xy(x), clamp_xy(y), clamp_z(z)))
        return points
    margin = _spread_margin(margin, spread)
    span = 560 - 2 * int(margin)
    points = []
    for idx, (nx, ny) in enumerate(_pick_norms(norms, n)):
        z = z_layers[idx % len(z_layers)]
        points.append((clamp_xy(margin + nx * span), clamp_xy(margin + ny * span), clamp_z(z)))
    return points


def geo_diagonal(n, reverse=False, margin=55, z_layers=(100, 160, 220), spread=1.0):
    """斜线推进母题。reverse=True 时反向回卷，spread>1 更靠边界。"""
    points = []
    margin = _spread_margin(margin, spread)
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


def geo_wave(
    n,
    center_y=280,
    amplitude=170,
    margin=55,
    z_layers=(100, 160, 220),
    reverse=False,
    spread=1.0,
):
    """波浪/呼吸母题。reverse=True 反向流动；spread 调整振幅和边界。"""
    points = []
    margin = _spread_margin(margin, spread)
    amplitude = float(amplitude) * _safe_spread(spread)
    if n <= 1:
        return [(280, clamp_xy(center_y), clamp_z(z_layers[0]))]
    for i in range(n):
        ratio = i / (n - 1)
        if reverse:
            ratio = 1 - ratio
        x = margin + ratio * (560 - 2 * margin)
        y = center_y + math.sin(ratio * math.pi * 2) * amplitude
        z = z_layers[(i * 2) % len(z_layers)]
        points.append((clamp_xy(x), clamp_xy(y), clamp_z(z)))
    return points


def geo_grid(n, margin=65, z_layers=(100, 160, 220), reverse=False, spread=1.0):
    """安全分散网格。spread>1 更靠边界，reverse=True 反向取点。"""
    cols = max(1, math.ceil(math.sqrt(n)))
    rows = max(1, math.ceil(n / cols))
    margin = _spread_margin(margin, spread)
    span = 560 - 2 * int(margin)
    points = []
    for i in range(n):
        idx = n - 1 - i if reverse else i
        col = idx % cols
        row = idx // cols
        x = margin + (span * col / max(1, cols - 1))
        y = margin + (span * row / max(1, rows - 1))
        z = z_layers[i % len(z_layers)]
        points.append((clamp_xy(x), clamp_xy(y), clamp_z(z)))
    return points


def _safe_spread(spread):
    try:
        value = float(spread)
    except (TypeError, ValueError):
        value = 1.0
    return max(0.45, min(1.6, value))


def _spread_scale(scale, spread):
    value = _safe_spread(spread)
    if isinstance(scale, (int, float)):
        return (float(scale) * value, float(scale) * value)
    sx, sy = scale
    return (float(sx) * value, float(sy) * value)


def _spread_margin(margin, spread):
    value = _safe_spread(spread)
    if value >= 1:
        return max(35, int(round(float(margin) / value)))
    return min(180, int(round(float(margin) / value)))


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
    min_path_cm = max(0.0, float(min_path_cm))
    min_spacing_cm = max(0.0, float(min_spacing_cm))
    collision_floor_cm = min(58.0, max(45.0, min_spacing_cm * 0.45))

    def evaluate(perm):
        tt_xyz = [targets_xyz[i] for i in perm]
        min_path_spacing = 1e9
        for step in range(0, 51):
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
                    d = (
                        (ai[0] - aj[0]) ** 2
                        + (ai[1] - aj[1]) ** 2
                    ) ** 0.5
                    if d < min_path_spacing:
                        min_path_spacing = d
        path_lengths = [Distance(starts_xyz[i], tt_xyz[i]) for i in range(n)]
        median_path = sorted(path_lengths)[n // 2]
        max_path = max(path_lengths)
        short_penalty = sum(max(0, min_path_cm - d) ** 2 for d in path_lengths)
        spacing_penalty = max(0, min_spacing_cm - min_path_spacing) ** 2
        collision_penalty = max(0, collision_floor_cm - min_path_spacing) ** 3
        safe_spacing = min(min_path_spacing, 120)
        score = (
            safe_spacing * 1800
            + median_path * 900
            + max_path * 80
            - short_penalty * 25
            - spacing_penalty * 350
            - collision_penalty * 50000
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
