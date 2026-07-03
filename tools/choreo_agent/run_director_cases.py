#!/usr/bin/env python3
"""真实 API 导演验收（C7-3b / C10）：细节修改指令 + 轨迹级确认。

每个 case 的流程：
  fresh 项目 → 生成并锁定 S01 → S02 先出 baseline（记录退化指标）→
  下达细节指令重做 S02 → 读回 .fii 做轨迹断言；断言失败把**实测偏差**
  作为针对性反馈再修（最多 --directive-rounds 轮，模拟导演"还没到位，再改"）→
  无新增退化 → 逐 case JSON。

指令语言即产品语言：支持相对方位（"往左一点/中间"）与复杂灯效
（"从左到右依次彩虹并明暗渐变"），由 core/director_language.py 在
session 入口自动 grounding。用便宜模型（默认 deepseek flash）。

Usage:
  conda run -n pyfii python tools/choreo_agent/run_director_cases.py \
      --provider deepseek --cases 1,2,3,4,5,6

提速两招：
  # 1) 舞台复用：S01 生成+锁定只做一次（各 case 从快照拷贝，省 ~40% 调用）
  ... --make-stage s01_stage_flash
  ... --cases 1,2,3 --stage s01_stage_flash
  # 2) case 级并行：各 case 项目独立，分进程同时跑即可
  ... --cases 4 --stage s01_stage_flash --out reports/c4.json &
  ... --cases 6 --stage s01_stage_flash --out reports/c6.json &
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import traceback
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_ROOT))

from core import Session  # noqa: E402
from core.director_language import format_directive_checklist  # noqa: E402
from core.trajectory_assert import (  # noqa: E402
    blue_dominant,
    check_brightness_modulation,
    check_collinear,
    check_max_altitude,
    check_max_speed,
    check_color_window,
    check_dark_multicolor,
    check_drone_at,
    check_drone_in_box,
    check_group_hold,
    check_hue_diversity,
    check_no_new_degradation,
    check_relative_shift,
    check_spatial_temporal_order,
    check_sync_pulses,
    drone_position_at,
    hue_deg,
    load_trajectory,
)

REPORT_DIR = TOOL_ROOT / "director_case_reports"

POSITION_TARGET = (140.0, 140.0, 180.0)
POSITION_DIRECTIVE = (
    "细节修改：让 drones[3]（从 0 计数的第 4 架）在本段结束时准确停在坐标 "
    f"({POSITION_TARGET[0]:.0f}, {POSITION_TARGET[1]:.0f}, {POSITION_TARGET[2]:.0f})，"
    "误差 ±25cm 以内，并在段尾保持在那里。"
    "写法注意：best_assign/far_assign/safe_move 会重排机-点对应，"
    "点表里放这个坐标不保证是 3 号机到达——必须身份保持：本段最后一个 keyframe 之后"
    "单独给 `move2(drones[3], (140, 140, 180), ...)` 收尾（或该 keyframe 的分配声明 "
    'assign="keep" 并把 3 号机的目标固定为该点）。'
    "其余无人机照常编舞，段尾点表与 (140,140,180) 保持 ≥60cm XY 间距。"
)
LIGHTING_DIRECTIVE = (
    "细节修改：本段时间过半之后，把全体无人机——全部机、每一架都要，"
    "包括编号最大的最后两架——的灯光改成蓝色系（蓝通道明显主导，"
    "可以做渐变/呼吸），一直保持到段尾不要中断；前半段灯光照常。"
    "写法注意：对 drones 全列表循环设灯，不要只对某个分组设色。"
)
FUZZY_DIRECTIVE = (
    "细节修改：把 5 号机（drones[5]）段尾的位置移到场地中间再往左一点，"
    "高度取中层，段尾停在那里；其余照常编舞并保持安全间距。"
)
RELATIVE_STAGE_A = (
    "细节修改：让 2 号机（drones[2]）段尾停在场地中间附近（身份保持写法），其余照常。"
)
RELATIVE_STAGE_B = (
    "继续修改：2 号机段尾的位置再往左一点，其余尽量保持上一版不变。"
)
RAINBOW_DIRECTIVE = (
    "细节修改：本段后半，全体无人机按当前位置从左到右的顺序**依次**点亮各自的彩虹色"
    "（左边的机先亮，右边的机后亮，明显错开），色相从红到紫依次分布形成彩虹；"
    "点亮后一直到段尾做明暗渐变（呼吸式亮度起伏）。每一架都要参与。"
)


# ---- 逐指令评估器：返回 (name, ok, detail, 针对性修正反馈) ----


def _eval_position(data, fps, window, _ctx):
    ok, detail = check_drone_at(data, fps, 3, window[1] - 0.3, POSITION_TARGET, tol_cm=25.0)
    fb = None
    if not ok:
        fb = (
            f"指令仍未满足：drones[3] 段尾实测 {tuple(detail['actual'])}，"
            f"要求 ({POSITION_TARGET[0]:.0f},{POSITION_TARGET[1]:.0f},{POSITION_TARGET[2]:.0f})±25cm。"
            "保持其余内容不变，在本段末尾单独加 "
            "`move2(drones[3], (140, 140, 180), ...)` 收尾，并让其它机的段尾点位"
            "与该点保持 ≥60cm XY 间距。"
        )
    return "position", ok, detail, fb


def _eval_lighting(data, fps, window, _ctx):
    mid = (window[0] + window[1]) / 2.0
    ok, detail = check_color_window(
        data, fps, mid + 0.5, window[1] - 0.3, blue_dominant, min_fraction=0.6
    )
    fb = None
    if not ok:
        low = [k for k, v in detail["per_drone_fraction"].items() if v < 0.6]
        fb = (
            f"指令仍未满足：机 {low} 在后半窗口的蓝色占比不足 0.6"
            f"（详情 {detail['per_drone_fraction']}）。"
            "对 drones 全列表（每一架）在时间过半后设置蓝通道主导的颜色并保持到段尾。"
        )
    return "lighting", ok, detail, fb


# "中间再往左一点"：中心 x≈280 左移 30-150，y 居中带，z 中层
FUZZY_BOX = ((130.0, 255.0), (180.0, 380.0), (120.0, 215.0))


def _eval_fuzzy_box(data, fps, window, _ctx):
    ok, detail = check_drone_in_box(data, fps, 5, window[1] - 0.3, FUZZY_BOX)
    fb = None
    if not ok:
        fb = (
            f"指令仍未满足：drones[5] 段尾实测 {tuple(detail['actual'])}。"
            "要求：场地中间(280,280)再往左一点 ≈ x 在 130-255、y 在 180-380、"
            "z 中层 120-215。保持其余不变，把 5 号机段尾用身份保持写法挪进该区域。"
        )
    return "fuzzy_box", ok, detail, fb


def _eval_rainbow(data, fps, window, _ctx):
    mid = (window[0] + window[1]) / 2.0
    t_end = window[1] - 0.4
    # predicate=None → 按"到达各自段尾最终色相"检测 onset（防前半段既有彩灯误判）
    order_ok, order_detail = check_spatial_temporal_order(
        data, fps, mid, t_end, None, axis=0, ascending=True,
        min_span_s=0.6, max_inversions=1,
    )
    hue_ok, hue_detail = check_hue_diversity(data, fps, t_end, min_hue_buckets=5)
    mod_ok, mod_detail = check_brightness_modulation(
        data, fps, mid, t_end, min_amplitude=60, min_fraction=0.7
    )
    ok = order_ok and hue_ok and mod_ok
    detail = {"order": order_detail, "hues": hue_detail, "modulation": mod_detail}
    fb = None
    if not ok:
        parts = []
        if not order_ok:
            parts.append(
                "'从左到右依次点亮'未满足：按 x 从小到大各机的点亮时刻应递增且首尾差 ≥0.6s，"
                f"实测 onset（按左→右序）= {order_detail.get('onsets_in_spatial_order')}"
                f"，逆序对 {order_detail.get('inversions')}，缺席 {order_detail.get('missing', [])}。"
                "按当前 x 排序逐机延迟点灯（light_wave 或逐机 delay 后 apply_light）。"
            )
        if not hue_ok:
            parts.append(
                f"彩虹色相不足：段尾仅覆盖色相桶 {hue_detail['hue_buckets']}（需 ≥5 桶）。"
                "每机独立色相，红→紫依次分布（palette[i] 写具体 hex）。"
            )
        if not mod_ok:
            parts.append(
                f"明暗渐变不足：亮度摆幅 ≥60 的机占比 {mod_detail['qualified_fraction']}（需 ≥0.7）。"
                "点亮后到段尾做呼吸式亮度起伏（breathe_group 或渐变 ticks）。"
            )
        fb = "指令仍未满足：\n- " + "\n- ".join(parts)
    return "rainbow", ok, detail, fb


# ---- 广覆盖样例（C12）：多机/队形/不可行/部分灯光/同步爆闪/暗多彩/定格/
# ---- 对穿身份/后悔撤销/逐条组合 ----

MULTI_POSITION_DIRECTIVE = (
    "细节修改：0 号机和 6 号机段尾并排停在前排——drones[0] 停 (200, 120, 150)，"
    "drones[6] 停 (360, 120, 150)，各 ±25cm，身份保持写法（段末分别单独 move2）；"
    "其余照常并保持安全间距。"
)
FORMATION_LINE_DIRECTIVE = (
    "细节修改：本段结束时全体排成一条清晰的斜线——从左前方到右后方，"
    "均匀铺开（跨度至少大半个场地），高度可以有层次；段尾停在线上。"
)
INFEASIBLE_DIRECTIVE = (
    "细节修改：让 3 号机段尾停到 (600, 100, 180)。"
)
PARTIAL_LIGHT_DIRECTIVE = (
    "细节修改：只把 2 号机（drones[2]）后半段的灯光改成红色并保持到段尾；"
    "其余所有机保持原来的配色，不要跟着变红。"
)
SYNC_FLASH_DIRECTIVE = (
    "细节修改：本段中段全体无人机同步爆闪 3 下——同时亮、同时灭，"
    "三下节奏一致；爆闪前后灯光照常。"
)
DARK_MULTI_DIRECTIVE = (
    "细节修改：后半段做'五彩斑斓的黑'——暗底多彩微光：每一架机不同色相，"
    "但亮度都压得很低（每个通道不超过 120），微微闪动保持到段尾，不要灭灯也不要亮场。"
)
HOLD_DIRECTIVE = (
    "细节修改：本段中段全体到位后**定住 2 秒**（位置保持不动、灯保持亮），"
    "定格结束后再继续后续动作铺满段尾。"
)
SWAP_DIRECTIVE = (
    "细节修改：3 号机和 4 号机在本段内交换彼此的位置——段尾 drones[3] 停在 "
    "drones[4] 的本段入口位置，drones[4] 停在 drones[3] 的入口位置（各 ±45cm，"
    "身份保持写法）。注意对穿路径要错峰或绕行，其余机让出通道。"
)
SLOW_DIRECTIVE = (
    "细节修改：整段动作明显放慢、优雅一点——不要快速冲刺，"
    "任何机任何时刻的移动速度都不要超过 120cm/s（用更长的 flying_ms、"
    "更短的单次位移），动作仍要铺满整段窗口。"
)
NEGATIVE_DIRECTIVE = (
    "细节修改（两条禁令）：本段不要用圆形/环形队形（不要绕圈），"
    "并且所有机全程别飞到 200cm 以上（高度都压在 200 以下），其余照常编舞。"
)
REGRET_STAGE_A = "细节修改：2 号机段尾往左移一大步（至少 80cm），其余照常。"
REGRET_STAGE_B = (
    "刚才说错了，撤销上一条往左的要求：2 号机回到本段入口原来的位置附近停住，"
    "其余尽量保持不变。"
)
SEQ_STAGE_B = (
    "在保持 3 号机停位 (140, 140, 180) 不变的前提下：本段时间过半之后"
    "全体（每一架）灯光改成蓝色系并保持到段尾。"
)


def red_dominant(rgb):
    r, g, b = rgb
    return r >= 90 and r > b and r >= g


def _eval_multi_position(data, fps, window, _ctx):
    ok0, d0 = check_drone_at(data, fps, 0, window[1] - 0.3, (200, 120, 150), tol_cm=25.0)
    ok6, d6 = check_drone_at(data, fps, 6, window[1] - 0.3, (360, 120, 150), tol_cm=25.0)
    ok = ok0 and ok6
    fb = None
    if not ok:
        parts = []
        if not ok0:
            parts.append(f"drones[0] 实测 {tuple(d0['actual'])}，要求 (200,120,150)±25")
        if not ok6:
            parts.append(f"drones[6] 实测 {tuple(d6['actual'])}，要求 (360,120,150)±25")
        fb = "指令仍未满足：" + "；".join(parts) + "。分别在段末单独 move2 修正，其余机让开前排。"
    return "multi_position", ok, {"d0": d0, "d6": d6}, fb


def _eval_formation_line(data, fps, window, _ctx):
    ok, detail = check_collinear(data, fps, window[1] - 0.3, max_residual_cm=35.0, min_span_cm=250.0)
    fb = None
    if not ok:
        fb = (
            f"指令仍未满足：段尾队形离直线偏差 {detail['max_residual_cm']}cm"
            f"（限 35）、跨度 {detail['span_cm']}cm（需 ≥250）。"
            "把段尾点表改成一条显式斜线：如 (80+i*65, 80+i*65, z_i)，i=0..6。"
        )
    return "formation_line", ok, detail, fb


def _eval_precheck_fired(_data, _fps, _window, ctx):
    warnings = ctx.get("precheck_warnings") or []
    ok = any("越界" in w for w in warnings)
    fb = None  # 预检是确定性行为，不需要模型修正
    return "precheck_fired", ok, {"warnings": warnings}, fb


def _eval_partial_light(data, fps, window, _ctx):
    mid = (window[0] + window[1]) / 2.0
    ok2, d2 = check_color_window(data, fps, mid + 0.5, window[1] - 0.3, red_dominant,
                                 drones=[2], min_fraction=0.6)
    others = [k for k in range(len(data)) if k != 2]
    _ok_o, d_o = check_color_window(data, fps, mid + 0.5, window[1] - 0.3, red_dominant,
                                    drones=others, min_fraction=0.0)
    leak = [k for k, v in d_o["per_drone_fraction"].items() if v > 0.35]
    ok = ok2 and not leak
    fb = None
    if not ok:
        parts = []
        if not ok2:
            parts.append(f"drones[2] 红色占比 {d2['per_drone_fraction'].get(2, 0)}（需 ≥0.6）")
        if leak:
            parts.append(f"机 {leak} 不该跟着变红（指令只改 2 号机）")
        fb = "指令仍未满足：" + "；".join(parts) + "。只对 drones[2] 设红色，其余保持原配色。"
    return "partial_light", ok, {"d2": d2, "others": d_o}, fb


def _eval_sync_flash(data, fps, window, _ctx):
    ok, detail = check_sync_pulses(
        data, fps, window[0] + 1.5, window[1] - 1.0, expected_pulses=3, sync_tol_s=0.35
    )
    fb = None
    if not ok:
        fb = (
            f"指令仍未满足：各机脉冲数 {detail['pulse_counts']}（需每机 ≥3），"
            f"脉冲对齐偏差 {detail['pulse_spreads_s']}s（需 ≤0.35s）。"
            "全体一起做 3 次 亮(≥150)→灭(≤60) 的循环：flash_group(drones, color, times=3, ...)"
            " 或统一 for 循环 TurnOnAll/TurnOffAll，不要逐机错开。"
        )
    return "sync_flash", ok, detail, fb


def _eval_dark_multicolor(data, fps, window, _ctx):
    mid = (window[0] + window[1]) / 2.0
    ok, detail = check_dark_multicolor(data, fps, mid + 0.5, window[1] - 0.3)
    fb = None
    if not ok:
        fb = (
            f"指令仍未满足：色相桶 {detail['hues'].get('hue_buckets')}（需 ≥4 桶）、"
            f"低亮度达标机占比 {detail['dark_qualified_fraction']}（需 ≥0.7，"
            f"亮度峰值 {detail['brightness_peaks']}，每通道 ≤130 且不灭灯）。"
            "每机不同色相但数值压低，如 (90, 20, 70) 这类暗彩。"
        )
    return "dark_multicolor", ok, detail, fb


def _eval_hold(data, fps, window, _ctx):
    ok, detail = check_group_hold(
        data, fps, window[0] + 1.0, window[1] - 0.5, min_hold_s=1.6, max_drift_cm=12.0
    )
    fb = None
    if not ok:
        fb = (
            f"指令仍未满足：最长全体静止亮灯区间 {detail['longest_hold_s']}s（需 ≥1.6s）。"
            "中段安排一个明确定格：全体到位后同时 apply_light + delay(2000)，期间不 move。"
        )
    return "hold", ok, detail, fb


def _eval_slow(data, fps, window, _ctx):
    ok, detail = check_max_speed(data, fps, window[0] + 0.5, window[1] - 0.3, max_cm_s=140.0)
    fb = None
    if not ok:
        fb = (
            f"指令仍未满足：瞬时速度峰值 {detail['peak_speed_cm_s']}cm/s、"
            f"超限采样占比 {detail['over_limit_fraction']}（限 120cm/s，验收容差 140）。"
            "加长每个 move2 的 flying_ms 或缩短单次位移；保持动作铺满窗口。"
        )
    return "slow_motion", ok, detail, fb


def _eval_negative(data, fps, window, ctx):
    alt_ok, alt_detail = check_max_altitude(data, fps, window[0] + 0.3, window[1] - 0.3, max_z_cm=210.0)
    degradation = ctx.get("_directed_degradation") or {}
    circle_fraction = float(degradation.get("circle_like_fraction", 0.0) or 0.0)
    circle_ok = circle_fraction < 0.5
    ok = alt_ok and circle_ok
    detail = {"altitude": alt_detail, "circle_like_fraction": circle_fraction}
    fb = None
    if not ok:
        parts = []
        if not alt_ok:
            parts.append(
                f"d{alt_detail['offender']} 飞到 {alt_detail['peak_z_cm']}cm"
                "（禁令：全程 ≤200，验收容差 210）——把 Z 压回 200 以下"
            )
        if not circle_ok:
            parts.append(
                f"仍在绕圈（circle_like={circle_fraction:.2f}）——禁令：不要圆形/环形队形，"
                "改成直线/斜线/散点等非圆几何"
            )
        fb = "禁令仍被违反：" + "；".join(parts) + "。"
    return "negative_constraints", ok, detail, fb


def _eval_swap(data, fps, window, _ctx):
    entry3 = drone_position_at(data, fps, 3, window[0] + 0.2)
    entry4 = drone_position_at(data, fps, 4, window[0] + 0.2)
    ok3, d3 = check_drone_at(data, fps, 3, window[1] - 0.3, entry4, tol_cm=45.0)
    ok4, d4 = check_drone_at(data, fps, 4, window[1] - 0.3, entry3, tol_cm=45.0)
    ok = ok3 and ok4
    fb = None
    if not ok:
        fb = (
            f"指令仍未满足：交换后 drones[3] 应停在 {tuple(round(v,0) for v in entry4)}±45"
            f"（实测 {tuple(d3['actual'])}），drones[4] 应停在 {tuple(round(v,0) for v in entry3)}±45"
            f"（实测 {tuple(d4['actual'])}）。保持身份保持写法，对穿用错峰/绕行清冲突。"
        )
    return "swap", ok, {"d3": d3, "d4": d4}, fb


def _case_specs() -> dict[int, dict]:
    return {
        1: {"name": "position_hold", "directives": [POSITION_DIRECTIVE], "evals": [_eval_position]},
        2: {"name": "blue_second_half", "directives": [LIGHTING_DIRECTIVE], "evals": [_eval_lighting]},
        3: {
            "name": "combo_position_and_blue",
            "directives": [POSITION_DIRECTIVE, LIGHTING_DIRECTIVE],
            "evals": [_eval_position, _eval_lighting],
        },
        4: {"name": "fuzzy_center_left", "directives": [FUZZY_DIRECTIVE], "evals": [_eval_fuzzy_box]},
        5: {"name": "relative_refinement", "special": "relative"},
        6: {"name": "rainbow_wave_fade", "directives": [RAINBOW_DIRECTIVE], "evals": [_eval_rainbow]},
        7: {"name": "multi_drone_position", "directives": [MULTI_POSITION_DIRECTIVE],
            "evals": [_eval_multi_position]},
        8: {"name": "formation_line", "directives": [FORMATION_LINE_DIRECTIVE],
            "evals": [_eval_formation_line]},
        9: {"name": "infeasible_precheck", "directives": [INFEASIBLE_DIRECTIVE],
            "evals": [_eval_precheck_fired], "skip_degradation": True},
        10: {"name": "partial_lighting", "directives": [PARTIAL_LIGHT_DIRECTIVE],
             "evals": [_eval_partial_light]},
        11: {"name": "sync_flash_x3", "directives": [SYNC_FLASH_DIRECTIVE],
             "evals": [_eval_sync_flash]},
        12: {"name": "dark_multicolor", "directives": [DARK_MULTI_DIRECTIVE],
             "evals": [_eval_dark_multicolor]},
        13: {"name": "hold_still_2s", "directives": [HOLD_DIRECTIVE], "evals": [_eval_hold]},
        14: {"name": "swap_identity_through_safety", "directives": [SWAP_DIRECTIVE],
             "evals": [_eval_swap]},
        15: {"name": "regret_undo", "special": "regret"},
        16: {"name": "sequential_combo", "special": "sequential"},
        17: {"name": "slow_elegant", "directives": [SLOW_DIRECTIVE], "evals": [_eval_slow]},
        18: {"name": "negative_constraints", "directives": [NEGATIVE_DIRECTIVE],
             "evals": [_eval_negative]},
    }


MAX_LLM_CALLS_PER_PHASE = 10  # 弱模型保险丝：每个生成阶段的调用次数硬预算


def _generate(session: Session, provider: str, feedback: str, max_attempts: int):
    rounds = session.generate_until_safe_with_llm(
        provider=provider,
        feedback=feedback,
        max_attempts=max_attempts,
        use_planning_pass=True,
        max_llm_calls=MAX_LLM_CALLS_PER_PHASE,
    )
    return rounds, (rounds[-1].validation if rounds else None)


def _directed_loop(
    session: Session,
    provider: str,
    directive: str,
    evals,
    window,
    project: Path,
    max_attempts: int,
    directive_rounds: int,
    verdict: dict,
):
    """指令下达 → 安全生成 → 轨迹断言 → 未达标用实测偏差再修（导演修正回路）。"""
    feedback = directive
    last_validation = None
    last_assertions: dict = {}
    for round_index in range(1, directive_rounds + 2):
        _rounds, validation = _generate(session, provider, feedback, max_attempts)
        last_validation = validation
        verdict.setdefault("llm_calls_per_phase", []).append(session._llm_calls_used)
        if session.last_budget_exhausted:
            verdict["budget_exhausted"] = True
        if session.last_precheck_warnings:
            verdict["precheck_warnings"] = list(session.last_precheck_warnings)
        if validation is not None:
            # 供否定约束类断言读取验证器的退化指标（circle_like 等）
            verdict["_directed_degradation"] = dict(validation.degradation or {})
        if not (validation and validation.passed):
            from core.directive_advisor import explain_conflict

            verdict.setdefault("directive_trace", []).append(
                {"round": round_index, "safety_passed": False}
            )
            verdict["explanation"] = explain_conflict(validation, directive)
            # 保留上一轮的断言细节：安全崩在修正轮时，之前的偏差数据是关键诊断
            return False, last_assertions, last_validation
        data, fps = load_trajectory(project / "output")
        assertions = {}
        repair_notes = []
        all_ok = True
        for evaluator in evals:
            name, ok, detail, fb = evaluator(data, fps, window, verdict)
            assertions[name] = {"ok": ok, **detail}
            all_ok = all_ok and ok
            if fb:
                repair_notes.append(fb)
        last_assertions = assertions
        verdict.setdefault("directive_trace", []).append(
            {"round": round_index, "safety_passed": True,
             "assertions": {k: v["ok"] for k, v in assertions.items()}}
        )
        if all_ok or round_index > directive_rounds:
            return all_ok, assertions, last_validation
        feedback = directive + "\n\n## 上轮执行偏差（逐条修正，保持已满足的部分不变）\n" + "\n\n".join(repair_notes)
    return False, {}, last_validation


def _setup_project(
    case_id: int, spec: dict, provider: str, max_attempts: int, verdict: dict,
    stage: Path | None = None,
):
    stamp = time.strftime("%Y%m%d_%H%M%S")
    name = f"director_case{case_id}_{spec['name']}_{stamp}"
    project = TOOL_ROOT / "agent_projects" / name
    verdict["project"] = name

    if stage is not None:
        # 舞台复用：从 S01 已锁定的快照起步，跳过重复的 S01 生成
        shutil.copytree(stage, project)
        session = Session(project, gate_profile="safety")
        if session.state.locked_segment_ids != ["S01"]:
            verdict["error"] = (
                f"stage must have exactly S01 locked, got {session.state.locked_segment_ids}"
            )
            return None, None
        verdict["s01_locked"] = True
        verdict["stage"] = stage.name
    else:
        shutil.copytree(TOOL_ROOT / "project_template", project)
        session = Session(project, gate_profile="safety")
        _rounds, validation = _generate(session, provider, "", max_attempts)
        if not (validation and validation.passed):
            verdict["error"] = "S01 generation did not pass"
            return None, None
        approval = session.approve_and_lock()
        verdict["s01_locked"] = bool(approval.locked)
        if not approval.locked:
            verdict["error"] = f"S01 lock failed: {approval.reason}"
            return None, None

    seg = session.state.current_segment
    if seg is None or seg.id != "S02":
        verdict["error"] = f"unexpected current segment: {seg and seg.id}"
        return None, None
    verdict["window"] = [float(seg.start_time), float(seg.end_time)]
    return project, session


def _run_case(
    case_id: int, spec: dict, provider: str, max_attempts: int,
    directive_rounds: int, stage: Path | None = None,
) -> dict:
    verdict: dict = {
        "case": case_id, "name": spec["name"], "provider": provider,
        "s01_locked": False, "baseline_ok": None, "generation_ok": False,
        "assertions": {}, "degradation": None, "passed": False,
    }
    project, session = _setup_project(case_id, spec, provider, max_attempts, verdict, stage=stage)
    if project is None:
        return verdict
    window = tuple(verdict["window"])

    if spec.get("special") == "relative":
        return _run_relative_case(session, project, provider, window, max_attempts, directive_rounds, verdict)
    if spec.get("special") == "regret":
        return _run_regret_case(session, project, provider, window, max_attempts, directive_rounds, verdict)
    if spec.get("special") == "sequential":
        return _run_sequential_case(session, project, provider, window, max_attempts, directive_rounds, verdict)

    directive = format_directive_checklist(spec["directives"])
    verdict["directive"] = directive

    # baseline（无指令）：退化对照
    _rounds, baseline_validation = _generate(session, provider, "", max_attempts)
    baseline_degradation = dict(baseline_validation.degradation) if baseline_validation else {}
    verdict["baseline_ok"] = bool(baseline_validation and baseline_validation.passed)

    ok, assertions, directed_validation = _directed_loop(
        session, provider, directive, spec["evals"], window, project,
        max_attempts, directive_rounds, verdict,
    )
    verdict["assertions"] = assertions
    if directed_validation is None or not directed_validation.passed:
        verdict["error"] = "directed regeneration did not pass safety gates"
        return verdict
    verdict["generation_ok"] = True

    if spec.get("skip_degradation"):
        verdict["degradation"] = {"ok": True, "note": "case asserts advisor behavior; degradation n/a"}
        verdict["passed"] = bool(ok)
        return verdict
    degr_ok, degr_detail = check_no_new_degradation(
        baseline_degradation, dict(directed_validation.degradation or {})
    )
    verdict["degradation"] = {"ok": degr_ok, **degr_detail}
    verdict["passed"] = bool(ok and degr_ok)
    return verdict


def _run_regret_case(session, project, provider, window, max_attempts, directive_rounds, verdict):
    """case 15（Q2）：先"往左一大步"，再"说错了撤销"——最新指令优先。"""
    verdict["directive"] = REGRET_STAGE_A + " → " + REGRET_STAGE_B
    entry2 = None

    def eval_stage_a(data, fps, win, _ctx):
        nonlocal entry2
        if entry2 is None:
            entry2 = drone_position_at(data, fps, 2, win[0] + 0.2)
        p = drone_position_at(data, fps, 2, win[1] - 0.3)
        ok, detail = check_relative_shift(entry2, p, axis=0, sign=-1, min_cm=60.0,
                                          max_other_drift_cm=200.0)
        fb = None
        if not ok:
            fb = (
                f"指令仍未满足：2 号机段尾 x 应比入口 {entry2[0]:.0f} 至少小 60cm，"
                f"实测 {tuple(detail['after'])}。段末单独 move2 修正。"
            )
        return "stage_a_left", ok, detail, fb

    ok_a, assertions_a, validation_a = _directed_loop(
        session, provider, REGRET_STAGE_A, [eval_stage_a], window, project,
        max_attempts, directive_rounds, verdict,
    )
    verdict["assertions"]["stage_a"] = assertions_a
    if not ok_a or validation_a is None:
        verdict["error"] = "stage A (move left) not satisfied"
        return verdict
    data, fps = load_trajectory(project / "output")
    stage_a_pos = drone_position_at(data, fps, 2, window[1] - 0.3)
    verdict["stage_a_position"] = [round(v, 1) for v in stage_a_pos]

    def eval_stage_b(data, fps, win, _ctx):
        p = drone_position_at(data, fps, 2, win[1] - 0.3)
        back_near_entry = abs(p[0] - entry2[0]) <= 60.0
        moved_back_right = p[0] > stage_a_pos[0] + 40.0
        ok = back_near_entry and moved_back_right
        detail = {
            "entry": [round(v, 1) for v in entry2],
            "stage_a": [round(v, 1) for v in stage_a_pos],
            "final": [round(v, 1) for v in p],
        }
        fb = None
        if not ok:
            fb = (
                f"撤销指令仍未满足：2 号机应回到入口 x≈{entry2[0]:.0f}±60"
                f"（上一版在 {stage_a_pos[0]:.0f}），实测 {p[0]:.0f}。"
                "以最新指令为准：回到入口位置附近。"
            )
        return "stage_b_undo", ok, detail, fb

    ok_b, assertions_b, validation_b = _directed_loop(
        session, provider, REGRET_STAGE_B, [eval_stage_b], window, project,
        max_attempts, directive_rounds, verdict,
    )
    verdict["assertions"]["stage_b"] = assertions_b
    if validation_b is None or not validation_b.passed:
        verdict["error"] = "stage B regeneration did not pass safety gates"
        return verdict
    verdict["generation_ok"] = True
    verdict["degradation"] = {"ok": True, "note": "regret case compares positions"}
    verdict["passed"] = bool(ok_a and ok_b)
    return verdict


def _run_sequential_case(session, project, provider, window, max_attempts, directive_rounds, verdict):
    """case 16：组合指令的产品路径——逐条下达，后条要求保持前条成果。"""
    verdict["directive"] = POSITION_DIRECTIVE + " → " + SEQ_STAGE_B

    ok_a, assertions_a, validation_a = _directed_loop(
        session, provider, POSITION_DIRECTIVE, [_eval_position], window, project,
        max_attempts, directive_rounds, verdict,
    )
    verdict["assertions"]["stage_a"] = assertions_a
    if not ok_a or validation_a is None:
        verdict["error"] = "stage A (position) not satisfied"
        return verdict

    def eval_stage_b_both(data, fps, win, ctx):
        name_p, ok_p, detail_p, fb_p = _eval_position(data, fps, win, ctx)
        name_l, ok_l, detail_l, fb_l = _eval_lighting(data, fps, win, ctx)
        ok = ok_p and ok_l
        fb = None
        if not ok:
            notes = [f for f in (fb_p, fb_l) if f]
            fb = "\n".join(notes) + "\n（两条都必须满足：位置保持 + 后半蓝色）"
        return "position_and_lighting", ok, {"position": detail_p, "lighting": detail_l}, fb

    ok_b, assertions_b, validation_b = _directed_loop(
        session, provider, SEQ_STAGE_B, [eval_stage_b_both], window, project,
        max_attempts, directive_rounds, verdict,
    )
    verdict["assertions"]["stage_b"] = assertions_b
    if validation_b is None or not validation_b.passed:
        verdict["error"] = "stage B regeneration did not pass safety gates"
        return verdict
    verdict["generation_ok"] = True
    verdict["degradation"] = {"ok": True, "note": "sequential case asserts both directives"}
    verdict["passed"] = bool(ok_a and ok_b)
    return verdict


def _run_relative_case(session, project, provider, window, max_attempts, directive_rounds, verdict):
    """case 5：先"停到中间"，再"再往左一点"——相对方位的两段式导演流。"""
    center_box = ((170.0, 390.0), (170.0, 390.0), (100.0, 230.0))

    def eval_stage_a(data, fps, win, _ctx):
        ok, detail = check_drone_in_box(data, fps, 2, win[1] - 0.3, center_box)
        fb = None
        if not ok:
            fb = (
                f"指令仍未满足：drones[2] 段尾实测 {tuple(detail['actual'])}，"
                "要求停在场地中间附近（x/y 170-390，z 100-230）。用身份保持写法修正。"
            )
        return "stage_a_center", ok, detail, fb

    verdict["directive"] = RELATIVE_STAGE_A + " → " + RELATIVE_STAGE_B
    ok_a, assertions_a, validation_a = _directed_loop(
        session, provider, RELATIVE_STAGE_A, [eval_stage_a], window, project,
        max_attempts, directive_rounds, verdict,
    )
    verdict["assertions"]["stage_a"] = assertions_a
    if not ok_a or validation_a is None:
        verdict["error"] = "stage A (move to center) not satisfied"
        return verdict
    data, fps = load_trajectory(project / "output")
    p1 = drone_position_at(data, fps, 2, window[1] - 0.3)
    verdict["stage_a_position"] = [round(v, 1) for v in p1]

    def eval_stage_b(data, fps, win, _ctx):
        p2 = drone_position_at(data, fps, 2, win[1] - 0.3)
        ok, detail = check_relative_shift(p1, p2, axis=0, sign=-1, min_cm=20.0, max_other_drift_cm=120.0)
        fb = None
        if not ok:
            fb = (
                f"指令仍未满足：'再往左一点' = x 比上一版 ({p1[0]:.0f},{p1[1]:.0f},{p1[2]:.0f}) "
                f"减少 ≥20cm 且 y/z 基本保持；实测 {tuple(detail['after'])}"
                f"（x 位移 {detail['moved_cm']}cm）。保持其余不变，只把 2 号机段尾 x 再减 40-80。"
            )
        return "stage_b_left_shift", ok, detail, fb

    ok_b, assertions_b, validation_b = _directed_loop(
        session, provider, RELATIVE_STAGE_B, [eval_stage_b], window, project,
        max_attempts, directive_rounds, verdict,
    )
    verdict["assertions"]["stage_b"] = assertions_b
    if validation_b is None or not validation_b.passed:
        verdict["error"] = "stage B regeneration did not pass safety gates"
        return verdict
    verdict["generation_ok"] = True
    verdict["degradation"] = {"ok": True, "note": "relative case compares positions, not degradation"}
    verdict["passed"] = bool(ok_a and ok_b)
    return verdict


def _make_stage(provider: str, max_attempts: int, name: str) -> int:
    """生成一个 S01 已锁定的舞台快照，供 --stage 复用。"""
    project = TOOL_ROOT / "agent_projects" / name
    if project.exists():
        raise SystemExit(f"stage already exists: {project}")
    shutil.copytree(TOOL_ROOT / "project_template", project)
    session = Session(project, gate_profile="safety")
    _rounds, validation = _generate(session, provider, "", max_attempts)
    if not (validation and validation.passed):
        print("stage S01 generation did not pass")
        return 1
    approval = session.approve_and_lock()
    if not approval.locked:
        print(f"stage S01 lock failed: {approval.reason}")
        return 1
    print(f"stage ready: {project}  locked={session.state.locked_segment_ids}")
    return 0


def _resolve_stage(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        candidate = TOOL_ROOT / "agent_projects" / value
        path = candidate if candidate.exists() else (Path.cwd() / value).resolve()
    if not (path / "state.json").exists():
        raise SystemExit(f"stage project not found: {path}")
    return path


def main(argv: list[str] | None = None) -> int:
    global MAX_LLM_CALLS_PER_PHASE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--cases", default="1,2,3,4,5,6",
                        help="逗号分隔的 case 号，或 'all'（1-16 全量覆盖套件）")
    parser.add_argument("--max-attempts", type=int, default=4)
    parser.add_argument("--directive-rounds", type=int, default=2,
                        help="断言失败后的导演修正轮数（实测偏差回灌）")
    parser.add_argument("--max-llm-calls", type=int, default=MAX_LLM_CALLS_PER_PHASE,
                        help="每个生成阶段的 LLM 调用次数硬预算（弱模型快速失败）")
    parser.add_argument("--stage", help="S01 已锁定的舞台快照项目（名字或路径），跳过重复的 S01 生成")
    parser.add_argument("--make-stage", help="只生成并锁定 S01，产出可复用舞台快照后退出")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    MAX_LLM_CALLS_PER_PHASE = max(1, int(args.max_llm_calls))

    if args.make_stage:
        return _make_stage(args.provider, args.max_attempts, args.make_stage)
    stage = _resolve_stage(args.stage)

    specs = _case_specs()
    if args.cases.strip().lower() == "all":
        case_ids = sorted(specs)
    else:
        case_ids = [int(c) for c in args.cases.split(",") if c.strip()]
    results: list[dict] = []
    for case_id in case_ids:
        spec = specs[case_id]
        print(f"\n### director case {case_id}: {spec['name']} ({args.provider})")
        try:
            verdict = _run_case(case_id, spec, args.provider, args.max_attempts,
                                args.directive_rounds, stage=stage)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            traceback.print_exc()
            verdict = {
                "case": case_id, "name": spec["name"], "provider": args.provider,
                "passed": False, "error": f"{type(exc).__name__}: {str(exc)[-300:]}",
            }
        results.append(verdict)
        print(json.dumps(verdict, ensure_ascii=False, indent=1))

    report = {
        "provider": args.provider,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "directive_rounds": args.directive_rounds,
        "passed": sum(1 for r in results if r.get("passed")),
        "total": len(results),
        "cases": results,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else REPORT_DIR / f"cases_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nreport: {out}  passed {report['passed']}/{report['total']}")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
