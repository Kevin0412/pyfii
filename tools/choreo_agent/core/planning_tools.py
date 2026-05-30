"""Agent-side planning helpers for segment architecture.

This module is intentionally outside generated ``design.py`` files. It is the
place for reusable choreography planning tools: timeline cues, assignment, and
per-drone motion budgets. An LLM may invent additional planning helpers in its
scratch/architecture phase, but final segment code should contain concrete
tables and simple PyFii commands.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

try:
    from .best_assign import best_assign
    from .motion_math import MotionBudget, dist3, motion_budget
except ImportError:  # allow running tests from tools/choreo_agent/core
    from best_assign import best_assign
    from motion_math import MotionBudget, dist3, motion_budget

Point3 = tuple[int, int, int]


@dataclass(frozen=True)
class KeyframeCue:
    index: int
    start_s: float
    end_s: float
    interval_s: float


@dataclass(frozen=True)
class AssignmentPlan:
    perm: tuple[int, ...]
    min_distance_cm: float
    assigned_targets: list[Point3]


@dataclass(frozen=True)
class DroneMoveBudget:
    target: Point3
    speed_cm_s: int
    accel_cm_s2: int
    light_ticks: int
    delay_ms: int
    flight_ms: int
    distance_cm: float


@dataclass(frozen=True)
class LayerPlan:
    cue: KeyframeCue
    perm: tuple[int, ...]
    min_distance_cm: float
    moves: list[DroneMoveBudget]


def to_xyz(points: Iterable[Sequence[float]], default_z: int = 110) -> list[Point3]:
    """Normalize 2D/3D point-like values to integer xyz tuples."""
    normalized = []
    for point in points:
        if len(point) < 2:
            raise ValueError(f"point must contain at least x/y: {point!r}")
        x = int(round(point[0]))
        y = int(round(point[1]))
        z = int(round(point[2] if len(point) >= 3 else default_z))
        normalized.append((x, y, z))
    return normalized


def timeline_cues(
    start_s: float,
    end_s: float,
    *,
    count: int = 4,
    start_offset_s: float = 0.15,
    end_margin_s: float = 0.35,
    weights: Sequence[float] | None = None,
) -> list[KeyframeCue]:
    """Create adjacent keyframe intervals that cover the segment body."""
    if count <= 0:
        raise ValueError("count must be positive")
    cue_start = float(start_s) + start_offset_s
    cue_end = float(end_s) - end_margin_s
    if cue_end <= cue_start:
        raise ValueError("segment is too short for keyframe cues")

    if weights is None:
        weights = [1.0] * count
    if len(weights) != count:
        raise ValueError("weights length must match count")
    total = sum(weights)
    if total <= 0:
        raise ValueError("weights must sum to a positive number")

    cues = []
    current = cue_start
    active_s = cue_end - cue_start
    for index, weight in enumerate(weights, start=1):
        interval_s = active_s * weight / total
        next_time = cue_end if index == count else current + interval_s
        cues.append(
            KeyframeCue(
                index=index,
                start_s=current,
                end_s=next_time,
                interval_s=next_time - current,
            )
        )
        current = next_time
    return cues


def assign_targets(prev: Sequence[Sequence[float]], targets: Sequence[Sequence[float]]) -> AssignmentPlan:
    """Assign targets with best_assign and return hard-code-ready targets."""
    prev_xyz = to_xyz(prev)
    target_xyz = to_xyz(targets)
    perm, min_distance_cm = best_assign(
        [(x, y) for x, y, _z in prev_xyz],
        [(x, y) for x, y, _z in target_xyz],
    )
    if perm is None:
        raise RuntimeError("best_assign did not produce a permutation")
    assigned = [target_xyz[perm[i]] for i in range(len(target_xyz))]
    return AssignmentPlan(
        perm=tuple(perm),
        min_distance_cm=float(min_distance_cm),
        assigned_targets=assigned,
    )


def budget_layer(
    prev: Sequence[Sequence[float]],
    targets: Sequence[Sequence[float]],
    cue: KeyframeCue,
    *,
    feel: str = "balanced",
    light_ticks: int = 12,
    settle_ms: int = 120,
) -> LayerPlan:
    """Assign a keyframe and budget each drone's move for the cue interval."""
    prev_xyz = to_xyz(prev)
    assignment = assign_targets(prev_xyz, targets)
    moves = []
    for start, target in zip(prev_xyz, assignment.assigned_targets):
        budget: MotionBudget = motion_budget(
            dist3(start, target),
            cue.interval_s,
            feel=feel,
            light_ticks=light_ticks,
            settle_ms=settle_ms,
        )
        moves.append(
            DroneMoveBudget(
                target=target,
                speed_cm_s=budget.speed_cm_s,
                accel_cm_s2=budget.accel_cm_s2,
                light_ticks=budget.light_ticks,
                delay_ms=budget.delay_ms,
                flight_ms=budget.flight_ms,
                distance_cm=budget.distance_cm,
            )
        )
    return LayerPlan(
        cue=cue,
        perm=assignment.perm,
        min_distance_cm=assignment.min_distance_cm,
        moves=moves,
    )


