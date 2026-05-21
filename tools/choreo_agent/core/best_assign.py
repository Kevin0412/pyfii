#!/usr/bin/env python3
"""Best Assign — 全排列搜索最小碰撞分配"""
import math, itertools


def best_assign(starts, targets):
    """
    starts: [(x0,y0), ...]  7个起点
    targets: [(x0,y0), ...]  7个目标
    返回: [(permutation), min_distance_cm]
    """
    N = len(starts)
    best_md = -1
    best_perm = None

    for perm in itertools.permutations(range(N)):
        tt = [targets[i] for i in perm]
        md = _path_min_distance(starts, tt)

        if md > best_md:
            best_md = md
            best_perm = perm

    return best_perm, best_md


def _path_min_distance(starts, targets):
    """4个采样点上的最小两机距离"""
    N = len(starts)
    md = 1e9
    for ratio in [0.2, 0.4, 0.6, 0.8]:
        for i in range(N):
            for j in range(i + 1, N):
                ax = starts[i][0] * ratio + targets[i][0] * (1 - ratio)
                ay = starts[i][1] * ratio + targets[i][1] * (1 - ratio)
                bx = starts[j][0] * ratio + targets[j][0] * (1 - ratio)
                by = starts[j][1] * ratio + targets[j][1] * (1 - ratio)
                d = math.hypot(ax - bx, ay - by)
                if d < md:
                    md = d
    return md
