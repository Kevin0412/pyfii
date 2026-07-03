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
    check_color_window,
    check_drone_at,
    check_drone_in_box,
    check_hue_diversity,
    check_no_new_degradation,
    check_relative_shift,
    check_spatial_temporal_order,
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


def _rainbow_predicate(rgb):
    return hue_deg(rgb) is not None


def _eval_rainbow(data, fps, window, _ctx):
    mid = (window[0] + window[1]) / 2.0
    t_end = window[1] - 0.4
    order_ok, order_detail = check_spatial_temporal_order(
        data, fps, mid, t_end, _rainbow_predicate, axis=0, ascending=True,
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
    }


def _generate(session: Session, provider: str, feedback: str, max_attempts: int):
    rounds = session.generate_until_safe_with_llm(
        provider=provider,
        feedback=feedback,
        max_attempts=max_attempts,
        use_planning_pass=True,
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
    for round_index in range(1, directive_rounds + 2):
        _rounds, validation = _generate(session, provider, feedback, max_attempts)
        last_validation = validation
        if not (validation and validation.passed):
            verdict.setdefault("directive_trace", []).append(
                {"round": round_index, "safety_passed": False}
            )
            return False, {}, last_validation
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
        verdict.setdefault("directive_trace", []).append(
            {"round": round_index, "safety_passed": True,
             "assertions": {k: v["ok"] for k, v in assertions.items()}}
        )
        if all_ok or round_index > directive_rounds:
            return all_ok, assertions, last_validation
        feedback = directive + "\n\n## 上轮执行偏差（逐条修正，保持已满足的部分不变）\n" + "\n\n".join(repair_notes)
    return False, {}, last_validation


def _setup_project(case_id: int, spec: dict, provider: str, max_attempts: int, verdict: dict):
    stamp = time.strftime("%Y%m%d_%H%M%S")
    name = f"director_case{case_id}_{spec['name']}_{stamp}"
    project = TOOL_ROOT / "agent_projects" / name
    shutil.copytree(TOOL_ROOT / "project_template", project)
    verdict["project"] = name

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


def _run_case(case_id: int, spec: dict, provider: str, max_attempts: int, directive_rounds: int) -> dict:
    verdict: dict = {
        "case": case_id, "name": spec["name"], "provider": provider,
        "s01_locked": False, "baseline_ok": None, "generation_ok": False,
        "assertions": {}, "degradation": None, "passed": False,
    }
    project, session = _setup_project(case_id, spec, provider, max_attempts, verdict)
    if project is None:
        return verdict
    window = tuple(verdict["window"])

    if spec.get("special") == "relative":
        return _run_relative_case(session, project, provider, window, max_attempts, directive_rounds, verdict)

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

    degr_ok, degr_detail = check_no_new_degradation(
        baseline_degradation, dict(directed_validation.degradation or {})
    )
    verdict["degradation"] = {"ok": degr_ok, **degr_detail}
    verdict["passed"] = bool(ok and degr_ok)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--cases", default="1,2,3,4,5,6")
    parser.add_argument("--max-attempts", type=int, default=4)
    parser.add_argument("--directive-rounds", type=int, default=2,
                        help="断言失败后的导演修正轮数（实测偏差回灌）")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    specs = _case_specs()
    case_ids = [int(c) for c in args.cases.split(",") if c.strip()]
    results: list[dict] = []
    for case_id in case_ids:
        spec = specs[case_id]
        print(f"\n### director case {case_id}: {spec['name']} ({args.provider})")
        try:
            verdict = _run_case(case_id, spec, args.provider, args.max_attempts, args.directive_rounds)
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