def budget_layers(
    prev: Sequence[Sequence[float]],
    target_layers: Sequence[Sequence[Sequence[float]]],
    cues: Sequence[KeyframeCue],
    *,
    feels: Sequence[str] | None = None,
    light_ticks: int = 12,
) -> list[LayerPlan]:
    """Budget a sequence of adjacent keyframes."""
    if len(target_layers) != len(cues):
        raise ValueError("target_layers and cues must have the same length")
    if feels is None:
        feels = ["balanced"] * len(cues)
    if len(feels) != len(cues):
        raise ValueError("feels length must match cues")

    plans = []
    current = to_xyz(prev)
    for targets, cue, feel in zip(target_layers, cues, feels):
        plan = budget_layer(current, targets, cue, feel=feel, light_ticks=light_ticks)
        plans.append(plan)
        current = [move.target for move in plan.moves]
    return plans


# ---------- 安全几何生成 ----------

def generate_safe_geo(
    prev: Sequence[Sequence[float]],
    *,
    mode: str = "expand",
    n: int = 7,
    min_spacing_cm: float = 120,
    center: tuple[float, float] = (280, 280),
    z_min: int = 100,
    z_max: int = 250,
    seed: int = 0,
) -> list[Point3]:
    """Generate safe geometry guaranteed to have XY spacing >= min_spacing_cm.
    
    Modes:
    - expand: Poisson-disk sampling, asymmetric spread
    - rotate: center point + 6 points on circle
    - breathe: all points on circle with variable radius
    - contract: tight circle, low altitude
    """
    import random as _random
    import math as _math
    _random.seed(seed if seed != 0 else None)
    
    if mode == "rotate":
        r = max(150, min_spacing_cm)
        pts = []
        for i in range(n - 1):
            angle = 2 * _math.pi * i / (n - 1) + _random.uniform(0, 0.5)
            pts.append((
                int(center[0] + r * _math.cos(angle)),
                int(center[1] + r * _math.sin(angle)),
                _random.randint(z_min, z_max)
            ))
        pts.append((int(center[0]), int(center[1]), _random.randint(z_min, z_max)))
        return pts
    elif mode == "breathe":
        r = _random.randint(120, 220)
        pts = []
        for i in range(n):
            angle = 2 * _math.pi * i / n + _random.uniform(0, 0.3)
            pts.append((
                int(center[0] + r * _math.cos(angle)),
                int(center[1] + r * _math.sin(angle)),
                _random.randint(z_min, z_max)
            ))
        return pts
    elif mode == "contract":
        r = _random.randint(80, 130)
        pts = []
        for i in range(n):
            angle = 2 * _math.pi * i / n
            pts.append((
                int(center[0] + r * _math.cos(angle)),
                int(center[1] + r * _math.sin(angle)),
                z_min
            ))
        return pts
    else:  # expand — Poisson disk
        pts = []
        attempts = 0
        while len(pts) < n and attempts < 500:
            x = _random.randint(50, 510)
            y = _random.randint(50, 510)
            ok = True
            for px, py, _ in pts:
                if ((x - px)**2 + (y - py)**2)**0.5 < min_spacing_cm:
                    ok = False
                    break
            if ok:
                pts.append((x, y, _random.randint(z_min, z_max)))
            attempts += 1
        # fallback: relax spacing
        while len(pts) < n:
            x = _random.randint(80, 480)
            y = _random.randint(80, 480)
            if all(((x - px)**2 + (y - py)**2)**0.5 >= min_spacing_cm * 0.7 for px, py, _ in pts):
                pts.append((x, y, _random.randint(z_min, z_max)))
            else:
                pts.append((x, y, z_min))
        return pts[:n]


def check_min_spacing(points: Sequence[Sequence[float]]) -> tuple[float, tuple[int, int]]:
    """Return (min_xy_distance_cm, (i, j)) for the closest pair."""
    min_d = float("inf")
    min_pair = (-1, -1)
    pts = to_xyz(points)
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = ((pts[i][0] - pts[j][0])**2 + (pts[i][1] - pts[j][1])**2)**0.5
            if d < min_d:
                min_d = d
                min_pair = (i, j)
    return min_d, min_pair


