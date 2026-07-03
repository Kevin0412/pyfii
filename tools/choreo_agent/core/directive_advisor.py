"""指令可行性预检 + 安全冲突解释 — 导演回路的"为什么不行"层。

导演改一个坐标可能物理上做不到（越界/与他机太近/时间飞不到）。本模块：
1. precheck_directive：生成前对指令里的显式坐标/点名机号做确定性静态检查，
   预警同时给模型（附进反馈）和导演（REPL 打印）；
2. explain_conflict：安全门失败后，把 collision_intervals / 动作未完成等
   验证事实翻译成导演语言，并给出取舍选项——由导演决定改指令还是挪别的机。
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence

from .director_language import mentioned_drones

XY_MIN, XY_MAX = 0.0, 560.0
Z_MIN, Z_MAX = 80.0, 250.0
HARD_SPACING_CM = 51.0
SAFE_SPACING_CM = 60.0

_COORD = re.compile(
    r"\(\s*(\d{1,3}(?:\.\d+)?)\s*,\s*(\d{1,3}(?:\.\d+)?)\s*,\s*(\d{1,3}(?:\.\d+)?)\s*\)"
)


def extract_coordinates(text: str) -> list[tuple[float, float, float]]:
    return [tuple(float(g) for g in m.groups()) for m in _COORD.finditer(text or "")]


def precheck_directive(
    directive: str,
    prev_positions: Sequence[Sequence[float]] | None,
    drone_count: int,
    window_s: float | None = None,
) -> list[str]:
    """指令的确定性可行性预警（以上一段出口为参考，不是最终判定）。"""
    warnings: list[str] = []
    coords = extract_coordinates(directive)
    if not coords:
        return warnings
    named = set(mentioned_drones(directive))

    for x, y, z in coords:
        if not (XY_MIN <= x <= XY_MAX and XY_MIN <= y <= XY_MAX):
            warnings.append(
                f"目标点 ({x:.0f},{y:.0f},{z:.0f}) XY 越界（场地 0-560）——必须先修改指令坐标。"
            )
            continue
        if not (Z_MIN <= z <= Z_MAX):
            warnings.append(
                f"目标点 ({x:.0f},{y:.0f},{z:.0f}) Z 越界（80-250）——必须先修改指令坐标。"
            )
            continue
        if not prev_positions:
            continue
        for k, p in enumerate(prev_positions):
            if k in named:
                continue  # 被点名的机自己会挪走，不算冲突
            dxy = math.hypot(x - float(p[0]), y - float(p[1]))
            if dxy < HARD_SPACING_CM:
                warnings.append(
                    f"目标点 ({x:.0f},{y:.0f},{z:.0f}) 与 d{k} 的段入口位置 XY 仅 {dxy:.0f}cm"
                    f"（硬下限 {HARD_SPACING_CM:.0f}）——若 d{k} 段尾仍停在附近必撞："
                    f"需同时把 d{k} 的段尾点让开 ≥{SAFE_SPACING_CM:.0f}cm，或平移目标点。"
                )
            elif dxy < SAFE_SPACING_CM:
                warnings.append(
                    f"提示：目标点与 d{k} 段入口位置仅 {dxy:.0f}cm，边缘余量小，"
                    "建议让编舞把它们的段尾错开。"
                )
        if named and window_s:
            for k in named:
                if 0 <= k < len(prev_positions):
                    dist = math.dist(
                        (x, y, z), tuple(float(v) for v in prev_positions[k])
                    )
                    # 粗预算：平均 150cm/s，扣 2s 给其它动作/灯光
                    reachable = 150.0 * max(1.0, window_s - 2.0)
                    if dist > reachable:
                        warnings.append(
                            f"d{k} 从入口到目标点直线 {dist:.0f}cm，按 ~150cm/s 与本段窗口"
                            f" {window_s:.0f}s 预算勉强/不可达——考虑放宽目标或说明允许直飞不绕。"
                        )
    return warnings


def explain_conflict(validation, directive: str = "") -> str:
    """把安全门失败翻译成导演语言 + 取舍选项。validation.passed 时返回空串。"""
    if validation is None:
        return "生成失败：没有产生可验证的代码（多为格式/协议问题，与指令内容无关）。"
    if validation.passed:
        return ""
    named = set(mentioned_drones(directive))
    lines: list[str] = []

    if not (validation.compile_ok and validation.run_ok and validation.read_fii_ok):
        tail = (validation.error_message or "")[-160:]
        lines.append(f"代码本身执行失败（编译/运行/读回），与指令内容无关：{tail}")
        return "指令执行遇阻——" + " ".join(lines)

    intervals = validation.collision_intervals or []
    if intervals or validation.distance_warnings != 0:
        for item in intervals[:3]:
            pair = item.get("pair") or (None, None)
            i, j = pair
            who = f"d{i} 与 d{j}" if i is not None else "两机"
            involved = named & {i, j}
            blame = f"（正是指令点名的 {sorted(involved)} 号机）" if involved else ""
            lines.append(
                f"{who} 在 {item.get('min_time_s')}s 距离仅 {item.get('min_distance_cm')}cm"
                f"（{item.get('start_s')}-{item.get('end_s')}s 区间）{blame}"
            )
        lines.append(
            "取舍选项：① 保持指令，同时明确要求冲突机让位（段尾点挪开 ≥60cm 或错峰到点）；"
            "② 目标点平移出冲突带；③ 放宽到点时间让路径绕行。"
        )
        return "指令与安全约束冲突——" + "；".join(lines)

    if validation.action_warnings and validation.action_warnings > 0:
        detail = "；".join((validation.action_details or [])[:2])
        lines.append(
            f"动作未完成 ×{validation.action_warnings}：目标在给定时间内飞不到"
            f"（{detail[:160]}）。取舍：减小位移幅度、加长该 keyframe、或允许直飞。"
        )
        return "指令与时间预算冲突——" + " ".join(lines)

    if validation.continuity_required:
        integrity = []
        if validation.hover_segments or not validation.hover_check_ok:
            integrity.append("执行后段内出现长悬停")
        if not validation.window_fill_ok:
            integrity.append("段窗口没被动作铺满")
        if not validation.effective_motion_ok or validation.low_activity_segments:
            integrity.append("有效运动不足")
        if not validation.motion_envelope_ok:
            integrity.append("运动没有落在本段窗口内")
        if integrity:
            return (
                "指令满足后演出完整性受损——"
                + "、".join(integrity)
                + "。这类问题导演可拍板（o <理由> 强制锁定），或反馈要求补动作/灯光填满。"
            )

    tail = (validation.error_message or "")[-160:]
    return "验证未通过（非碰撞/时间类）：" + (tail or "见完整验证输出。")
