#!/usr/bin/env python3
"""AI 编舞产物退化检测工具。

对 output/ 中的 AI 生成 .fii 产物做批量轨迹读回，检测以下退化模式：
- 车道退化：某架机的 X 或 Y 活动范围锁在窄道（<150cm）
- 绕圈退化：6 架机绕中心的角度排序从不变化
- 中心锚点：一架机活动范围远小于其他机
- 安全钳制：XY 跨度远小于场地极限（560×560）
- 动作连贯度：相邻帧位移变化的标准差（jerk）

用法：
    cd /path/to/pyfii
    PYTHONPATH=src python tools/detect_degradation.py [--path output/some_project] [--fps 60]
"""

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from pyfii import read as pf  # noqa: E402


FIELD_LIMIT_XY = 560
FIELD_LIMIT_Z = 250
LANE_THRESHOLD_CM = 150          # 单轴范围小于此值标记车道
CENTER_RANGE_RATIO = 0.25        # 范围小于平均的此比例标记中心锚点
CENTER_ABS_MAX = 80              # 中心锚点的绝对范围上限
CIRCLE_FROZEN_RATIO = 0.8        # 角度顺序不变比例超过此值标记绕圈
SAFETY_CLAMP_RATIO = 0.85        # XY跨度小于场地极限的此比例标记安全钳制


def detect_lane(data, verbose=True):
    """检测车道退化：每架机单轴范围过窄。"""
    n = len(data)
    lanes = []
    for i in range(n):
        trace = data[i]
        xs = [p[1] for p in trace if p[1] > 0]
        ys = [p[2] for p in trace if p[1] > 0]
        if not xs:
            continue
        xr, yr = max(xs) - min(xs), max(ys) - min(ys)
        if xr < LANE_THRESHOLD_CM and yr > 200:
            lanes.append((i, "X", xr, yr))
        elif yr < LANE_THRESHOLD_CM and xr > 200:
            lanes.append((i, "Y", yr, xr))
    if verbose and lanes:
        for i, axis, narrow_r, wide_r in lanes:
            print(f"  LANE d{i+1}: {axis} locked at {narrow_r:.0f}cm (other axis {wide_r:.0f}cm)")
    return lanes


def detect_center_anchor(data, verbose=True):
    """检测中心锚点：一架机范围远小于平均。"""
    n = len(data)
    ranges = []
    for i in range(n):
        xs = [p[1] for p in data[i] if p[1] > 0]
        ys = [p[2] for p in data[i] if p[1] > 0]
        ranges.append((max(xs) - min(xs), max(ys) - min(ys)) if xs else (0, 0))

    avg_r = np.mean([x + y for x, y in ranges])
    for i, (xr, yr) in enumerate(ranges):
        total = xr + yr
        if total < avg_r * CENTER_RANGE_RATIO and total < CENTER_ABS_MAX * 2:
            if verbose:
                xs = [p[1] for p in data[i] if p[1] > 0]
                ys = [p[2] for p in data[i] if p[1] > 0]
                print(f"  CENTER d{i+1}: range=({xr:.0f},{yr:.0f}) vs avg={avg_r:.0f}, pos=({np.mean(xs):.0f},{np.mean(ys):.0f})")
            return i
    return None


def detect_circle_rigid(data, center_drone=None, verbose=True):
    """检测绕圈退化：各机绕中心的角度排序是否冻结。"""
    n = len(data)
    n_frames = min(len(d) for d in data)
    
    if center_drone is not None:
        xs_c = [p[1] for p in data[center_drone] if p[1] > 0]
        ys_c = [p[2] for p in data[center_drone] if p[1] > 0]
        cx = np.mean(xs_c) if xs_c else 280
        cy = np.mean(ys_c) if ys_c else 280
    else:
        cx, cy = 280, 280

    last_order = None
    frozen = 0
    samples = 0
    for t in range(0, n_frames, 60):  # 每秒采样
        angles = []
        for i in range(n):
            if i == center_drone:
                continue
            if t < len(data[i]):
                p = data[i][t]
                if p[1] > 0:
                    ang = np.arctan2(p[2] - cy, p[1] - cx)
                    angles.append((ang % (2 * np.pi), i))
        if len(angles) >= 5:
            angles.sort()
            order = tuple(i for _, i in angles)
            samples += 1
            if last_order is not None and order == last_order:
                frozen += 1
            last_order = order

    if samples > 1:
        ratio = frozen / (samples - 1)
        if ratio >= CIRCLE_FROZEN_RATIO:
            if verbose:
                print(f"  CIRCLE-RIGID: angle order frozen {frozen}/{samples - 1} times ({ratio:.0%})")
            return ratio
    return None


def compute_jerk(data, verbose=True):
    """计算每架机的动作连贯度（jerk）。"""
    n = len(data)
    jerks = []
    for i in range(n):
        trace = data[i]
        xs = [p[1] for p in trace if p[1] > 0]
        ys = [p[2] for p in trace if p[1] > 0]
        if len(xs) > 20:
            dx = np.diff(xs[::10])
            dy = np.diff(ys[::10])
            dists = np.sqrt(dx**2 + dy**2)
            j = np.std(np.diff(dists)) if len(dists) > 2 else 0
            jerks.append(j)
        else:
            jerks.append(0)
    if verbose:
        print(f"  JERK: {[f'{j:.1f}' for j in jerks]}")
    return jerks