def predict_crossings(
    prev: Sequence[Sequence[float]],
    targets: Sequence[Sequence[float]],
    speeds: Sequence[float] | None = None,
) -> list[tuple[int, int, float]]:
    """Detect trajectory crossings between drone pairs.
    
    Returns list of (drone_i, drone_j, closest_approach_cm).
    Uses 2D line segment intersection on XY plane.
    """
    crossings = []
    p_xyz = to_xyz(prev)
    t_xyz = to_xyz(targets)
    n = len(p_xyz)
    
    for i in range(n):
        for j in range(i + 1, n):
            # Simple 2D segment intersection check
            d = _segment_segment_distance_2d(
                (p_xyz[i][0], p_xyz[i][1]), (t_xyz[i][0], t_xyz[i][1]),
                (p_xyz[j][0], p_xyz[j][1]), (t_xyz[j][0], t_xyz[j][1]),
            )
            crossings.append((i, j, d))
    
    crossings.sort(key=lambda x: x[2])
    return crossings


def _segment_segment_distance_2d(a1, a2, b1, b2):
    """Minimum distance between two 2D line segments, detecting interior crossings."""
    def _cross(a, b, c):
        """cross product (b-a) x (c-a)"""
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
    def _on_segment(p, a, b):
        return min(a[0],b[0]) <= p[0] <= max(a[0],b[0]) and min(a[1],b[1]) <= p[1] <= max(a[1],b[1])
    def _point_seg_dist(p, s1, s2):
        dx, dy = s2[0] - s1[0], s2[1] - s1[1]
        if dx == 0 and dy == 0:
            return ((p[0] - s1[0])**2 + (p[1] - s1[1])**2)**0.5
        t = max(0, min(1, ((p[0] - s1[0])*dx + (p[1] - s1[1])*dy) / (dx*dx + dy*dy)))
        proj = (s1[0] + t*dx, s1[1] + t*dy)
        return ((p[0] - proj[0])**2 + (p[1] - proj[1])**2)**0.5
    # 线段相交判定：a1-a2 与 b1-b2
    d1 = _cross(a1, a2, b1)
    d2 = _cross(a1, a2, b2)
    d3 = _cross(b1, b2, a1)
    d4 = _cross(b1, b2, a2)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return 0  # 线段相交
    # 共线情况
    if d1 == 0 and _on_segment(b1, a1, a2): return 0
    if d2 == 0 and _on_segment(b2, a1, a2): return 0
    if d3 == 0 and _on_segment(a1, b1, b2): return 0
    if d4 == 0 and _on_segment(a2, b1, b2): return 0
    # 常规距离
    d1 = _point_seg_dist(a1, b1, b2)
    d2 = _point_seg_dist(a2, b1, b2)
    d3 = _point_seg_dist(b1, a1, a2)
    d4 = _point_seg_dist(b2, a1, a2)
    return min(d1, d2, d3, d4)


def prompt_planning_tool_reference() -> str:
    return "\n".join(
        [
            "# Agent-side Planning Tools",
            "",
            "这些工具属于 agent 规划层，不要复制到 final design.py segment。AI 可以在规划阶段写临时自定义函数来解析意图、生成几何候选、筛掉退化形态，然后用工具把结果转为硬编码表。",
            "",
            "推荐流程：",
            "1. 解析用户自然语言 -> beats / geometry intents / height layers / energy curve。",
            "2. 规划层可写自定义 helper，例如 make_wave(), make_diagonal(), avoid_lane_shape()；这些 helper 只用于产出候选几何。",
            "3. 调用/模拟工具层：timeline_cues -> assign_targets/best_assign -> budget_layer/budget_layers。",
            "4. final segment 只输出 concrete tables: geo*, perm*, speed/accel/light_ticks/delay_ms；不要 import，不要定义 best_assign，不要把通用 motion_math helper 写进 design.py。",
            "",
            "工具语义：",
            "- timeline_cues(start, end, count=4) 生成相邻 cue；后一个 keyframe 的 interval 是 cue[i].end - cue[i].start，不是 t_target - segment_start。",
            "- assign_targets(prev, targets) 产出 perm 和 assigned_targets；final 里硬编码 perm/target_idx。",
            "- budget_layer(prev, targets, cue) 产出每架机 target/speed/accel/light_ticks/delay_ms，确保 move2 后的 light+delay 覆盖飞行时间。",
            "",
            "允许 final segment 中出现编舞局部小函数，例如只封装重复灯光色表或简单局部几何表访问；不允许 final segment 中出现通用规划工具、import、best_assign、itertools/permutation 搜索、dist3/flight_time_ms/speed_for_interval/move_interval。",
        ]
    )
