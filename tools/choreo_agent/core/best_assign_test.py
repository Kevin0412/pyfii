#!/usr/bin/env python3
"""best_assign 离线工具测试"""
import sys, math, itertools
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

N = 7  # F400

# ====== 剪枝规则 ======
def prune(perm):
    """对向交换必然交叉 → 剪掉"""
    for i in range(N):
        for j in range(i + 1, N):
            if perm[i] == j and perm[j] == i:
                return True
    return False


# ====== 匹配策略 ======
def first_match(starts, targets):
    """第一个不碰撞的排列"""
    for perm in itertools.permutations(range(N)):
        if prune(perm):
            continue
        tt = [targets[i] for i in perm]
        min_d = min_path_distance(starts, tt)
        if min_d >= 51:
            return perm, min_d
    return None, 0


def min_distance(starts, targets):
    """最大化路径最小间距（最安全）"""
    best_score, best_perm, best_min_d = -1e9, None, 0
    for perm in itertools.permutations(range(N)):
        if prune(perm):
            continue
        tt = [targets[i] for i in perm]
        min_d = min_path_distance(starts, tt)
        max_d = max(math.dist(starts[i], tt[i]) for i in range(N))
        score = min_d * 2000 - max_d * 0.01
        if score > best_score:
            best_score = score
            best_perm = perm
            best_min_d = min_d
    return best_perm, best_min_d


def min_max_move(starts, targets):
    """最小化最远移动距离（最快完成）"""
    best_max, best_perm, best_min_d = 1e9, None, 0
    for perm in itertools.permutations(range(N)):
        if prune(perm):
            continue
        tt = [targets[i] for i in perm]
        min_d = min_path_distance(starts, tt)
        if min_d < 51:
            continue
        max_d = max(math.dist(starts[i], tt[i]) for i in range(N))
        if max_d < best_max:
            best_max = max_d
            best_perm = perm
            best_min_d = min_d
    return best_perm, best_min_d


def max_total_move(starts, targets):
    """最大化总移动距离（视觉丰富）"""
    best_total, best_perm, best_min_d = -1e9, None, 0
    for perm in itertools.permutations(range(N)):
        if prune(perm):
            continue
        tt = [targets[i] for i in perm]
        min_d = min_path_distance(starts, tt)
        if min_d < 51:
            continue
        total = sum(math.dist(starts[i], tt[i]) for i in range(N))
        if total > best_total:
            best_total = total
            best_perm = perm
            best_min_d = min_d
    return best_perm, best_min_d


def min_path_distance(starts, targets):
    """线性插值路径上的最小距离"""
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


# ====== 测试 ======
starts = [(60, 120), (180, 60), (350, 60), (500, 160), (500, 380), (350, 480), (160, 480)]
targets = [(280 + 140 * math.cos(2 * math.pi * i / N), 280 + 140 * math.sin(2 * math.pi * i / N)) for i in range(N)]

print("=== best_assign 测试 ===")
print(f"start: {len(starts)} drones scattered")
print(f"target: {len(targets)}-point ring r=140")

for name, fn in [
    ("first_match", first_match),
    ("min_distance(安全)", min_distance),
    ("min_max_move(最快)", min_max_move),
    ("max_total_move(丰富)", max_total_move),
]:
    perm, min_d = fn(starts, targets)
    if perm:
        max_d = max(math.dist(starts[i], targets[perm[i]]) for i in range(N))
        print(f"  {name}: min_d={min_d:.1f}cm max_move={max_d:.0f}cm perm={perm}")
    else:
        print(f"  {name}: NO SAFE MATCH")

# 剪枝效果
total = 5040
pruned = sum(1 for p in itertools.permutations(range(N)) if prune(p))
print(f"\n剪枝: {pruned}/{total} ({pruned*100//total}%) 对向交换被剪")
print("OK")
