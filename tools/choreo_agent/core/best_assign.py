#!/usr/bin/env python3
"""Best Assign — 全排列搜索最小碰撞分配"""
import itertools
import math


def best_assign(starts, targets):
    """
    starts: [(x0,y0), ...]
    targets: [(x0,y0), ...]
    返回: (permutation, min_distance_cm)
    """
    if len(starts) != len(targets):
        raise ValueError("starts and targets must have the same length")

    N = len(starts)
    best_md = -1
    best_max_move = 1e9
    best_perm = None

    for perm in _candidate_permutations(N, starts, targets):
        tt = [targets[i] for i in perm]
        md = _path_min_distance(starts, tt)
        max_move = max(_distance(starts[i], tt[i]) for i in range(N))
        if md > best_md or (math.isclose(md, best_md) and max_move < best_max_move):
            best_md = md
            best_max_move = max_move
            best_perm = perm

    return best_perm, best_md


def _candidate_permutations(n, starts, targets):
    """Exhaustive for small N; deterministic local search for 9+ drones."""
    if n <= 8:
        yield from itertools.permutations(range(n))
        return

    def evaluate(perm):
        tt = [targets[i] for i in perm]
        md = _path_min_distance(starts, tt)
        max_move = max(_distance(starts[i], tt[i]) for i in range(n))
        return md * 100000 - max_move

    seen = set()
    for seed in _seed_permutations(n, starts, targets):
        perm = _improve_permutation(seed, evaluate)
        if perm not in seen:
            seen.add(perm)
            yield perm


def _seed_permutations(n, starts, targets):
    base = tuple(range(n))
    seeds = [base, tuple(reversed(base))]
    seeds.extend(base[k:] + base[:k] for k in range(1, n))

    start_order = _angle_order(starts)
    target_order = _angle_order(targets)
    for shift in range(n):
        perm = [0] * n
        for pos, start_i in enumerate(start_order):
            perm[start_i] = target_order[(pos + shift) % n]
        seeds.append(tuple(perm))

    seeds.append(_greedy_permutation(starts, targets, prefer_far=False))
    seeds.append(_greedy_permutation(starts, targets, prefer_far=True))
    return seeds


def _improve_permutation(seed, evaluate, max_passes=4):
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
    cx = sum(_xy(p)[0] for p in points) / len(points)
    cy = sum(_xy(p)[1] for p in points) / len(points)
    return [
        i for i, _ in sorted(
            enumerate(points),
            key=lambda item: math.atan2(_xy(item[1])[1] - cy, _xy(item[1])[0] - cx),
        )
    ]


def _greedy_permutation(starts, targets, prefer_far=False):
    remaining = set(range(len(targets)))
    perm = []
    chooser = max if prefer_far else min
    for start in starts:
        target_i = chooser(
            remaining,
            key=lambda idx: _distance(start, targets[idx]),
        )
        remaining.remove(target_i)
        perm.append(target_i)
    return tuple(perm)


def _path_min_distance(starts, targets):
    """7机中任意两机路径线段的最短距离"""
    N = len(starts)
    md = 1e9
    for i in range(N):
        for j in range(i + 1, N):
            d = _segment_distance(
                starts[i], targets[i],
                starts[j], targets[j],
            )
            if d < md:
                md = d
    return md


def _segment_distance(a1, a2, b1, b2):
    """两条线段 AB 和 CD 的最短距离（计算几何精确解）"""
    # 先检查线段是否相交
    if _segments_intersect(a1, a2, b1, b2):
        return 0.0

    # 最短距离 = min(端点到另一线段距离, 端点距离)
    return min(
        _point_to_segment(a1, b1, b2),
        _point_to_segment(a2, b1, b2),
        _point_to_segment(b1, a1, a2),
        _point_to_segment(b2, a1, a2),
    )


def _segments_intersect(a1, a2, b1, b2):
    """两条线段是否相交"""
    d1 = _cross(a2, a1, b1)
    d2 = _cross(a2, a1, b2)
    d3 = _cross(b2, b1, a1)
    d4 = _cross(b2, b1, a2)
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def _cross(a, b, c):
    """叉积 (b-a) × (c-a)"""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_to_segment(p, a, b):
    """点 p 到线段 ab 的最短距离"""
    ax, ay = _xy(a)
    bx, by = _xy(b)
    px, py = _xy(p)

    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay
    denom = abx * abx + aby * aby
    if denom == 0:
        return math.hypot(px - ax, py - ay)

    # 投影参数 t
    t = (apx * abx + apy * aby) / denom

    if t <= 0:
        return math.hypot(px - ax, py - ay)
    elif t >= 1:
        return math.hypot(px - bx, py - by)
    else:
        proj_x = ax + t * abx
        proj_y = ay + t * aby
        return math.hypot(px - proj_x, py - proj_y)


def _distance(a, b):
    ax, ay = _xy(a)
    bx, by = _xy(b)
    return math.hypot(ax - bx, ay - by)


def _xy(point):
    return point[0], point[1]
