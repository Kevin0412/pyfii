"""Agent 函数库 — DNTG 风格

用法: from function import *
"""

import math
import itertools

# math 函数导出，支持 from function import * 后直接写 sin/cos/pi
sin = math.sin
cos = math.cos
pi = math.pi

__all__ = [
    "Distance",
    "Time",
    "Vel",
    "move2",
    "move_group",
    "move_group_staggered",
    "pulse_group",
    "custom_points",
    "active_min_path_cm",
    "clamp_xy",
    "clamp_z",
    "best_assign",
    "far_assign",
    "safe_assign",
    "verify_timed_clearance",
    "rotate_assign",
    "mirror_assign",
    "swap_assign",
    "keep_assign",
    "spatial_ranks",
    "ripple_delays",
    "split_groups",
    "ripple_move",
    "chain_lane",
    "follow_chain",
    "chain_follow_safe",
    "group_relay",
    "safe_move",
    "apply_light",
    "light_wave",
    "fade_rgb",
    "fade_group",
    "breathe_group",
    "flash_group",
    "beat_ms",
    "auto_init",
    "wait_until",
    "sin",
    "cos",
    "pi",
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

def move2(d, p, t_ms=None, T=100, flying_ms=None):
    """反算速度 → VelXY/VelZ → d.move2。不 delay。

    原理：
    1. v = Vel(start, p, (t_ms-T)/1000)
    2. d.VelXY(v, 2v); d.VelZ(v, 2v)
    3. d.move2(p[0], p[1], p[2])

    flying_ms 是 t_ms 的别名（文档用语）。
    不调用 d.delay()；但会记录预计飞行完成时间，供 auto_init 防止下一段提前开始。
    """
    if t_ms is None:
        t_ms = flying_ms
    if isinstance(t_ms, (list, tuple)):
        t_ms = max(t_ms)
    if t_ms is None:
        raise ValueError("move2 需要时长参数：move2(drone, target, flying_ms)")
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
def custom_points(points, n=None, min_xy_cm=51):
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


# ---------- 时间感知安全分配：按真实错峰时序评估碰撞，与逐帧验证器同模型 ----------
def _norm_schedule(n, delays, flying_ms):
    """把 delays/flying_ms 规整成每架机的 (delay_ms, flying_ms)。delays=None → 全 0（同步）。"""
    if delays is None:
        delays_ms = [0.0] * n
    else:
        delays_ms = [max(0.0, float(v)) for v in delays]
        if len(delays_ms) != n:
            raise ValueError(f"delays count {len(delays_ms)} != {n}")
    if isinstance(flying_ms, (list, tuple)):
        flying_list = [max(1.0, float(v)) for v in flying_ms]
        if len(flying_list) != n:
            raise ValueError(f"flying_ms count {len(flying_list)} != {n}")
    else:
        flying_list = [max(1.0, float(flying_ms))] * n
    return delays_ms, flying_list


def _timed_min_xy(starts_xyz, targets_xyz, delays_ms, flying_list, fps=60, max_samples=300):
    """真实分时轨迹的两两最小 XY 间距（镜像验证器 _add_dense_distance_report 的逐帧 60fps XY 检查）。
    每架机 i：t<delay_i 停在起点；delay_i..delay_i+flying_i 沿直线插值；之后停在终点。
    fps 控制采样密度——默认 60 与验证器一致；过疏会把短暂的近距离别(alias)过去，导致这里算
    安全、验证器却测到碰撞。Z 一律忽略（碰撞门就是 XY-only）。返回 (min_cm, worst_t_ms, (i,j))。"""
    n = len(starts_xyz)
    spans = [delays_ms[i] + flying_list[i] for i in range(n)]
    tmax = max(spans) if spans else 0.0
    steps = max(8, min(int(max_samples), int(tmax / 1000.0 * float(fps))))
    min_d, worst_t, worst_pair = 1e9, 0.0, None
    sx = [s[0] for s in starts_xyz]; sy = [s[1] for s in starts_xyz]
    tx = [t[0] for t in targets_xyz]; ty = [t[1] for t in targets_xyz]
    for s in range(steps + 1):
        t = tmax * s / steps if steps else 0.0
        px = [0.0] * n; py = [0.0] * n
        for i in range(n):
            if t <= delays_ms[i] or flying_list[i] <= 0:
                r = 0.0
            elif t >= spans[i]:
                r = 1.0
            else:
                r = (t - delays_ms[i]) / flying_list[i]
            px[i] = sx[i] + (tx[i] - sx[i]) * r
            py[i] = sy[i] + (ty[i] - sy[i]) * r
        for i in range(n):
            for j in range(i + 1, n):
                d = ((px[i] - px[j]) ** 2 + (py[i] - py[j]) ** 2) ** 0.5
                if d < min_d:
                    min_d, worst_t, worst_pair = d, t, (i, j)
    return min_d, worst_t, worst_pair


def safe_assign(starts, targets, delays=None, flying_ms=2800):
    """时间感知的安全分配。在模型真正要用的错峰时序(delays)+飞行时长下，挑选让**真实分时
    轨迹**两两 XY 间距最大的 targets 排列。

    为什么需要它：best_assign/far_assign 假设全员同步直线（锁步），与逐帧验证器不一致——
    错峰/分组段会“算着安全、实跑相撞”（验证器看真实分时轨迹）。safe_assign 直接按验证器的
    分时 XY 模型评分，选出的排列实跑也安全，省去反复返工。
    用法：先 `delays = ripple_delays(prev, ...)`，再 `targets = safe_assign(prev, geo, delays=delays,
    flying_ms=2800)`，再用同一 delays 做 `ripple_move(drones, targets, 2800, delays, ...)`。
    delays=None 时退化为同步（≈best_assign，不推荐——错峰段务必传 delays）。返回重排后的 targets。"""
    n = len(starts)
    _assert_target_count(starts, targets)
    starts_xyz = [_xyz(p) for p in starts]
    targets_xyz = [_xyz(_target3(t)) for t in targets]
    target_items = [_target3(t) for t in targets]
    delays_ms, flying_list = _norm_schedule(n, delays, flying_ms)
    # 排列搜索只需"排序"用粗采样(快)；选定排列后再用满 60fps 硬校验（见下方地板）做安全判定，
    # 所以排序略糙不影响最终是否抛错。n<=8 是全排列、评估次数多→更粗。
    search_fps = 18 if n > 8 else 12

    def evaluate(perm):
        tt = [targets_xyz[i] for i in perm]
        md, _, _ = _timed_min_xy(starts_xyz, tt, delays_ms, flying_list, fps=search_fps)
        # 可达性：每架机路径不要超过本飞行时长能完成的距离(≈170cm/s×flying×0.9)，
        # 否则段尾“动作未完成”、实跑还会因没飞到位而相撞。超长按平方惩罚。
        overlong = 0.0
        for i in range(n):
            cap = 170.0 * flying_list[i] / 1000.0 * 0.9
            d = Distance(starts_xyz[i], tt[i])
            if d > cap:
                overlong += (d - cap) ** 2
        # 间距奖励封顶 90cm（够安全即可，不为多挤间距换超长路径）
        return min(md, 90.0) * 200.0 - overlong * 3.0

    best_score, best = -1e18, target_items
    for perm in _assignment_permutations(n, starts_xyz, targets_xyz, evaluate):
        score = evaluate(perm)
        if score > best_score:
            best_score = score
            best = [target_items[i] for i in perm]
    # 硬地板：选出的排列若在真实分时轨迹下仍 <51cm，不静默返回相撞排列——
    # 像 custom_points/follow_chain 一样直接抛错，在 preflight 快速失败、给可执行信息，
    # 而不是把一个自己都算出会撞的排列丢给 ripple_move（S02 反复返工的直接原因之一）。
    best_md, best_t, best_pair = _timed_min_xy(
        starts_xyz, [_xyz(t) for t in best], delays_ms, flying_list, fps=60
    )
    if best_md < 51.0 and best_pair is not None:
        raise ValueError(
            f"safe_assign 无法避撞：最优排列在分时轨迹下 d{best_pair[0]}-d{best_pair[1]} "
            f"@{best_t:.0f}ms 仅 {best_md:.1f}cm < 51cm。这组几何+时序装不下该大动作——"
            "请拉大错峰 step_ms、加长 flying_ms、或把目标点表铺开（相邻≥90cm）后重试。"
        )
    return best


def verify_timed_clearance(starts, targets, delays=None, flying_ms=2800):
    """按真实错峰时序回放轨迹，报告全程最小 XY 间距（镜像逐帧 60fps 验证器）。组合完
    ripple_move/分组时序后调用，拿到 go/no-go，省一轮验证器。targets 是最终每机目标
    （drone i → targets[i]）。

    返回 **3 元组** `(ok, min_cm, pair)`：ok=min_cm>=51(bool)，min_cm=全程最小 XY 间距(cm)，
    pair=最近的一对 (i,j)（无则 None）。直接解包用：
        `ok, min_cm, pair = verify_timed_clearance(prev, targets, delays=delays, flying_ms=2800)`"""
    n = len(starts)
    _assert_target_count(starts, targets)
    starts_xyz = [_xyz(p) for p in starts]
    targets_xyz = [_xyz(_target3(t)) for t in targets]
    delays_ms, flying_list = _norm_schedule(n, delays, flying_ms)
    md, _t, pair = _timed_min_xy(starts_xyz, targets_xyz, delays_ms, flying_list, fps=60)
    return (md >= 51.0, round(md, 1), pair)


# ---------- 意图分配家族：转场即编舞，按叙事意图选映射 ----------
def keep_assign(prev, targets):
    """身份保持分配：drone i → targets[i]，不重排。

    用于 per-drone 叙事（palette 色彩身份跟踪、焦点机连续剧情）。
    交叉风险自行用错峰处理（delay(i*150)），validator 逐帧兜底。
    """
    _assert_target_count(prev, targets)
    return [_target3(t) for t in targets]


def rotate_assign(prev, targets, steps=1):
    """旋转分配：按角序把每架机映射到沿环移动 steps 位的目标 —— 整体漩涡/轨道转场。

    同构队形下机间距离恒定（刚体旋转天然安全）；steps 可负反向，
    abs(steps) 越大转动越剧烈。
    """
    _assert_target_count(prev, targets)
    n = len(prev)
    tt = [_target3(t) for t in targets]
    prev_order = _angle_order([_xyz(p) for p in prev])
    target_order = _angle_order(tt)
    mapping = [None] * n
    for rank, drone_i in enumerate(prev_order):
        mapping[drone_i] = tt[target_order[(rank + int(steps)) % n]]
    return mapping


def mirror_assign(prev, targets):
    """镜像对穿分配：每架机飞向自己关于目标质心的反射点附近的目标。

    必须配合错峰（move2 前 `drone.delay(i * 150)`）：同步对穿必撞，
    错峰让各机在不同时刻过中心 —— 人类作品对穿的安全机制。
    """
    _assert_target_count(prev, targets)
    tt = [_target3(t) for t in targets]
    cx = sum(t[0] for t in tt) / len(tt)
    cy = sum(t[1] for t in tt) / len(tt)
    used: set[int] = set()
    mapping = []
    for p in prev:
        px, py, _ = _xyz(p)
        rx, ry = 2 * cx - px, 2 * cy - py
        best_j = min(
            (j for j in range(len(tt)) if j not in used),
            key=lambda j: (tt[j][0] - rx) ** 2 + (tt[j][1] - ry) ** 2,
        )
        used.add(best_j)
        mapping.append(tt[best_j])
    return mapping


def swap_assign(prev, targets, axis="x"):
    """半场交换分配：左右(axis='x')或前后(axis='y')两半互换 —— 组级换位叙事。

    每半场内部用 best_assign 保证路径安全；奇数机时中位机守中。
    """
    _assert_target_count(prev, targets)
    n = len(prev)
    key = 0 if axis == "x" else 1
    tt = [_target3(t) for t in targets]
    prev_rank = sorted(range(n), key=lambda i: _xyz(prev[i])[key])
    target_rank = sorted(range(n), key=lambda j: tt[j][key])
    half = n // 2
    mapping = [None] * n
    if n % 2:
        mapping[prev_rank[half]] = tt[target_rank[half]]
    pairs = [
        (prev_rank[:half], target_rank[n - half:]),
        (prev_rank[n - half:], target_rank[:half]),
    ]
    for drone_idx, target_idx in pairs:
        sub_prev = [prev[i] for i in drone_idx]
        sub_targets = [tt[j] for j in target_idx]
        assigned = best_assign(sub_prev, sub_targets)
        for i, t in zip(drone_idx, assigned):
            mapping[i] = t
    return mapping


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

# ---------- 波次/分组计算器：从当前队形推导时间编排，动序即光序 ----------
def spatial_ranks(points, mode="center_out", origin=None, reverse=False, quantize_cm=30, center=None):
    """按空间结构给每架机一个波次序号 rank（0 = 第一波）。返回与 points 同序的 rank 列表。

    mode:
      center_out — 距质心(或 origin)由近到远；reverse=True 即 edge_in
      sweep_x / sweep_y — 沿 X / Y 扫过
      spiral — 按质心方位角顺序（每机一个波次）
      by_index — 机号顺序
    quantize_cm 把相近的键合并为同一波（对称队形的镜像机自然同波），spiral 不适用。
    center 是 origin 的别名。同一份 rank 同时驱动动作错峰和灯光波次，就是"先动先亮"。
    """
    if origin is None:
        origin = center
    n = len(points)
    if n == 0:
        return []
    xyz = [_xyz(p) for p in points]
    if mode == "by_index":
        ranks = list(range(n))
    elif mode == "spiral":
        order = _angle_order(xyz)
        ranks = [0] * n
        for rank, i in enumerate(order):
            ranks[i] = rank
    else:
        if origin is None:
            origin = (sum(p[0] for p in xyz) / n, sum(p[1] for p in xyz) / n)
        ox, oy = float(origin[0]), float(origin[1])
        if mode == "center_out":
            keys = [((p[0] - ox) ** 2 + (p[1] - oy) ** 2) ** 0.5 for p in xyz]
        elif mode == "sweep_x":
            keys = [p[0] for p in xyz]
        elif mode == "sweep_y":
            keys = [p[1] for p in xyz]
        else:
            raise ValueError(
                f"spatial_ranks mode {mode!r} 不存在；可用: center_out/sweep_x/sweep_y/spiral/by_index"
            )
        q = max(0.0, float(quantize_cm))
        bucketed = [round(k / q) if q > 0 else k for k in keys]
        ordered = sorted(set(bucketed))
        rank_of = {b: r for r, b in enumerate(ordered)}
        ranks = [rank_of[b] for b in bucketed]
    if reverse:
        top = max(ranks)
        ranks = [top - r for r in ranks]
    return ranks


def ripple_delays(points, mode="center_out", step_ms=150, origin=None, reverse=False, quantize_cm=30, center=None, step=None):
    """波次延迟表(ms)：rank * step_ms。直接喂给 ripple_move / light_wave。

    同一份 delays 同时用于动作和灯光，即"先动的先亮"；reverse 反向（边缘先动=收拢）。
    center 是 origin 的别名。step 是 step_ms 的别名。
    """
    if step is not None:
        step_ms = step
    ranks = spatial_ranks(
        points, mode=mode, origin=origin, reverse=reverse, quantize_cm=quantize_cm, center=center
    )
    _step = max(0, int(round(step_ms)))
    return [r * _step for r in ranks]


def split_groups(points, mode="left_right", origin=None, center=None):
    """把当前队形按空间结构分成 0/1 两组，返回每架机的组号列表（问答/异步分组输入）。

    mode: left_right(X 中位) / front_back(Y 中位) / inner_outer(距质心中位) / alternate(角序奇偶)。
    center 是 origin 的别名。
    """
    if origin is None:
        origin = center
    n = len(points)
    if n == 0:
        return []
    xyz = [_xyz(p) for p in points]
    if mode == "alternate":
        order = _angle_order(xyz)
        gid = [0] * n
        for rank, i in enumerate(order):
            gid[i] = rank % 2
        return gid
    if origin is None:
        origin = (sum(p[0] for p in xyz) / n, sum(p[1] for p in xyz) / n)
    ox, oy = float(origin[0]), float(origin[1])
    if mode == "left_right":
        keys = [p[0] for p in xyz]
    elif mode == "front_back":
        keys = [p[1] for p in xyz]
    elif mode == "inner_outer":
        keys = [((p[0] - ox) ** 2 + (p[1] - oy) ** 2) ** 0.5 for p in xyz]
    else:
        raise ValueError(
            f"split_groups mode {mode!r} 不存在；可用: left_right/front_back/inner_outer/alternate"
        )
    order = sorted(range(n), key=lambda i: keys[i])
    gid = [1] * n
    for rank in range((n + 1) // 2):
        gid[order[rank]] = 0
    return gid


# ---------- 母题执行器：波次推进 / 链式跟随 / 分组问答 ----------
def _grad_at(gradient_to, index):
    """gradient_to 为 None 时返回 None（=纯色保持），否则按索引取目标色。"""
    return None if gradient_to is None else _color_at(gradient_to, index)


def _emit_drone_light(drone, color_a, color_b, ticks, interval_ms=100):
    """统一灯光发射：color_b 为 None 时纯色保持，否则 color_a→color_b 逐 tick 渐变。

    两种写法都恰好消耗 ticks*interval_ms，因此可在母题执行器里透明替换、
    不破坏段尾对齐。渐变需要至少 2 帧，ticks<2 时退回纯色。
    """
    if color_b is None or int(ticks) < 2:
        apply_light(drone, color_a, int(ticks), interval_ms)
    else:
        fade_rgb(drone, color_a, color_b, steps=int(ticks), interval_ms=interval_ms)


_RIPPLE_UNSET = object()


def _looks_like_target_table(value, n):
    """Best-effort discriminator for the legacy ``(drones, prev, targets, ...)`` call shape."""
    try:
        return len(value) == n and all(len(point) >= 2 for point in value)
    except (TypeError, ValueError):
        return False


def ripple_move(drones, targets_or_prev=_RIPPLE_UNSET, *args, targets=_RIPPLE_UNSET,
                flying_ms=None, delays=None, colors=_RIPPLE_UNSET,
                hold_ticks=_RIPPLE_UNSET, tail_ms=_RIPPLE_UNSET,
                palette=_RIPPLE_UNSET, gradient_to=_RIPPLE_UNSET, **_ignored):
    """波次推进：每架机等待自己的波次延迟后启动，启动瞬间点亮 —— 先动先亮。

    delays（毫秒表）用 ripple_delays(prev, mode=...) 从当前队形算出；
    所有机段尾自动对齐到 max(delays)+flying_ms+tail_ms，免回正算术。
    palette 是 colors 的别名。给 gradient_to（与 colors 同形）则每架机在亮灯窗口内
    colors[i]→gradient_to[i] 连续渐变（dntg 式飞行中持续变色，色彩更丰富）。
    宽容接受模型常写错的 safe_move 形状：
    ``ripple_move(drones, prev, targets, flying_ms, delays, ...)``，其中 prev 会被忽略。
    位置参数与同名 keyword 重复时以 keyword 为准，避免在 Python 参数绑定阶段浪费一轮。
    返回标准化 targets，可直接赋给 prev。
    """
    positional = list(args)
    resolved_targets = targets if targets is not _RIPPLE_UNSET else targets_or_prev
    if (
        targets is _RIPPLE_UNSET
        and positional
        and _looks_like_target_table(positional[0], len(drones))
    ):
        resolved_targets = positional.pop(0)

    if positional:
        positional_flying_ms = positional.pop(0)
        if flying_ms is None:
            flying_ms = positional_flying_ms
    if positional:
        positional_delays = positional.pop(0)
        if delays is None:
            delays = positional_delays
    if positional and colors is _RIPPLE_UNSET:
        colors = positional.pop(0)
    if positional and hold_ticks is _RIPPLE_UNSET:
        hold_ticks = positional.pop(0)
    if positional and tail_ms is _RIPPLE_UNSET:
        tail_ms = positional.pop(0)
    if positional and palette is _RIPPLE_UNSET:
        palette = positional.pop(0)
    if positional and gradient_to is _RIPPLE_UNSET:
        gradient_to = positional.pop(0)

    if flying_ms is None:
        flying_ms = _ignored.get("t_ms", _ignored.get("duration_ms"))
    if flying_ms is None:
        raise ValueError("ripple_move 需要 flying_ms")
    if resolved_targets is _RIPPLE_UNSET:
        raise ValueError("ripple_move 需要 targets")
    if colors is _RIPPLE_UNSET:
        colors = "#ffffff"
    if hold_ticks is _RIPPLE_UNSET:
        hold_ticks = 4
    if tail_ms is _RIPPLE_UNSET:
        tail_ms = 0
    if palette is _RIPPLE_UNSET:
        palette = None
    if gradient_to is _RIPPLE_UNSET:
        gradient_to = None
    if palette is not None:
        colors = palette
    _assert_target_count(drones, resolved_targets)
    if isinstance(flying_ms, (list, tuple)):
        flying_ms = max(flying_ms)
    if delays is None:
        delays = [0] * len(drones)
    if len(delays) != len(drones):
        raise ValueError(f"delays count {len(delays)} != drones count {len(drones)}")
    delays = [max(0, int(round(v))) for v in delays]
    span = max(delays) if delays else 0
    flying_ms = int(round(flying_ms))
    ticks = max(1, min(int(hold_ticks), max(1, flying_ms // 100)))
    normalized = []
    for i, drone in enumerate(drones):
        if delays[i]:
            drone.delay(delays[i])
        target = _target3(resolved_targets[i])
        move2(drone, target, flying_ms)
        _emit_drone_light(drone, _color_at(colors, i), _grad_at(gradient_to, i), ticks)
        drone.delay(max(0, flying_ms - ticks * 100 + (span - delays[i]) + int(tail_ms)))
        normalized.append(target)
    return normalized


def follow_chain(drones, waypoints, hop_ms, lag_hops=1, colors="#ffffff", min_xy_cm=51.0,
                 hold_ticks=2, palette=None, gradient_to=None):
    """链式跟随（蛇形/领舞）：头机沿 waypoints 逐点推进，后机依次延迟 lag_hops 跳走同一路径。

    - 进链顺序按当前位置距 waypoints[0] 由近到远（自然蛇形），进链瞬间点亮 —— 先动先亮。
    - 需要 len(waypoints) ≥ (机数-1)*lag_hops + 1；结束时队伍停在路径末端连续 lag 间隔点上。
    - 安全由链上间距保证：任意相距 k*lag_hops 跳的波点对 XY 间距必须 ≥ min_xy_cm，否则直接抛错。
    - 每架机总耗时都等于 len(waypoints)*hop_ms，段尾天然对齐。
    palette 是 colors 的别名；gradient_to（按进链 rank 取）则进链亮灯做色相渐变。
    返回每架机的结束点（与 drones 同序），可直接赋给 prev。
    """
    if palette is not None:
        colors = palette
    n = len(drones)
    wps = [_target3(w) for w in waypoints]
    H = len(wps)
    lag = max(1, int(lag_hops))
    if H < 2:
        raise ValueError("follow_chain 至少需要 2 个波点")
    need = (n - 1) * lag + 1
    if H < need:
        raise ValueError(
            f"follow_chain 波点不足：{n} 机 lag_hops={lag} 需要至少 {need} 个波点，目前 {H} 个"
        )
    worst, pair = 1e9, (0, 0)
    for k in range(1, n):
        gap = k * lag
        for j in range(gap, H):
            d = ((wps[j][0] - wps[j - gap][0]) ** 2 + (wps[j][1] - wps[j - gap][1]) ** 2) ** 0.5
            if d < worst:
                worst, pair = d, (j - gap, j)
    if worst < float(min_xy_cm):
        raise ValueError(
            f"follow_chain 链上间距不足：波点{pair[0]}-波点{pair[1]} XY 距离 {worst:.1f}cm"
            f" < {float(min_xy_cm):.0f}cm（两机会同时占据这两点）— 增大波点间距或减少机数重叠"
        )
    hop_ms = int(round(hop_ms))
    ticks = max(1, min(int(hold_ticks), max(1, hop_ms // 100)))
    order = sorted(range(n), key=lambda i: (
        (float(getattr(drones[i], "x", 0)) - wps[0][0]) ** 2
        + (float(getattr(drones[i], "y", 0)) - wps[0][1]) ** 2
    ))
    ends = [None] * n
    for rank, di in enumerate(order):
        drone = drones[di]
        if rank:
            drone.delay(rank * lag * hop_ms)
        move2(drone, wps[0], hop_ms)
        _emit_drone_light(drone, _color_at(colors, rank), _grad_at(gradient_to, rank), ticks)
        drone.delay(hop_ms - ticks * 100)
        last = H - 1 - rank * lag
        for k in range(1, last + 1):
            move2(drone, wps[k], hop_ms)
            drone.delay(hop_ms)
        ends[di] = wps[last]
    return ends


def _chain_worst_spacing(wps, lag_hops=1, n=None):
    """Return the worst XY spacing among wavepoints that can be occupied together."""
    lag = max(1, int(lag_hops))
    count = int(n) if n is not None else len(wps)
    worst, pair = 1e9, (0, 0)
    for k in range(1, max(2, count)):
        gap = k * lag
        for j in range(gap, len(wps)):
            d = ((wps[j][0] - wps[j - gap][0]) ** 2 + (wps[j][1] - wps[j - gap][1]) ** 2) ** 0.5
            if d < worst:
                worst, pair = d, (j - gap, j)
    return worst, pair


def chain_lane(control_points, count=None, spacing_cm=65.0, min_xy_cm=51.0, lag_hops=1):
    """把少量控制点扩展为安全链式跟随波点。

    LLM 不擅长手写 9-12 个蛇形 waypoints，常把相邻/回折点写到 40cm 内导致
    `follow_chain` 运行期抛错。chain_lane 只让它给 2-5 个控制点，本函数按固定
    间距重采样出波点，并在返回前用 follow_chain 同一套「同时占位」XY 间距规则检查。

    参数：
    - control_points: [(x,y,z), ...]，至少 2 个；可以是起点→中继→终点。
    - count: 需要的波点数；不传则尽量返回控制点数，但 chain_follow_safe 会自动计算。
    - spacing_cm: 相邻波点目标间距，默认 65cm，建议不要低于 60。
    - min_xy_cm: 硬下限，默认 51cm。
    - lag_hops: 跟随间隔；用于检查可能同时占位的波点对。
    """
    cps = [_target3(p) for p in control_points]
    if len(cps) < 2:
        raise ValueError("chain_lane 至少需要 2 个 control_points")
    need = int(count) if count is not None else len(cps)
    if need < 2:
        raise ValueError("chain_lane count 至少为 2")
    step = max(float(spacing_cm), float(min_xy_cm) + 4.0)
    if step < 1:
        raise ValueError("chain_lane spacing_cm 必须为正数")

    out = [cps[0]]
    cur = cps[0]
    remaining_to_next = step
    for nxt in cps[1:]:
        seg_len = ((nxt[0] - cur[0]) ** 2 + (nxt[1] - cur[1]) ** 2) ** 0.5
        if seg_len <= 1e-6:
            cur = nxt
            continue
        while seg_len + 1e-6 >= remaining_to_next and len(out) < need:
            ratio = remaining_to_next / seg_len
            point = _target3((
                cur[0] + (nxt[0] - cur[0]) * ratio,
                cur[1] + (nxt[1] - cur[1]) * ratio,
                cur[2] + (nxt[2] - cur[2]) * ratio,
            ))
            out.append(point)
            cur = point
            seg_len = ((nxt[0] - cur[0]) ** 2 + (nxt[1] - cur[1]) ** 2) ** 0.5
            remaining_to_next = step
        remaining_to_next -= seg_len
        cur = nxt
        if len(out) >= need:
            break

    if len(out) < need:
        raise ValueError(
            f"chain_lane 路径太短：需要 {need} 个波点（约 {(need - 1) * step:.0f}cm 路径），"
            f"目前只生成 {len(out)} 个；请拉长 control_points 或降低 spacing_cm（但不得低于 51cm）"
        )

    worst, pair = _chain_worst_spacing(out, lag_hops=lag_hops, n=min(need, len(out)))
    if worst < float(min_xy_cm):
        raise ValueError(
            f"chain_lane 波点回折过近：波点{pair[0]}-波点{pair[1]} XY 距离 {worst:.1f}cm"
            f" < {float(min_xy_cm):.0f}cm；请把控制点改成更开阔的单向路径或增大 spacing_cm"
        )
    return out


def chain_follow_safe(drones, control_points, hop_ms, lag_hops=1, colors="#ffffff",
                      min_xy_cm=51.0, spacing_cm=65.0, extra_hops=1,
                      hold_ticks=2, palette=None, gradient_to=None):
    """安全链式跟随：控制点 → 安全波点 → follow_chain。

    这是 chain-follow-phrase 的首选入口。它保持「领机起步、后机按 hop_ms 间隔
    跟随同一路径」语义，但不要求 LLM 手写每个 waypoint。默认比最低需求多 1 个
    extra_hop，让头机真正向前游走，9 机 hop_ms=580 时总耗时约 5.8s。
    返回值与 follow_chain 一样：每架机结束点（可赋给 prev）。
    """
    if palette is not None:
        colors = palette
    n = len(drones)
    lag = max(1, int(lag_hops))
    extra = max(0, int(extra_hops))
    need = (n - 1) * lag + 1 + extra
    wps = chain_lane(
        control_points,
        count=need,
        spacing_cm=max(float(spacing_cm), float(min_xy_cm) + 4.0),
        min_xy_cm=min_xy_cm,
        lag_hops=lag,
    )
    return follow_chain(
        drones,
        wps,
        hop_ms,
        lag_hops=lag,
        colors=colors,
        min_xy_cm=min_xy_cm,
        hold_ticks=hold_ticks,
        gradient_to=gradient_to,
    )


def group_relay(drones, targets, group_ids=None, flying_ms=None, colors=("#ff6040", "#4060ff"),
                hold_ticks=4, gap_ms=200, lead_group=0, palette=None, gradient_to=None,
                gids=None):
    """分组问答接力：lead 组先动（另一组原地亮灯应答），到位后另一组再动 —— 组色对话。

    group_ids 用 split_groups(prev, mode=...) 从当前队形算出；colors[g] 是 g 组色。
    总时长 = 2*flying_ms + gap_ms，所有机段尾自动对齐。palette 是 colors 的别名。
    给 gradient_to（与 colors 同形的两组色）则每架机亮灯做组色→目标色渐变。
    返回标准化 targets。
    """
    if group_ids is None:
        group_ids = gids
    if group_ids is None:
        raise ValueError("group_relay 需要 group_ids/gids")
    if flying_ms is None:
        raise ValueError("group_relay 需要 flying_ms")
    if palette is not None:
        colors = palette
    _assert_target_count(drones, targets)
    if len(group_ids) != len(drones):
        raise ValueError(f"group_ids count {len(group_ids)} != drones count {len(drones)}")
    flying_ms = int(round(flying_ms))
    gap = max(0, int(round(gap_ms)))
    ticks = max(1, min(int(hold_ticks), max(1, flying_ms // 100)))
    resp_ticks = max(1, (flying_ms + gap) // 100)
    two_group = lambda spec, g: (
        spec[g] if isinstance(spec, (list, tuple)) and len(spec) >= 2 else spec
    )
    normalized = []
    for i, drone in enumerate(drones):
        g = int(group_ids[i]) % 2
        target = _target3(targets[i])
        color = _color_at(two_group(colors, g), i)
        color_b = None if gradient_to is None else _color_at(two_group(gradient_to, g), i)
        if g == int(lead_group) % 2:
            move2(drone, target, flying_ms)
            _emit_drone_light(drone, color, color_b, ticks)
            drone.delay(flying_ms - ticks * 100 + gap + flying_ms)
        else:
            _emit_drone_light(drone, color, color_b, resp_ticks)
            drone.delay(max(0, flying_ms + gap - resp_ticks * 100))
            move2(drone, target, flying_ms)
            _emit_drone_light(drone, color, color_b, ticks)
            drone.delay(flying_ms - ticks * 100)
        normalized.append(target)
    return normalized


def safe_move(drones, prev, geo, flying_ms, mode="wave", step_ms=150,
              colors="#ffffff", gradient_to=None, hold_ticks=4, gap_ms=250,
              relay_split="left_right", light=None, color=None, palette=None,
              ticks=None, light_ticks=None, **_ignored):
    """融合「安全分配 + 错峰 + 执行」为一次调用：用来验证无碰撞的错峰时序，就是真正飞的时序——
    safe_assign 的保证不会被「手搓 move2 用了别的 delay」或「分配后又改时序」破坏（密集/对穿段
    反复返工的直接原因）。prev=当前队形，geo=目标点表（custom_points 产物），返回飞完后的新 prev，
    可直接赋给 prev。

    宽容签名：灯光用 colors/gradient_to（light/color/palette 是 colors 别名，ticks/light_ticks 是
    hold_ticks 别名）；safe_move 自己算错峰，传入的 delays/speed/accel 等会被忽略（自带安全时序）。

    mode="wave"（默认，错峰大动作/密集承接首选）：
      delays = ripple_delays(prev, step_ms) → targets = safe_assign(prev, geo, delays, flying_ms)
      → ripple_move(drones, targets, flying_ms, delays)（同一 delays）。
      若该几何 + 该错峰装不下（safe_assign 抛错）→ 自动降级到 relay。
    mode="relay"（对穿/大交叉首选）：
      gids = split_groups(prev, relay_split)，far_assign 取交叉排列，group_relay 顺序飞
      （lead 组清场后另一组再动 = 零跨组交叉）；按真实接力时序自检，必要时自动放大 gap。
    彻底装不下则抛 ValueError（附最近对/间距）——把目标点表铺开（相邻≥90cm）或减少同时交叉的机数。
    勿再照抄预算表 delay_ms 手搓 move2 做错峰/对穿——那会「算着安全实跑撞」。"""
    # 宽容别名：模型常把 light/color/palette、ticks/light_ticks 当 kwargs 传进来（来自 apply_light/
    # ripple_move 的习惯）——映射而非崩溃，让 safe_move 难以被误用。
    for _alias in (palette, color, light):
        if _alias is not None:
            colors = _alias
            break
    if ticks is not None:
        hold_ticks = ticks
    elif light_ticks is not None:
        hold_ticks = light_ticks
    n = len(drones)
    if isinstance(flying_ms, (list, tuple)):
        flying_ms = max(flying_ms)
    flying_ms = int(round(flying_ms))

    def _do_relay():
        # lead 组在 [0, flying]、另一组在 [flying+gap, 2*flying+gap] 飞（group_relay 的真实时序）。
        # 用这份接力时序喂 safe_assign：它按真实分时轨迹挑无碰撞排列并 60fps 硬校验，
        # 同一排列直接交给 group_relay 执行——验证的时序就是飞的时序。
        gids = split_groups(prev, mode=relay_split)
        lead = 0
        last_err = None
        for gap in (int(gap_ms), int(gap_ms) + 400, int(gap_ms) + 900):
            relay_delays = [0 if (int(gids[i]) % 2) == (lead % 2) else (flying_ms + gap)
                            for i in range(n)]
            try:
                targets = safe_assign(prev, geo, delays=relay_delays, flying_ms=flying_ms)
            except ValueError as e:  # 这个 gap 下装不下，放大 gap 再试
                last_err = e
                continue
            group_relay(drones, targets, gids, flying_ms, colors=colors,
                        hold_ticks=hold_ticks, gap_ms=gap, lead_group=lead,
                        gradient_to=gradient_to)
            return [tuple(_target3(t)) for t in targets]
        raise ValueError(
            f"safe_move(relay) 仍相撞（已试到 gap≥{int(gap_ms) + 900}ms）："
            f"{last_err}。顺序接力也清不开——多为静止组挡住移动组的 XY 航线（同 XY 巷的对穿）；"
            "请改 route-around（两组走不同 XY 带）或把目标点表铺开（相邻≥90cm）。"
        )

    if str(mode) == "relay":
        return _do_relay()
    # wave（默认）：safe_assign 在所选错峰下 60fps 硬校验，过门即用同一 delays 执行
    delays = ripple_delays(prev, step_ms=int(step_ms))
    try:
        targets = safe_assign(prev, geo, delays=delays, flying_ms=flying_ms)
    except ValueError:
        # by_index 错峰装不下该交叉 → 顺序接力（零跨组交叉）
        return _do_relay()
    ripple_move(drones, targets, flying_ms, delays, colors=colors,
                hold_ticks=hold_ticks, gradient_to=gradient_to)
    return [tuple(_target3(t)) for t in targets]


# ---------- 灯光 ----------
def apply_light(drone, color_hex: str, ticks: int, interval_ms: int = 100):
    """灯光：ticks 次 TurnOnAll，每次 interval_ms。总耗时 ticks*interval_ms。"""
    for _ in range(ticks):
        drone.TurnOnAll(color_hex)
        drone.delay(interval_ms)


def _rgb(color):
    """颜色解析：'#rrggbb' / 'rrggbb' / (r,g,b) → (r,g,b) 整数三元组。"""
    if isinstance(color, (list, tuple)) and len(color) == 3:
        return tuple(max(0, min(255, int(round(float(v))))) for v in color)
    if isinstance(color, str):
        s = color.lstrip("#")
        if len(s) == 6:
            return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    raise ValueError(f"无法解析颜色: {color!r}（支持 '#rrggbb' 或 (r,g,b)）")


def light_wave(drones, delays, colors=None, hold_ticks=6, tail_ms=0, palette=None, gradient_to=None):
    """静止队形上的灯光涟漪：按 delays 依次点亮，段尾对齐（不移动）。

    与 ripple_delays 配合：用与动作同一份 delays（或定格段单独算）即光波扫过队形。
    每架机总耗时 = max(delays) + hold_ticks*100 + tail_ms。palette 是 colors 的别名。
    给 gradient_to（与 colors 同形）则光波过处每架机 colors[i]→gradient_to[i] 渐变
    （定格队形上的流光溢彩）。返回消耗的毫秒数。
    """
    if palette is not None:
        colors = palette
    if colors is None:
        colors = "#ffffff"
    if len(delays) != len(drones):
        raise ValueError(f"delays count {len(delays)} != drones count {len(drones)}")
    delays = [max(0, int(round(v))) for v in delays]
    span = max(delays) if delays else 0
    ticks = max(1, int(hold_ticks))
    for i, drone in enumerate(drones):
        if delays[i]:
            drone.delay(delays[i])
        _emit_drone_light(drone, _color_at(colors, i), _grad_at(gradient_to, i), ticks)
        drone.delay(span - delays[i] + max(0, int(tail_ms)))
    return span + ticks * 100 + max(0, int(tail_ms))


def fade_rgb(drone, c_from, c_to, steps=12, interval_ms=100):
    """单机颜色渐变：c_from→c_to 线性插值 steps 步（dntg 式"持续变色"）。

    总耗时 steps*interval_ms。返回消耗的毫秒数。
    """
    a, b = _rgb(c_from), _rgb(c_to)
    steps = max(2, int(steps))
    for s in range(steps):
        t = s / (steps - 1)
        drone.TurnOnAll(tuple(int(round(a[c] + (b[c] - a[c]) * t)) for c in range(3)))
        drone.delay(int(interval_ms))
    return steps * int(interval_ms)


def fade_group(drones, c_from, c_to, duration_ms=1500, interval_ms=100):
    """全队同步渐变（收束/过渡）：duration_ms 内 c_from→c_to。返回消耗的毫秒数。"""
    duration_ms = max(200, int(round(duration_ms)))
    interval_ms = max(50, int(interval_ms))
    steps = max(2, duration_ms // interval_ms)
    rem = duration_ms - steps * interval_ms
    for drone in drones:
        fade_rgb(drone, c_from, c_to, steps, interval_ms)
        if rem > 0:
            drone.delay(rem)
    return duration_ms


def breathe_group(drones, color, cycles=2, period_ms=1600, floor=0.18, interval_ms=100):
    """呼吸灯：亮度从满亮按余弦凹陷到 floor 再回满，cycles 个周期（静止持灯段首选）。

    返回消耗的毫秒数（所有机相同，段尾对齐）。
    """
    base = _rgb(color)
    cycles = max(1, int(cycles))
    interval_ms = max(50, int(interval_ms))
    steps_per = max(4, int(period_ms) // interval_ms)
    lo = max(0.0, min(1.0, float(floor)))
    for drone in drones:
        for s in range(cycles * steps_per):
            k = lo + (1.0 - lo) * 0.5 * (1.0 + cos(2 * pi * (s % steps_per) / steps_per))
            drone.TurnOnAll(tuple(int(round(v * k)) for v in base))
            drone.delay(interval_ms)
    return cycles * steps_per * interval_ms


def flash_group(drones, color, times=3, on_ms=250, off_ms=150, alt_color=None):
    """全队同步频闪（强拍/结尾宣言）：times 次亮-灭；alt_color 时双色交替。

    结束后自动回亮 color，避免落入黑灯静止。返回消耗的毫秒数。
    """
    times = max(1, int(times))
    on_ms = max(100, int(on_ms))
    off_ms = max(50, int(off_ms))
    for drone in drones:
        for t in range(times):
            c = color if (alt_color is None or t % 2 == 0) else alt_color
            drone.TurnOnAll(_rgb(c))
            drone.delay(on_ms)
            drone.TurnOffAll()
            drone.delay(off_ms)
        drone.TurnOnAll(_rgb(color))
    return times * (on_ms + off_ms)


def beat_ms(bpm, beats=1.0):
    """节拍转毫秒：把动作/灯光时长贴到音乐拍上。beat_ms(120, 4) = 2000ms。"""
    return int(round(60000.0 / max(1e-6, float(bpm)) * float(beats)))

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
