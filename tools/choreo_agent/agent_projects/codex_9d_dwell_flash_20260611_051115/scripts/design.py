#!/usr/bin/env python3
"""PyFii choreography — function-based segments. LLM edits function bodies only."""
import json, math, os, sys
from pathlib import Path

HERE = Path(__file__).resolve()

def find_repo_root(path):
    for parent in path.parents:
        if (parent / "src" / "pyfii").exists():
            return parent
    raise RuntimeError("Cannot find repo root")

REPO_ROOT = find_repo_root(HERE)
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(HERE.parent))

import numpy as np
import pyfii as pf
import warnings
from function import *

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def load_drone_count(default=7):
    try:
        state = json.loads((PROJECT_ROOT / "state.json").read_text(encoding="utf-8"))
        return max(1, int(state.get("drone_count", default)))
    except Exception:
        return default

N = load_drone_count()
MUSIC = str(REPO_ROOT / "cannon_in_D.mp3")
OUT = PROJECT_ROOT / "output"

drones = [pf.Drone(0, 0, pf.drone_config_6m, f"192.168.51.{51+i}") for i in range(N)]

# ============================================================
# SEGMENT FUNCTIONS (LLM edits body between AGENT markers)
# ============================================================

def s01(drones: list):
    """S01: 4-13s 起飞+初始展开"""
    # === PYFII_AGENT_SEGMENT_START id=S01 locked=true ===
    # role: 主题引入，分散点火到对称宽V，播种斜线推进和层次
    # motifs: 宽V展开，斜线推进，高度三层，浅蓝白灯光
    # beat: 紧凑三段式：从散点到宽V（快），宽V到对角斜线（中速），对角斜线到水平三层（收束）
    # formation: 不对称起飞→对称宽V→对角斜线→水平三层分层
    # lighting: 开场浅蓝白，过渡蓝白，结束白色巩固

    start_positions = [
        (50, 460, 110),
        (120, 380, 130),
        (190, 300, 150),
        (260, 220, 180),
        (330, 140, 200),
        (400, 260, 170),
        (470, 340, 140),
        (360, 450, 120),
        (280, 480, 100)
    ]

    for i, d in enumerate(drones):
        x, y, z = start_positions[i]
        d.X = d.x = x
        d.Y = d.y = y
        d.takeoff(1, z)
    wait_until(drones, 4.0)

    prev = [(d.x, d.y, d.z) for d in drones]

    # Keyframe 1: 分散 → 对称宽V
    geo1 = custom_points([
        (280, 100, 220),   # 尖端
        (100, 250, 180), (70, 330, 150), (40, 410, 120), (10, 490, 100),
        (460, 250, 180), (490, 330, 150), (520, 410, 120), (550, 490, 100)
    ], n=len(drones), min_xy_cm=70)
    targets1 = best_assign(prev, geo1)
    flying_ms1 = 2900
    ticks1 = 4
    for i, drone in enumerate(drones):
        move2(drone, targets1[i], flying_ms1)
        apply_light(drone, "#aaddff", ticks1)
        drone.delay(max(0, flying_ms1 - ticks1 * 100 + 100))
    prev = [(t[0], t[1], t[2]) for t in targets1]

    # Keyframe 2: 宽V → 对角斜线
    geo2 = custom_points([
        (50, 470, 150), (125, 395, 200), (200, 320, 120), (275, 245, 180), (350, 170, 160),
        (120, 500, 190), (195, 425, 130), (270, 350, 170), (345, 275, 110)
    ], n=len(drones), min_xy_cm=70)
    targets2 = best_assign(prev, geo2)
    flying_ms2 = 2900
    ticks2 = 4
    for i, drone in enumerate(drones):
        move2(drone, targets2[i], flying_ms2)
        apply_light(drone, "#88bbff", ticks2)
        drone.delay(max(0, flying_ms2 - ticks2 * 100 + 100))
    prev = [(t[0], t[1], t[2]) for t in targets2]

    # Keyframe 3: 对角斜线 → 水平三层
    geo3 = custom_points([
        (100, 100, 210), (280, 100, 210), (460, 100, 210),
        (140, 280, 170), (280, 280, 170), (420, 280, 170),
        (60, 450, 120), (280, 450, 120), (500, 450, 120)
    ], n=len(drones), min_xy_cm=80)
    targets3 = best_assign(prev, geo3)
    flying_ms3 = 2900
    ticks3 = 4
    for i, drone in enumerate(drones):
        move2(drone, targets3[i], flying_ms3)
        apply_light(drone, "#cceeff", ticks3)
        drone.delay(max(0, flying_ms3 - ticks3 * 100 + 100))
    prev = [(t[0], t[1], t[2]) for t in targets3]
    # === PYFII_AGENT_SEGMENT_END S01 ===