def detect_safety_clamp(data, verbose=True):
    """检测安全钳制：XY 跨度是否远小于场地极限。"""
    all_x = [p[1] for d in data for p in d if p[1] > 0]
    all_y = [p[2] for d in data for p in d if p[1] > 0]
    if not all_x:
        return None
    xs, ys = max(all_x) - min(all_x), max(all_y) - min(all_y)
    clamp = xs < FIELD_LIMIT_XY * SAFETY_CLAMP_RATIO or ys < FIELD_LIMIT_XY * SAFETY_CLAMP_RATIO
    if clamp and verbose:
        print(f"  SAFETY-CLAMP: XY=({xs:.0f},{ys:.0f}) vs field limit ({FIELD_LIMIT_XY},{FIELD_LIMIT_XY})")
    return clamp


def analyze_project(path, fps=60, verbose=True):
    """对单个项目目录做完整退化检测。"""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        data, t0, music, field, dev = pf.read_fii(path, fps=fps, ignore_acc=False)
    
    n = len(data)
    uf = sum(1 for c in caught if 'completed' in str(c.message))
    
    all_x = [p[1] for d in data for p in d if p[1] > 0]
    all_y = [p[2] for d in data for p in d if p[1] > 0]
    all_z = [p[3] for d in data for p in d if p[1] > 0]
    xs, ys = max(all_x) - min(all_x), max(all_y) - min(all_y) if all_x else (0, 0)

    # 最小距离
    md = 9999
    mf = min(len(d) for d in data)
    for t in range(0, mf, 60):
        pos = [(data[i][t][1], data[i][t][2]) for i in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                dd = np.sqrt((pos[i][0] - pos[j][0]) ** 2 + (pos[i][1] - pos[j][1]) ** 2)
                if 0 < dd < md:
                    md = dd

    if verbose:
        print(f"\n{'='*60}")
        print(f"Project: {path}")
        print(f"  drones={n}  device={dev}  duration={t0/60:.1f}s  uf={uf}")
        print(f"  XY=({xs:.0f},{ys:.0f})  Z=[{min(all_z):.0f},{max(all_z):.0f}]  min_dist={md:.1f}cm")

    lanes = detect_lane(data, verbose)
    center = detect_center_anchor(data, verbose)
    circle = detect_circle_rigid(data, center, verbose)
    jerk = compute_jerk(data, verbose)
    clamp = detect_safety_clamp(data, verbose)

    return {
        "path": path,
        "drones": n,
        "device": dev,
        "duration_s": t0 / 60,
        "unfinished": uf,
        "xy_span": (xs, ys),
        "z_range": (min(all_z), max(all_z)) if all_z else (0, 0),
        "min_distance": md,
        "lane_drones": len(lanes),
        "center_anchor": center,
        "circle_rigid_ratio": circle,
        "jerk": jerk,
        "safety_clamp": clamp,
    }


def main():
    parser = argparse.ArgumentParser(description="AI 编舞产物退化检测")
    parser.add_argument("--path", type=str, default=None,
                        help="项目目录路径（默认扫描预设列表）")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.path:
        paths = [args.path]
    else:
        # 预设 AI 产物列表
        paths = [
            "output/gpt55_phrase_vibe_v3_60s/gpt55_phrase_vibe_v3_60s",
            "output/gpt55_template_motion_v2_60s/gpt55_template_motion_v2_60s",
            "output/gpt55_action_score_v2_60s/gpt55_action_score_v2_60s",
            "output/gpt55_burst_recompose_60s/gpt55_burst_recompose_60s",
            "output/original_crosscut_v9_60s/original_crosscut_v9_60s",
            "output/original_kinetic_ribbon_v8_60s/original_kinetic_ribbon_v8_60s",
            "output/original_flow_field_v5_70s/original_flow_field_v5_70s",
            "output/codex_mirror_bloom_60s/codex_mirror_bloom_60s",
        ]
        # 过滤存在的路径
        paths = [p for p in paths if (REPO_ROOT / p).is_dir()]

    results = []
    for path in paths:
        try:
            r = analyze_project(str(REPO_ROOT / path), fps=args.fps, verbose=not args.quiet)
            results.append(r)
        except Exception as e:
            print(f"ERROR {path}: {e}")

    # 汇总
    if results and not args.quiet:
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'Project':<40s} {'d':>2s} {'dur':>5s} {'uf':>5s} {'minD':>5s} {'flaws'}")
        for r in results:
            flaws = []
            if r["lane_drones"]:
                flaws.append(f"lane×{r['lane_drones']}")
            if r["center_anchor"] is not None:
                flaws.append(f"center(d{r['center_anchor']+1})")
            if r["circle_rigid_ratio"] is not None:
                flaws.append(f"circle({r['circle_rigid_ratio']:.0%})")
            if r["safety_clamp"]:
                flaws.append("clamp")
            name = r["path"].split("/")[-1][:38]
            print(f"{name:<40s} {r['drones']:>2d} {r['duration_s']:>4.0f}s {r['unfinished']:>5d} {r['min_distance']:>4.0f}cm {' '.join(flaws)}")


if __name__ == "__main__":
    main()
