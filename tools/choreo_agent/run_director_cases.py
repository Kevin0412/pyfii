#!/usr/bin/env python3
"""真实 API 导演验收（C7-3b）：细节修改指令 + 轨迹级确认。

每个 case 的流程：
  fresh 项目 → 生成并锁定 S01 → S02 先出 baseline（记录退化指标）→
  下达细节指令重做 S02 → 读回 .fii 做轨迹断言 + 无新增退化 → 逐 case JSON。

用便宜模型（默认 deepseek flash）。安全门（Tier-0/1）始终硬；
gate_profile="safety" 让审美门不干扰导演指令。

Usage:
  conda run -n pyfii python tools/choreo_agent/run_director_cases.py \
      --provider deepseek --cases 1,2,3
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
from core.trajectory_assert import (  # noqa: E402
    blue_dominant,
    check_color_window,
    check_drone_at,
    check_no_new_degradation,
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


def _case_specs() -> dict[int, dict]:
    return {
        1: {"name": "position_hold", "directive": POSITION_DIRECTIVE, "checks": ("position",)},
        2: {"name": "blue_second_half", "directive": LIGHTING_DIRECTIVE, "checks": ("lighting",)},
        3: {
            "name": "combo_position_and_blue",
            "directive": POSITION_DIRECTIVE + "\n" + LIGHTING_DIRECTIVE,
            "checks": ("position", "lighting"),
        },
    }


def _generate(session: Session, provider: str, feedback: str, max_attempts: int):
    rounds = session.generate_until_safe_with_llm(
        provider=provider,
        feedback=feedback,
        max_attempts=max_attempts,
        use_planning_pass=True,
    )
    last_validation = rounds[-1].validation if rounds else None
    return rounds, last_validation


def _run_case(case_id: int, spec: dict, provider: str, max_attempts: int) -> dict:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    name = f"director_case{case_id}_{spec['name']}_{stamp}"
    project = TOOL_ROOT / "agent_projects" / name
    shutil.copytree(TOOL_ROOT / "project_template", project)

    verdict: dict = {
        "case": case_id,
        "name": spec["name"],
        "project": name,
        "provider": provider,
        "directive": spec["directive"],
        "s01_locked": False,
        "baseline_ok": None,
        "generation_ok": False,
        "assertions": {},
        "degradation": None,
        "passed": False,
    }

    session = Session(project, gate_profile="safety")

    # 1) S01：常规生成并锁定（导演验收的前置舞台）
    _rounds, validation = _generate(session, provider, feedback="", max_attempts=max_attempts)
    if not (validation and validation.passed):
        verdict["error"] = "S01 generation did not pass"
        return verdict
    approval = session.approve_and_lock()
    verdict["s01_locked"] = bool(approval.locked)
    if not approval.locked:
        verdict["error"] = f"S01 lock failed: {approval.reason}"
        return verdict

    seg = session.state.current_segment
    if seg is None or seg.id != "S02":
        verdict["error"] = f"unexpected current segment: {seg and seg.id}"
        return verdict
    window = (float(seg.start_time), float(seg.end_time))
    verdict["window"] = list(window)

    # 2) S02 baseline：无指令版本，取退化指标做对照
    _rounds, baseline_validation = _generate(session, provider, feedback="", max_attempts=max_attempts)
    baseline_degradation = dict(baseline_validation.degradation) if baseline_validation else {}
    verdict["baseline_ok"] = bool(baseline_validation and baseline_validation.passed)

    # 3) 下达细节指令重做 S02
    _rounds, directed_validation = _generate(
        session, provider, feedback=spec["directive"], max_attempts=max_attempts
    )
    if not (directed_validation and directed_validation.passed):
        verdict["error"] = "directed regeneration did not pass safety gates"
        return verdict
    verdict["generation_ok"] = True

    # 4) 轨迹断言（读回 output/ 的最终 .fii）
    data, fps = load_trajectory(project / "output")
    checks_ok = True
    if "position" in spec["checks"]:
        ok, detail = check_drone_at(
            data, fps, 3, window[1] - 0.3, POSITION_TARGET, tol_cm=25.0
        )
        verdict["assertions"]["position"] = {"ok": ok, **detail}
        checks_ok = checks_ok and ok
    if "lighting" in spec["checks"]:
        mid = (window[0] + window[1]) / 2.0
        ok, detail = check_color_window(
            data, fps, mid + 0.5, window[1] - 0.3, blue_dominant, min_fraction=0.6
        )
        verdict["assertions"]["lighting"] = {"ok": ok, **detail}
        checks_ok = checks_ok and ok

    # 5) 指令满足不等于验收通过：还必须没有引发结构性塌缩
    directed_degradation = dict(directed_validation.degradation or {})
    degr_ok, degr_detail = check_no_new_degradation(baseline_degradation, directed_degradation)
    verdict["degradation"] = {"ok": degr_ok, **degr_detail}

    verdict["passed"] = bool(checks_ok and degr_ok)
    return verdict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--cases", default="1,2,3")
    parser.add_argument("--max-attempts", type=int, default=4)
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    specs = _case_specs()
    case_ids = [int(c) for c in args.cases.split(",") if c.strip()]
    results: list[dict] = []
    for case_id in case_ids:
        spec = specs[case_id]
        print(f"\n### director case {case_id}: {spec['name']} ({args.provider})")
        try:
            verdict = _run_case(case_id, spec, args.provider, args.max_attempts)
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