def s02(drones: list):
    """S02: 13-23s 展开推进"""
    # === PYFII_AGENT_SEGMENT_START id=S02 locked=true ===
    # role: 第一次展开：从起点的分散布局向更开阔的边界流动，形成宽三列+V形+扇框
    # motifs: 扇形展开; 边界框线; 高低三层
    # beat: 平滑启动，auto_init 对齐，第一帧交错启动，第二帧到达波次，第三帧交错启动
    # formation: 宽三列（左中右各三机不同高度）→ 对称V形（斜线五层高度）→ 边界扇框
    # lighting: 灯光时钟型，全程亮光；第一帧蓝白，第二帧冰蓝，第三帧个体色调（彩虹色）
    auto_init(drones)
    prev = [(d.x, d.y, d.z) for d in drones]

    # ---------- Keyframe 1: 展开为宽三列（左80、中280、右500）----------
    geo1 = custom_points(
        [
            (80, 80, 230),
            (80, 280, 180),
            (80, 480, 100),
            (280, 80, 230),
            (280, 280, 180),
            (280, 480, 100),
            (500, 80, 230),
            (500, 280, 180),
            (500, 480, 100),
        ],
        n=len(drones),
        min_xy_cm=90,
    )
    targets1 = best_assign(prev, geo1)
    flying_ms = 3000
    ticks = flying_ms // 100  # 30 ticks = 3s 灯光覆盖全程
    for i, drone in enumerate(drones):
        drone.delay(i * 80)  # 交错启动
        move2(drone, targets1[i], flying_ms)
        apply_light(drone, "#88ccff", ticks)
    prev = [(t[0], t[1], t[2]) for t in targets1]

    # ---------- Keyframe 2: 转为对称V形（左右斜线+中心）----------
    geo2 = custom_points(
        [
            (100, 100, 100),
            (150, 180, 140),
            (200, 260, 180),
            (250, 340, 220),   # 修正：增大y间距至80，确保距离>90
            (280, 200, 200),
            (350, 340, 220),   # 对称修正
            (400, 260, 180),
            (450, 180, 140),
            (500, 100, 100),
        ],
        n=len(drones),
        min_xy_cm=90,
    )
    targets2 = best_assign(prev, geo2)
    flying_ms = 3000
    for i, drone in enumerate(drones):
        stagger_move = (i % 3) * 250
        move2(drone, targets2[i], flying_ms + stagger_move)
        apply_light(drone, "#44ddff", (flying_ms + stagger_move) // 100)
    prev = [(t[0], t[1], t[2]) for t in targets2]

    # ---------- Keyframe 3: 向边界散开，形成扇框（四角+四边中点+中心偏移）----------
    geo3 = custom_points(
        [
            (60, 60, 220),
            (60, 280, 150),
            (60, 520, 100),
            (280, 60, 220),
            (280, 280, 180),
            (280, 520, 100),
            (500, 60, 220),
            (500, 280, 150),
            (500, 520, 100),
        ],
        n=len(drones),
        min_xy_cm=90,
    )
    targets3 = best_assign(prev, geo3)
    flying_ms = 3500
    palette = [
        "#ff6b6b",
        "#feca57",
        "#48dbfb",
        "#1dd1a1",
        "#5f27cd",
        "#54a0ff",
        "#ff9f43",
        "#00d2d3",
        "#ee5a24",
    ]
    for i, drone in enumerate(drones):
        drone.delay(i * 90)  # 交错启动
        move2(drone, targets3[i], flying_ms)
        apply_light(drone, palette[i], flying_ms // 100)
    prev = [(t[0], t[1], t[2]) for t in targets3]
    # === PYFII_AGENT_SEGMENT_END S02 ===

def s03(drones: list):
    """S03: 24-32s"""
    # === PYFII_AGENT_SEGMENT_START id=S03 locked=true ===
    # role: 卡农错峰变奏，展示分组交叉与空间扩散
    # motifs: 分组卡农; 椭圆扩散; 阶梯排列
    # beat: 所有无人机同时按顺序延时起飞（drone.delay(i*120)），形成启动波次；后续灯光时钟型占满飞行窗口，到达时间自然错位
    # formation: 第一拍从S02出口散点飞向均匀椭圆（围绕(280,280)），第二拍展开为清晰阶梯对称阵（前排低、中排中、后排高）
    # lighting: 第一拍使用个体色彩身份（palette），第二拍统一暖金色灯光时钟型

    auto_init(drones)
    prev = [(d.x, d.y, d.z) for d in drones]

    # --- 第一拍: 椭圆阵 + 起飞波次错峰 ---
    geo1 = custom_points([
        (280 + int(180 * cos(2 * pi * i / 9)), 280 + int(150 * sin(2 * pi * i / 9)), 120 + int(30 * sin(2 * pi * i / 9)))
        for i in range(9)
    ], n=9, min_xy_cm=51)
    targets1 = far_assign(prev, geo1, min_path_cm=active_min_path_cm(3200))
    flying_ms1 = 3200
    palette = ["#ff4444","#ffaa00","#ffee44","#44ff88","#44ddff","#4466ff","#aa44ff","#ff44aa","#ffffff"]
    for i, drone in enumerate(drones):
        drone.delay(i * 120)                     # 起飞波次，卡农启动
        move2(drone, targets1[i], flying_ms1)
        apply_light(drone, palette[i], flying_ms1 // 100)   # 灯光时钟型，无尾部闲置
    prev = [(t[0], t[1], t[2]) for t in targets1]

    # --- 第二拍: 阶梯对称阵（前排低、中排中、后排高）---
    geo2 = custom_points([
        (100, 150, 100), (280, 150, 100), (460, 150, 100),
        (150, 300, 160), (280, 300, 160), (410, 300, 160),
        (180, 450, 220), (280, 450, 220), (380, 450, 220),
    ], n=9, min_xy_cm=51)
    targets2 = best_assign(prev, geo2)
    flying_ms2 = 3200
    for i, drone in enumerate(drones):
        move2(drone, targets2[i], flying_ms2)
        apply_light(drone, "#ffaa44", flying_ms2 // 100)    # 统一暖金
    prev = [(t[0], t[1], t[2]) for t in targets2]
    # === PYFII_AGENT_SEGMENT_END S03 ===

def s04(drones: list):
    """S04: 32-48s"""
    # === PYFII_AGENT_SEGMENT_START id=S04 locked=true ===
    auto_init(drones)
    prev = [(d.x, d.y, d.z) for d in drones]

    # role: 抒情中段：将星芒/框线/波浪母题拉长，强化高低层与呼吸，为高潮蓄力
    # motifs: 星芒/框线; 波浪高度层; 斜线回卷
    # beat: 星芒展开→框线稳定→宽V波浪(卡农错峰)→星芒回卷→紧凑框线收束，每段3200ms
    # formation: 对称星芒→矩形框+中心→两列V形→旋转星芒→缩合框线
    # lighting: 冷蓝→暖橙→翠绿→金→暖白，每段灯光短提示，V形段加入分组交错

    # --- Keyframe 1: 星芒展开 ---
    flying_ms = 3200
    ticks = 4
    color_k1 = "#44aaff"

    geo_k1 = custom_points([
        (280, 280, 160),  # center
        (460, 280, 220),
        (407, 407, 130),
        (280, 460, 220),
        (153, 407, 130),
        (100, 280, 220),
        (153, 153, 130),
        (280, 100, 220),
        (407, 153, 130)
    ], n=len(drones), min_xy_cm=90)

    targets_k1 = best_assign(prev, geo_k1)
    for i, drone in enumerate(drones):
        move2(drone, targets_k1[i], flying_ms)
        apply_light(drone, color_k1, ticks)
        drone.delay(flying_ms - ticks * 100 + 100)
    prev = [(t[0], t[1], t[2]) for t in targets_k1]

    # --- Keyframe 2: 框线+中心 ---
    flying_ms = 3200
    ticks = 4
    color_k2 = "#ff6644"

    geo_k2 = custom_points([
        (100, 100, 80),
        (100, 460, 80),
        (460, 460, 80),
        (460, 100, 80),
        (100, 280, 160),
        (280, 460, 160),
        (460, 280, 160),
        (280, 100, 160),
        (280, 280, 220)
    ], n=len(drones), min_xy_cm=90)

    targets_k2 = best_assign(prev, geo_k2)
    for i, drone in enumerate(drones):
        move2(drone, targets_k2[i], flying_ms)
        apply_light(drone, color_k2, ticks)
        drone.delay(flying_ms - ticks * 100 + 100)
    prev = [(t[0], t[1], t[2]) for t in targets_k2]

    # --- Keyframe 3: 宽V波浪（卡农错峰）---
    flying_ms = 3200
    ticks = 4
    color_k3 = "#66ff44"
    stagger_ms = 100

    geo_k3 = custom_points([
        (120, 100, 80),
        (120, 200, 160),
        (120, 300, 240),
        (120, 400, 160),
        (440, 100, 250),
        (440, 200, 170),
        (440, 300, 90),
        (440, 400, 170),
        (280, 250, 200)
    ], n=len(drones), min_xy_cm=90)

    targets_k3 = far_assign(prev, geo_k3, min_path_cm=active_min_path_cm(flying_ms))
    for i, drone in enumerate(drones):
        drone.delay((i % 3) * stagger_ms)
        move2(drone, targets_k3[i], flying_ms)
        apply_light(drone, color_k3, ticks)
        drone.delay(flying_ms - ticks * 100 + 100)
    prev = [(t[0], t[1], t[2]) for t in targets_k3]

    # --- Keyframe 4: 星芒回卷（旋转90度）---
    flying_ms = 3200
    ticks = 4
    color_k4 = "#ffaa00"

    geo_k4 = custom_points([
        (280, 280, 180),  # center
        (370, 190, 80),
        (190, 190, 220),
        (370, 370, 80),
        (190, 370, 220),
        (280, 120, 160),
        (120, 280, 120),
        (440, 280, 160),
        (280, 440, 120)
    ], n=len(drones), min_xy_cm=90)

    targets_k4 = best_assign(prev, geo_k4)
    for i, drone in enumerate(drones):
        move2(drone, targets_k4[i], flying_ms)
        apply_light(drone, color_k4, ticks)
        drone.delay(flying_ms - ticks * 100 + 100)
    prev = [(t[0], t[1], t[2]) for t in targets_k4]

    # --- Keyframe 5: 紧凑框线收束 ---
    flying_ms = 3200
    ticks = 4
    color_k5 = "#ffffff"

    geo_k5 = custom_points([
        (180, 180, 100),
        (180, 380, 200),
        (380, 380, 100),
        (380, 180, 200),
        (180, 280, 150),
        (280, 380, 250),
        (380, 280, 150),
        (280, 180, 250),
        (280, 280, 220)
    ], n=len(drones), min_xy_cm=90)

    targets_k5 = best_assign(prev, geo_k5)
    for i, drone in enumerate(drones):
        move2(drone, targets_k5[i], flying_ms)
        apply_light(drone, color_k5, ticks)
        drone.delay(flying_ms - ticks * 100 + 100)
    prev = [(t[0], t[1], t[2]) for t in targets_k5]
    # === PYFII_AGENT_SEGMENT_END S04 ===

def s05(drones: list):
    """S05: 47-58s"""
    # === PYFII_AGENT_SEGMENT_START id=S05 locked=true ===
    # role: 明亮高潮：全场尺度爆发、分组交换与收束，形成最强视觉记忆点
    # motifs: 中心爆点（边界扩张）、波次到达、暖金-白爆-暖白弧线
    # beat: 三阶段快步，每阶段带到达波次（stagger=30ms），节奏递增后收缓
    # formation: 边界四点+边中点+中心（爆发）→ 左中右三列（分组交换）→ 左V+右V+高点（收束）
    # lighting: 暖金（#FFD700）→ 白爆（#FFFFFF）→ 暖白（#FFE4B5），每阶段固定34tick灯光覆盖

    auto_init(drones)
    prev = [(d.x, d.y, d.z) for d in drones]

    base_ms = 3400
    stagger_ms = 30
    tick_count = base_ms // 100  # 34

    # ── Keyframe 1：边界爆发 ──────────────────────────────────────
    geo1 = custom_points([
        (20, 20, 90),    # 角1低
        (20, 540, 130),  # 角2中低
        (540, 20, 170),  # 角3中
        (540, 540, 210), # 角4高
        (20, 280, 100),  # 左边中点低
        (540, 280, 150), # 右边边中中
        (280, 20, 120),  # 上边中低
        (280, 540, 180), # 下边中高
        (280, 280, 250), # 中心高
    ], n=len(drones), min_xy_cm=90)
    targets1 = far_assign(prev, geo1, min_path_cm=active_min_path_cm(base_ms))

    for i, d in enumerate(drones):
        move2(d, targets1[i], base_ms + i * stagger_ms)
        apply_light(d, "#FFD700", tick_count)
        d.delay(i * stagger_ms)  # 补齐剩余时间，同步到达波次

    prev = [(t[0], t[1], t[2]) for t in targets1]

    # ── Keyframe 2：分组矩形交换 ──────────────────────────────────
    geo2 = custom_points([
        (100, 100, 100), (100, 280, 180), (100, 460, 100),   # 左列
        (280, 100, 220), (280, 280, 250), (280, 460, 140),   # 中列
        (460, 100, 120), (460, 280, 200), (460, 460, 160),   # 右列
    ], n=len(drones), min_xy_cm=90)
    targets2 = far_assign(prev, geo2, min_path_cm=active_min_path_cm(base_ms))

    for i, d in enumerate(drones):
        move2(d, targets2[i], base_ms + i * stagger_ms)
        apply_light(d, "#FFFFFF", tick_count)
        d.delay(i * stagger_ms)

    prev = [(t[0], t[1], t[2]) for t in targets2]

    # ── Keyframe 3：V形收束 ──────────────────────────────────────
    geo3 = custom_points([
        (100, 100, 80), (100, 200, 140), (100, 300, 200), (100, 400, 80),   # 左V
        (460, 100, 80), (460, 200, 140), (460, 300, 200), (460, 400, 80),   # 右V
        (280, 280, 250),                                                     # 高点
    ], n=len(drones), min_xy_cm=90)
    targets3 = far_assign(prev, geo3, min_path_cm=active_min_path_cm(base_ms))

    for i, d in enumerate(drones):
        move2(d, targets3[i], base_ms + i * stagger_ms)
        apply_light(d, "#FFE4B5", tick_count)
        d.delay(i * stagger_ms)

    prev = [(t[0], t[1], t[2]) for t in targets3]
    # === PYFII_AGENT_SEGMENT_END S05 ===

def s06(drones: list):
    """S06: 58-63s"""
    # === PYFII_AGENT_SEGMENT_START id=S06 locked=true ===
    # role: 尾声署名
    # motifs: 署名姿态; 温暖白光; 斜线/宽V母题回忆
    # beat: 从倒V宽V回忆到正V对称署名，清晰收束
    # formation: 两段式收尾：倒V（顶点在上）→ 正V（顶点在下），Z三层混合
    # lighting: 统一暖金色 #ffd700，全程覆盖

    auto_init(drones)
    prev = [(d.x, d.y, d.z) for d in drones]

    # Keyframe 1: 倒V宽V回忆（中继姿态）
    # 顶点 (280,480,230)，左臂点 t=0.2,0.4,0.6,0.8 到 (20,60)，
    # 右臂点 t=0.2,0.4,0.6,0.8 到 (540,60)
    geo1 = custom_points([
        (280, 480, 230),          # 顶点
        (228, 396, 120),          # 左1
        (176, 312, 180),          # 左2
        (124, 228, 230),          # 左3
        (72,  144, 120),          # 左4
        (332, 396, 180),          # 右1
        (384, 312, 230),          # 右2
        (436, 228, 120),          # 右3
        (488, 144, 180)           # 右4
    ], n=len(drones), min_xy_cm=90)
    targets1 = best_assign(prev, geo1)
    flying_ms1 = 2400
    ticks1 = flying_ms1 // 100   # 24 ticks，覆盖全飞行窗口
    for i, drone in enumerate(drones):
        move2(drone, targets1[i], flying_ms1)
        apply_light(drone, "#ffd700", ticks1)
        # 灯光已占满2400ms，无需额外delay
    prev = [(t[0], t[1], t[2]) for t in targets1]

    # Keyframe 2: 正V对称署名（最终姿态）
    # 顶点 (280,80,230)，左臂点 t=0.2,0.4,0.6,0.8 到 (20,480)，
    # 右臂点 t=0.2,0.4,0.6,0.8 到 (540,480)
    geo2 = custom_points([
        (280, 80,  230),          # 顶点
        (228, 160, 120),          # 左1
        (176, 240, 180),          # 左2
        (124, 320, 230),          # 左3
        (72,  400, 120),          # 左4
        (332, 160, 180),          # 右1
        (384, 240, 230),          # 右2
        (436, 320, 120),          # 右3
        (488, 400, 180)           # 右4
    ], n=len(drones), min_xy_cm=90)
    targets2 = best_assign(prev, geo2)
    flying_ms2 = 2600
    ticks2 = flying_ms2 // 100   # 26 ticks，覆盖全飞行窗口
    for i, drone in enumerate(drones):
        move2(drone, targets2[i], flying_ms2)
        apply_light(drone, "#ffd700", ticks2)
        # 灯光已占满2600ms，无需额外delay
    prev = [(t[0], t[1], t[2]) for t in targets2]
    # === PYFII_AGENT_SEGMENT_END S06 ===

def land(drones: list):
    """LAND: 63-68s 降落"""
    # === PYFII_AGENT_SEGMENT_START id=LAND locked=true ===
    # role: 安全降落：不再编舞，只做短灯光提示和降落。
    # motifs: 温暖白光、短促灯光提示、降落收尾。
    # beat: 自动同步时间后，每架机暖白闪烁3次后逐个降落。
    # formation: 维持入口9点散点形态，不做任何平移或编队改变。
    # lighting: 暖白色 #ffdd88，每架闪烁3个tick后降落。

    auto_init(drones)                               # 同步上一段未完成动作

    for i, drone in enumerate(drones):
        drone.delay(i * 30)                         # 微错峰灯光，避免全同时闪烁
        apply_light(drone, "#ffdd88", 3)            # 暖白闪烁3 tick（300ms）
        drone.land()                                # 降落（自动处理落地的时序）
    # === PYFII_AGENT_SEGMENT_END LAND ===

# ============================================================
# MAIN EXECUTION
# ============================================================
s01(drones)
s02(drones)
s03(drones)
s04(drones)
s05(drones)
s06(drones)
land(drones)

# ============================================================
# FIXED FOOTER
# ============================================================
# Only save Fii if drones have actual actions
has_actions = any(len(getattr(d, 'action_list', [])) > 0 or bool(getattr(d, 'light_actions', {})) for d in drones)
if has_actions:
    for drone in drones:
        drone.end()
    os.makedirs(str(OUT), exist_ok=True)
    try:
        fii = pf.Fii(str(OUT), drones, music=MUSIC)
        fii.save(field=6)
        data, t0, *_ = pf.read_fii(str(OUT), fps=60, ignore_acc=False)
    except Exception:
        print("Fii save/read failed")
        sys.exit(1)
else:
    print("empty template — no drone actions")
    sys.exit(0)


mf = min(len(d) for d in data)
all_x = [p[1] for d in data for p in d if p[1] > 0]
all_y = [p[2] for d in data for p in d if p[1] > 0]
md = 1e9
for t in range(0, mf, 60):
    for i in range(N):
        for j in range(i+1, N):
            dd = ((data[i][t][1]-data[j][t][1])**2 + (data[i][t][2]-data[j][t][2])**2)**0.5
            if 0 < dd < md:
                md = dd
if all_x and all_y:
    print(f"{N}d F400 {t0/60:.1f}s XY({max(all_x)-min(all_x):.0f},{max(all_y)-min(all_y):.0f}) minD={md:.1f}cm")

with warnings.catch_warnings(record=True) as c:
    warnings.simplefilter("always")
    pf.show(data, t0, [MUSIC], field=6, device="F400", max_fps=60, show=False)
dw = [x for x in c if "distance between" in str(x.message)]
aw = [x for x in c if "completed" in str(x.message)]
print(f"dist:{len(dw)} act:{len(aw)}")
print("done")
