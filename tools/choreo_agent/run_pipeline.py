#!/usr/bin/env python3
"""Fresh full-flow stability runner for choreo_agent.

This runner is intentionally strict:
- starts from project_template when requested;
- follows Session.current_segment, so dynamic S07/S08 insertion is tested;
- never uses human override or external replacement code;
- records generation/validation summaries in agent_interaction.log and
  stability_result.json.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_ROOT = REPO_ROOT / "tools" / "choreo_agent"
sys.path.insert(0, str(TOOL_ROOT))

from core import Session
from core.token_usage import summarize_usage


DEFAULT_MAX_CYCLES_PER_SEGMENT = 3
DEFAULT_MAX_ATTEMPTS_PER_CYCLE = 5


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    project_root = _resolve_project(args.project, args.fresh_name)
    if args.fresh_name:
        _init_fresh_project(
            project_root,
            provider=args.provider,
            mode=args.mode,
            drone_count=args.drone_count,
            music=args.music,
            music_title=args.music_title,
        )

    result = run_full_flow(
        project_root=project_root,
        provider=args.provider,
        max_cycles_per_segment=args.max_cycles_per_segment,
        max_attempts_per_cycle=args.max_attempts_per_cycle,
        use_planning_pass=not args.no_planning_pass,
        retry_sleep_s=args.retry_sleep_s,
        max_api_exceptions_per_segment=args.max_api_exceptions_per_segment,
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0 if result["summary"]["completed"] else 1


def run_full_flow(
    project_root: Path,
    provider: str | None = None,
    max_cycles_per_segment: int = DEFAULT_MAX_CYCLES_PER_SEGMENT,
    max_attempts_per_cycle: int = DEFAULT_MAX_ATTEMPTS_PER_CYCLE,
    use_planning_pass: bool = True,
    retry_sleep_s: int = 30,
    max_api_exceptions_per_segment: int = 5,
) -> dict:
    project_root = Path(project_root).resolve()
    log_path = project_root / "agent_interaction.log"
    _append(log_path, f"\n\n# FULL FLOW START {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    records: list[dict] = []
    started_at = time.time()
    session = Session(project_root)
    _write_partial_result(project_root, records, session, started_at, provider=provider or session.state.provider)

    while True:
        session = Session(project_root)
        seg = session.state.current_segment
        if seg is None:
            break

        run_provider = provider or session.state.provider
        segment_record = {
            "segment": seg.id,
            "start_time": seg.start_time,
            "end_time": seg.end_time,
            "provider": run_provider,
            "cycles": [],
            "locked": False,
            "failure_category": None,
        }
        records.append(segment_record)
        feedback = _segment_feedback(seg.id, session.state.drone_count)
        _append(
            log_path,
            (
                f"\n# SEGMENT {seg.id} {seg.start_time}-{seg.end_time}s\n"
                f"# FEEDBACK\n{feedback}\n"
            ),
        )
        _write_partial_result(project_root, records, session, started_at, provider=run_provider)

        locked = False
        for cycle in range(1, max_cycles_per_segment + 1):
            _append(log_path, f"\n# {seg.id} CYCLE {cycle} START\n")
            _write_partial_result(project_root, records, session, started_at, provider=run_provider)
            stream = _StreamLog(log_path, seg.id, cycle)
            try:
                rounds = session.generate_until_safe_with_llm(
                    provider=run_provider,
                    feedback=feedback,
                    max_attempts=max_attempts_per_cycle,
                    use_planning_pass=use_planning_pass,
                    on_delta=stream.delta,
                    on_reasoning_delta=stream.reasoning_delta,
                    on_heartbeat=stream.heartbeat,
                    on_round_start=stream.round_start,
                )
            except Exception as exc:
                category = _failure_category_from_exception(exc)
                cycle_record = {
                    "cycle": cycle,
                    "exception": f"{type(exc).__name__}: {str(exc)[-500:]}",
                    "failure_category": category,
                }
                segment_record["cycles"].append(cycle_record)
                segment_record["failure_category"] = category
                _append(
                    log_path,
                    (
                        f"\n# {seg.id} CYCLE {cycle} EXCEPTION\n"
                        f"{cycle_record['exception']}\n"
                        f"{traceback.format_exc()}\n"
                    ),
                )
                _write_partial_result(
                    project_root,
                    records,
                    session,
                    started_at,
                    provider=run_provider,
                    last_failure_category=category,
                    last_exception=cycle_record["exception"],
                )
                # Count API exceptions per segment
                api_exc_count = sum(1 for c in segment_record["cycles"] if c.get("failure_category") == "api_network")
                if category == "api_network" and api_exc_count >= max_api_exceptions_per_segment:
                    _append(log_path, f"\n# STOP {seg.id} max API exceptions reached\n")
                    break
                if category == "api_network":
                    time.sleep(retry_sleep_s)
                feedback = feedback + "\n\nAPI/网络层失败；继续同一段。"
                continue

            cycle_record = {
                "cycle": cycle,
                "rounds": [_round_summary(round_item) for round_item in rounds],
            }
            segment_record["cycles"].append(cycle_record)
            _write_partial_result(project_root, records, session, started_at, provider=run_provider)
            _append(
                log_path,
                f"\n# {seg.id} CYCLE {cycle} SUMMARY\n"
                + json.dumps(cycle_record, ensure_ascii=False, indent=2)
                + "\n",
            )

            if rounds and rounds[-1].validation and rounds[-1].validation.passed:
                approval = session.approve_and_lock(allow_human_override=False)
                lock_summary = {
                    "locked": approval.locked,
                    "reason": approval.reason,
                    "validation": _validation_summary(approval.validation),
                }
                _append(
                    log_path,
                    f"\n# {seg.id} LOCK ATTEMPT\n"
                    + json.dumps(lock_summary, ensure_ascii=False, indent=2)
                    + "\n",
                )
                _write_partial_result(
                    project_root,
                    records,
                    session,
                    started_at,
                    provider=run_provider,
                    last_failure_category=None if approval.locked else "lock_failed",
                    last_exception=None if approval.locked else (approval.reason or "lock failed"),
                )
                if approval.locked:
                    segment_record["locked"] = True
                    segment_record["final_validation"] = lock_summary["validation"]
                    locked = True
                    _write_partial_result(project_root, records, session, started_at, provider=run_provider)
                    break
                segment_record["failure_category"] = "lock_failed"
                feedback = feedback + "\n\n验证通过但锁定失败：" + (approval.reason or "unknown")
            else:
                last_validation = rounds[-1].validation if rounds else None
                category = _failure_category_from_validation(last_validation)
                segment_record["failure_category"] = category
                feedback = feedback + "\n\n继续修复 validator 反馈，目标是本段 passed=True。"
                if last_validation is not None:
                    feedback += "\n" + _compact_runner_validation_feedback(last_validation)

        if not locked:
            _append(log_path, f"\n# STOP {seg.id} not locked\n")
            break

    session = Session(project_root)
    completed = session.state.current_segment is None
    summary = {
        "project": str(project_root),
        "provider": provider or session.state.provider,
        "completed": completed,
        "locked_segment_ids": session.state.locked_segment_ids,
        "elapsed_s": round(time.time() - started_at, 1),
        "failed_segment": None if completed else session.state.current_segment.id,
        "token_usage": _token_usage_summary(records),
        "records": records,
    }
    result = {"summary": summary}
    _write_json_atomic(project_root / "stability_result.json", result)
    _append(
        log_path,
        "\n# FULL FLOW RESULT\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
    )
    return result


class _StreamLog:
    def __init__(self, log_path: Path, segment_id: str, cycle: int):
        self.log_path = log_path
        self.segment_id = segment_id
        self.cycle = cycle
        self._reasoning_open = False
        self._content_open = False
        self._last_heartbeat = 0.0

    def round_start(self, index: int) -> None:
        _append(self.log_path, f"\n# {self.segment_id} CYCLE {self.cycle} ROUND {index} START\n")

    def reasoning_delta(self, text: str) -> None:
        if not self._reasoning_open:
            _append(self.log_path, f"\n# {self.segment_id} CYCLE {self.cycle} REASONING\n")
            self._reasoning_open = True
        _append(self.log_path, text)

    def delta(self, text: str) -> None:
        if not self._content_open:
            _append(self.log_path, f"\n# {self.segment_id} CYCLE {self.cycle} CONTENT\n")
            self._content_open = True
        _append(self.log_path, text)

    def heartbeat(self) -> None:
        now = time.monotonic()
        if now - self._last_heartbeat >= 15:
            _append(self.log_path, f"\n# {self.segment_id} CYCLE {self.cycle} HEARTBEAT\n")
            self._last_heartbeat = now


def _round_summary(round_item) -> dict:
    response = round_item.response
    validation = round_item.validation
    return {
        "round": round_item.index,
        "model": response.model if response else None,
        "input_tokens": _optional_int(getattr(response, "input_tokens", None)) if response else None,
        "output_tokens": _optional_int(getattr(response, "output_tokens", None)) if response else None,
        "prompt_cache_hit_tokens": _optional_int(getattr(response, "prompt_cache_hit_tokens", None)) if response else None,
        "prompt_cache_miss_tokens": _optional_int(getattr(response, "prompt_cache_miss_tokens", None)) if response else None,
        "total_tokens": _optional_int(getattr(response, "total_tokens", None)) if response else None,
        "estimated_input_tokens": _optional_int(getattr(response, "estimated_input_tokens", None)) if response else None,
        "estimated_output_tokens": _optional_int(getattr(response, "estimated_output_tokens", None)) if response else None,
        "system_prompt_chars": _optional_int(getattr(response, "system_prompt_chars", None)) if response else None,
        "user_prompt_chars": _optional_int(getattr(response, "user_prompt_chars", None)) if response else None,
        "prompt_chars": _optional_int(getattr(response, "prompt_chars", None)) if response else None,
        "response_chars": len(response.text or "") if response else 0,
        "reasoning_chars": len(response.reasoning_text or "") if response else 0,
        "raw_usage": _optional_dict(getattr(response, "raw_usage", None)) if response else None,
        "validation": _validation_summary(validation),
    }


def _token_usage_summary(records: list[dict]) -> dict:
    items = []
    for segment_record in records:
        for cycle_record in segment_record.get("cycles", []):
            for round_record in cycle_record.get("rounds", []):
                if round_record.get("model") or round_record.get("response_chars") or round_record.get("reasoning_chars"):
                    items.append(round_record)
    return summarize_usage(items)


def _optional_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _optional_dict(value) -> dict | None:
    return value if isinstance(value, dict) else None


def _optional_bool(value) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_list(value) -> list:
    return value if isinstance(value, list) else []


def _validation_summary(validation) -> dict | None:
    if validation is None:
        return None
    return {
        "passed": validation.passed,
        "quality_window": validation.quality_window,
        "compile_ok": validation.compile_ok,
        "run_ok": validation.run_ok,
        "read_fii_ok": validation.read_fii_ok,
        "dist": validation.distance_warnings,
        "act": validation.action_warnings,
        "minD": validation.min_distance_cm,
        "dense_minD": validation.dense_min_distance_cm,
        "motion": [validation.motion_start_s, validation.motion_end_s],
        "effective": [validation.effective_motion_start_s, validation.effective_motion_end_s],
        "motion_quality_ok": validation.motion_quality_ok,
        "degradation_ok": validation.degradation_ok,
        "composition_ok": _optional_bool(getattr(validation, "composition_ok", True)),
        "code_quality_ok": validation.code_quality_ok,
        "expected_drone_count": _optional_int(getattr(validation, "expected_drone_count", None)),
        "actual_drone_count": _optional_int(getattr(validation, "actual_drone_count", None)),
        "errors": {
            "motion": validation.motion_envelope_errors[:3],
            "effective": validation.effective_motion_errors[:3],
            "quality": validation.motion_quality_errors[:3],
            "degradation": validation.degradation_errors[:3],
            "composition": _optional_list(getattr(validation, "composition_errors", []))[:3],
            "code": validation.code_quality_errors[:3],
            "error": validation.error_message[-300:],
        },
    }


def _compact_runner_validation_feedback(validation) -> str:
    summary = _validation_summary(validation) or {}
    payload = {
        "passed": summary.get("passed"),
        "dist": summary.get("dist"),
        "act": summary.get("act"),
        "minD": summary.get("minD"),
        "dense_minD": summary.get("dense_minD"),
        "motion": summary.get("motion"),
        "effective": summary.get("effective"),
        "errors": summary.get("errors"),
    }
    return json.dumps(payload, ensure_ascii=False)[:2400]


def _failure_category_from_exception(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    api_kw = ["llm", "http", "ssl", "connect", "protocol", "timeout", "read", "remote", "eof", "disconnect", "peer"]
    if any(kw in name or kw in text for kw in api_kw):
        return "api_network"
    return "exception"


def _failure_category_from_validation(validation) -> str:
    if validation is None:
        return "empty_or_unwritten"
    if not validation.compile_ok:
        return "compile"
    if validation.code_quality_errors:
        return "code_quality"
    if not validation.run_ok or not validation.read_fii_ok:
        return "runtime_or_read"
    if validation.action_warnings:
        return "action_incomplete"
    if validation.distance_warnings or validation.collision_intervals:
        return "collision"
    if validation.motion_envelope_errors or validation.effective_motion_errors:
        return "hover_or_low_activity"
    if validation.motion_quality_errors:
        return "motion_quality"
    if getattr(validation, "composition_errors", []):
        return "composition"
    if validation.degradation_errors:
        return "degradation"
    return "unknown_validation"


def _segment_feedback(segment_id: str, drone_count: int = 7) -> str:
    sid = segment_id.upper()
    if sid == "LAND":
        return (
            "继续 LAND。LAND 是降落段，不是正式编舞段。先 auto_init(drones)，"
            f"然后对全部 {int(drone_count)} 架短灯光提示并 d.land()。不要 move2，不要 keyframe。"
        )
    if sid in {"S07", "S08", "S09", "S10", "S11", "S12"}:
        return (
            f"继续 {sid}。这是 LAND 前自动追加的正式编舞段，用来让整首作品真实动作超过 60s。"
            "时间预算：动作（move2 飞行 + 灯光）要贴满整个段窗口，不留 >1s 的静止空窗；"
            "keyframe 数量自定，`min_path_cm=active_min_path_cm(flying_ms)` 让路径匹配时长。"
            "保持高度层，不要原地硬等。"
        )
    return (
        f"继续 {sid}。只重写当前未锁定段，保持安全、连贯、非退化、有高度层。"
        "不要手工改 locked 段；验证器通过后才能锁定。"
    )


def _resolve_project(project: str | None, fresh_name: str | None) -> Path:
    if fresh_name:
        return TOOL_ROOT / "agent_projects" / fresh_name
    if project:
        path = Path(project)
        return path if path.is_absolute() else REPO_ROOT / path
    raise SystemExit("Provide --fresh-name or a project path.")


def _init_fresh_project(
    project_root: Path,
    provider: str | None,
    mode: str,
    drone_count: int,
    music: str | None = None,
    music_title: str | None = None,
) -> None:
    template = TOOL_ROOT / "project_template"
    if project_root.exists():
        raise SystemExit(f"Refusing to overwrite existing project: {project_root}")
    shutil.copytree(template, project_root)
    state_path = project_root / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["name"] = project_root.name
    if provider:
        state["provider"] = provider
    state["mode"] = mode
    state["drone_count"] = max(1, int(drone_count))

    if music:
        _apply_music_plan(
            project_root, state, music,
            provider or state.get("provider", "deepseek"),
            title=music_title,
        )

    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _apply_music_plan(project_root: Path, state: dict, music: str, provider: str, title: str | None = None) -> None:
    """音乐驱动初始化：分析音乐 → LLM 生成章法+段窗 → 重写 state（PLAN 11.11）。

    取代模板里手写的 cannon dramaturgy；模板 composition_plan/段窗仅在
    未传 --music 时作为回退保留。
    """
    from core.composition_planner import generate_composition_plan

    music_path = Path(music)
    if not music_path.is_absolute():
        music_path = (REPO_ROOT / music).resolve()
    if not music_path.exists():
        raise SystemExit(f"music not found: {music_path}")

    print(f"[music plan] analyzing {music_path.name} and generating composition plan...")
    result = generate_composition_plan(
        str(music_path), provider=provider, drone_count=int(state["drone_count"]),
        title=title,
    )
    plan, legacy, brief = result["plan"], result["legacy"], result["brief"]

    state["music_path"] = os.path.relpath(music_path, project_root)
    state["music_duration"] = float(brief["duration_s"])
    state["composition_plan"] = legacy

    windows = {str(s["id"]).upper(): s for s in plan["segments"]}
    for seg in state.get("segments", []):
        sid = str(seg.get("id", "")).upper()
        win = windows.get(sid)
        if not win:
            continue
        seg["start_time"] = float(win["start_s"])
        seg["end_time"] = float(win["end_s"])
        role = win.get("role")
        # LAND 不接受 plan 的编舞角色 — 它只降落（LAND 协议）。
        if role and sid != "LAND":
            seg["intent"] = str(role)

    (project_root / "music_brief.json").write_text(
        json.dumps(brief, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (project_root / "music_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    show_end = windows.get("LAND", {}).get("end_s")
    print(f"[music plan] theme: {str(plan.get('theme'))[:60]} | show_end: {show_end}s")


def _append(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)



def _write_partial_result(project_root: Path, records: list, session, started_at: float,
                          failed_segment: str | None = None,
                          provider: str | None = None,
                          last_failure_category: str | None = None,
                          last_exception: str | None = None) -> None:
    """Write intermediate stability_result.json after each cycle."""
    try:
        summary = {
            "project": str(project_root),
            "provider": provider or session.state.provider,
            "completed": False,
            "current_segment": session.state.current_segment.id if session.state.current_segment else None,
            "locked_segment_ids": session.state.locked_segment_ids,
            "elapsed_s": round(time.time() - started_at, 1),
            "failed_segment": failed_segment or (session.state.current_segment.id if session.state.current_segment else None),
            "last_failure_category": last_failure_category,
            "last_exception": last_exception,
            "token_usage": _token_usage_summary(records),
            "records": records,
        }
        _write_json_atomic(project_root / "stability_result.json", {"summary": summary})
    except Exception:
        pass


def _write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", help="Existing project path.")
    parser.add_argument("--fresh-name", help="Create a fresh project under agent_projects/.")
    parser.add_argument("--music", help="Music file (abs or repo-root relative); generates composition plan + segment windows from it.")
    parser.add_argument("--music-title", help="Human-provided track title/character hint (e.g. 春节序曲); overrides audio-feature mood inference.")
    parser.add_argument("--provider", help="Provider name from ai_providers.local.json.")
    parser.add_argument("--mode", choices=["manual", "fast"], default="manual")
    parser.add_argument("--drone-count", type=int, default=7)
    parser.add_argument("--max-cycles-per-segment", type=int, default=DEFAULT_MAX_CYCLES_PER_SEGMENT)
    parser.add_argument("--max-attempts-per-cycle", type=int, default=DEFAULT_MAX_ATTEMPTS_PER_CYCLE)
    parser.add_argument("--no-planning-pass", action="store_true")
    parser.add_argument("--retry-sleep-s", type=int, default=30)
    parser.add_argument("--max-api-exceptions-per-segment", type=int, default=5)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
