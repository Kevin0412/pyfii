#!/usr/bin/env python3
"""Best Assign — 离线排列匹配工具"""
import math, itertools
from enum import Enum
from dataclasses import dataclass


class Strategy(Enum):
    FIRST_MATCH = "first_match"
    MIN_DISTANCE = "min_distance"
    MAX_MIN_DISTANCE = "max_min_distance"
    MIN_MAX_MOVE = "min_max_move"
    MAX_TOTAL_MOVE = "max_total_move"
    MAX_MAX_MOVE = "max_max_move"


@dataclass
class AssignResult:
    permutation: tuple
    min_distance_cm: float
    max_move_cm: float
    total_move_cm: float
    strategy: Strategy


def assign(starts, targets, strategy=Strategy.MIN_DISTANCE):
    """
    离线匹配工具入口。
    starts: [(x0,y0), ...]
    targets: [(x0,y0), ...]
    返回 AssignResult。
    """
    N = len(starts)
    if N <= 7:
        return _full_search(starts, targets, strategy)
    else:
        return _pruned_search(starts, targets, strategy)


def _full_search(starts, targets, strategy):
    N = len(starts)
    best_score = -1e9
    best = None

    for perm in itertools.permutations(range(N)):
        tt = [targets[i] for i in perm]
        min_d = _min_path_distance(starts, tt)
        max_d = max(math.dist(starts[i], tt[i]) for i in range(N))
        total_d = sum(math.dist(starts[i], tt[i]) for i in range(N))

        score = _score(strategy, min_d, max_d, total_d)
        if score > best_score:
            best_score = score
            best = (perm, min_d, max_d, total_d)

    perm, min_d, max_d, total_d = best
    return AssignResult(
        permutation=perm,
        min_distance_cm=min_d,
        max_move_cm=max_d,
        total_move_cm=total_d,
        strategy=strategy,
    )


def _pruned_search(starts, targets, strategy):
    """9机: 启用剪枝"""
    N = len(starts)
    best_score = -1e9
    best = None

    for perm in itertools.permutations(range(N)):
        if _should_prune(perm, starts, targets):
            continue
        tt = [targets[i] for i in perm]
        min_d = _min_path_distance(starts, tt)
        max_d = max(math.dist(starts[i], tt[i]) for i in range(N))
        total_d = sum(math.dist(starts[i], tt[i]) for i in range(N))

        score = _score(strategy, min_d, max_d, total_d)
        if score > best_score:
            best_score = score
            best = (perm, min_d, max_d, total_d)

    if best is None:
        # 剪枝太激进，回退到全搜
        return _full_search(starts, targets, strategy)

    perm, min_d, max_d, total_d = best
    return AssignResult(
        permutation=perm,
        min_distance_cm=min_d,
        max_move_cm=max_d,
        total_move_cm=total_d,
        strategy=strategy,
    )


def _score(strategy, min_d, max_d, total_d):
    if strategy == Strategy.FIRST_MATCH:
        return -max_d  # 第一个安全的 = 最小最大移动距离
    elif strategy == Strategy.MIN_DISTANCE:
        return min_d * 2000 - max_d * 0.01
    elif strategy == Strategy.MAX_MIN_DISTANCE:
        return min_d * 2000 - max_d * 0.01  # 同min_distance，已经是最大化
    elif strategy == Strategy.MIN_MAX_MOVE:
        return -max_d * 100 + min_d * 10
    elif strategy == Strategy.MAX_TOTAL_MOVE:
        return total_d * 10 - max_d * 0.01
    elif strategy == Strategy.MAX_MAX_MOVE:
        return max_d * 100 + min_d * 10
    return min_d * 2000


def _min_path_distance(starts, targets):
    """线性插值路径上的最小距离"""
    N = len(starts)
    md = 1e9
    for ratio in [0.2, 0.4, 0.6, 0.8]:
        for i in range(N):
            for j in range(i + 1, N):
                ai_x = starts[i][0] * ratio + targets[i][0] * (1 - ratio)
                ai_y = starts[i][1] * ratio + targets[i][1] * (1 - ratio)
                aj_x = starts[j][0] * ratio + targets[j][0] * (1 - ratio)
                aj_y = starts[j][1] * ratio + targets[j][1] * (1 - ratio)
                d = math.hypot(ai_x - aj_x, ai_y - aj_y)
                if d < md:
                    md = d
    return md


def _segment_dist(a1, a2, b1, b2):
    """两条线段的最小距离"""
    # 检查端点
    md = min(
        math.hypot(a1[0] - b1[0], a1[1] - b1[1]),
        math.hypot(a1[0] - b2[0], a1[1] - b2[1]),
        math.hypot(a2[0] - b1[0], a2[1] - b1[1]),
        math.hypot(a2[0] - b2[0], a2[1] - b2[1]),
    )
    # 检查线段 a 上的点到线段 b 的垂足
    for t in [0.25, 0.5, 0.75]:
        pa = (a1[0] * (1 - t) + a2[0] * t, a1[1] * (1 - t) + a2[1] * t)
        for u in [0.25, 0.5, 0.75]:
            pb = (b1[0] * (1 - u) + b2[0] * u, b1[1] * (1 - u) + b2[1] * u)
            d = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
            if d < md:
                md = d
    return md


def _should_prune(perm, starts, targets):
    """对向交换且两线段距离 < 51cm → 剪"""
    N = len(starts)
    for i in range(N):
        for j in range(i + 1, N):
            if perm[i] == j and perm[j] == i:
                d = _segment_dist(
                    starts[i],
                    targets[perm[i]],
                    starts[j],
                    targets[perm[j]],
                )
                if d < 51:
                    return True
    return False
