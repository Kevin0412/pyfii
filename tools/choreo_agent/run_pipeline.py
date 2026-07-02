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
import signal
import subprocess
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_ROOT = REPO_ROOT / "tools" / "choreo_agent"
sys.path.insert(0, str(TOOL_ROOT))

from core import Session
from core.token_usage import summarize_usage


DEFAULT_MAX_CYCLES_PER_SEGMENT = 4
DEFAULT_MAX_ATTEMPTS_PER_CYCLE = 5
CONVERGENCE_ROUND_LIMIT = 5


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
            plan_review=args.plan_review,
        )

    director_script = _load_director_script(args.director_script)
    result = run_full_flow(
        project_root=project_root,
        provider=args.provider,
        max_cycles_per_segment=args.max_cycles_per_segment,
        max_attempts_per_cycle=args.max_attempts_per_cycle,
        use_planning_pass=not args.no_planning_pass,
        parallel_candidates=args.parallel_candidates,
        # 导演剧本 = 脚本化的段级评审 + 交互 profile（审美门降建议）
        review_segments=args.review_segments or director_script is not None,
        retry_sleep_s=args.retry_sleep_s,
        max_api_exceptions_per_segment=args.max_api_exceptions_per_segment,
        gate_profile="safety" if director_script is not None else "full",
        director_script=director_script,
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0 if result["summary"]["completed"] else 1


def _load_director_script(value: str | None) -> dict | None:
    """导演剧本 JSON：{"segments": {SID: {"intent": str, "feedback": [str,...]}},
    "session_verdict": str}。feedback 依次在段级评审时下达，耗尽后锁定。"""
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = (REPO_ROOT / value).resolve()
    if not path.exists():
        raise SystemExit(f"director script not found: {path}")
    script = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(script, dict):
        raise SystemExit("director script must be a JSON object")
    return script


def run_full_flow(
    project_root: Path,
    provider: str | None = None,
    max_cycles_per_segment: int = DEFAULT_MAX_CYCLES_PER_SEGMENT,
    max_attempts_per_cycle: int = DEFAULT_MAX_ATTEMPTS_PER_CYCLE,
    use_planning_pass: bool = True,
    parallel_candidates: int = 2,
    review_segments: bool = False,
    retry_sleep_s: int = 30,
    max_api_exceptions_per_segment: int = 5,
    gate_profile: str = "full",
    director_script: dict | None = None,
) -> dict:
    project_root = Path(project_root).resolve()
    # 有导演剧本时评审由脚本驱动，不需要 TTY
    if review_segments and director_script is None and not sys.stdin.isatty():
        raise SystemExit("--review-segments needs an interactive terminal")
    log_path = project_root / "agent_interaction.log"
    _append(log_path, f"\n\n# FULL FLOW START {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Stage 4: load user-defined skills (global + per-project) so they flow into
    # the segment menu / planner catalog. Atomic + metadata-only; a bad file is
    # logged and ignored, never half-loaded.
    from core import skills as _skills
    _skills.clear_user_skills()
    for _sk_path in (TOOL_ROOT / "user_skills.json", project_root / "user_skills.json"):
        for _err in _skills.load_user_skills(_sk_path):
            _append(log_path, f"# USER SKILL WARN ({_sk_path.name}): {_err}\n")

    records: list[dict] = []
    started_at = time.time()
    session = Session(project_root, gate_profile=gate_profile)
    run_provider = provider or session.state.provider
    run_meta = _build_run_metadata(
        project_root=project_root,
        provider=run_provider,
        max_cycles_per_segment=max_cycles_per_segment,
        max_attempts_per_cycle=max_attempts_per_cycle,
        use_planning_pass=use_planning_pass,
        parallel_candidates=parallel_candidates,
        review_segments=review_segments,
        max_api_exceptions_per_segment=max_api_exceptions_per_segment,
    )
    _write_partial_result(project_root, records, session, started_at, provider=run_provider, run_meta=run_meta)

    # 被 SIGINT/SIGTERM 杀掉的 run 不能永远停留在 status="running"：
    # 先落盘 aborted 再退出，事后才能区分"中止"与"进行中/卡死"。
    def _abort_on_signal(signum, _frame):
        try:
            current = Session(project_root)
        except Exception:
            current = session
        _write_partial_result(
            project_root, records, current, started_at, provider=run_provider,
            last_failure_category="aborted", last_exception=f"signal {signum}",
            run_meta=run_meta, status="aborted",
        )
        raise SystemExit(128 + signum)

    prev_handlers = {}
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGINT, signal.SIGTERM):
            prev_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, _abort_on_signal)

    try:
        return _run_full_flow_body(
            project_root, records, session, started_at, log_path,
            run_provider, run_meta,
            max_cycles_per_segment, max_attempts_per_cycle,
            use_planning_pass, parallel_candidates, review_segments,
            retry_sleep_s, max_api_exceptions_per_segment,
            gate_profile, director_script,
        )
    finally:
        for sig, handler in prev_handlers.items():
            signal.signal(sig, handler)


def _run_full_flow_body(
    project_root: Path,
    records: list,
    session: Session,
    started_at: float,
    log_path: Path,
    run_provider: str,
    run_meta: dict,
    max_cycles_per_segment: int,
    max_attempts_per_cycle: int,
    use_planning_pass: bool,
    parallel_candidates: int,
    review_segments: bool,
    retry_sleep_s: int,
    max_api_exceptions_per_segment: int,
    gate_profile: str = "full",
    director_script: dict | None = None,
) -> dict:
    while True:
        session = Session(project_root, gate_profile=gate_profile)
        seg = session.state.current_segment
        if seg is None:
            break
        if director_script:
            _apply_scripted_intent(director_script, session, seg, log_path)

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

        # LAND: auto-generate, skip LLM entirely
        if str(seg.id).upper() == "LAND":
            _append(log_path, f"\n# {seg.id} AUTO-LAND\n")
            land_ok = _auto_land(session, segment_record, log_path)
            _write_partial_result(
                project_root, records, session, started_at,
                provider=run_provider, run_meta=run_meta,
                last_failure_category=None if land_ok else segment_record.get("failure_category"),
                last_exception=None,
            )
            if land_ok:
                continue
            else:
                break

        feedback = _segment_feedback(seg.id, session.state.drone_count)
        _append(
            log_path,
            (
                f"\n# SEGMENT {seg.id} {seg.start_time}-{seg.end_time}s\n"
                f"# FEEDBACK\n{feedback}\n"
            ),
        )
        _write_partial_result(project_root, records, session, started_at, provider=run_provider, run_meta=run_meta)

        locked = False
        for cycle in range(1, max_cycles_per_segment + 1):
            _append(log_path, f"\n# {seg.id} CYCLE {cycle} START\n")
            _write_partial_result(project_root, records, session, started_at, provider=run_provider, run_meta=run_meta)
            stream = _StreamLog(
                log_path, seg.id, cycle,
                on_activity=lambda s=session: _write_partial_result(
                    project_root, records, s, started_at,
                    provider=run_provider, run_meta=run_meta,
                ),
            )
            try:
                rounds = session.generate_until_safe_with_llm(
                    provider=run_provider,
                    feedback=feedback,
                    max_attempts=max_attempts_per_cycle,
                    use_planning_pass=use_planning_pass,
                    parallel_candidates=parallel_candidates,
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
                    run_meta=run_meta,
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
            _write_partial_result(project_root, records, session, started_at, provider=run_provider, run_meta=run_meta)
            _append(
                log_path,
                f"\n# {seg.id} CYCLE {cycle} SUMMARY\n"
                + json.dumps(cycle_record, ensure_ascii=False, indent=2)
                + "\n",
            )

            if rounds and rounds[-1].validation and rounds[-1].validation.passed:
                if review_segments:
                    if director_script is not None:
                        human = _scripted_review(director_script, seg, log_path)
                    else:
                        human = _segment_review_prompt(seg, rounds[-1].validation)
                    if human == "__quit__":
                        _append(log_path, f"\n# STOP human aborted at {seg.id}\n")
                        raise SystemExit("segment review aborted by human")
                    if human:
                        from core.design_memory import record as _dm_record

                        _dm_record(project_root, "segment_feedback", human, context=seg.id)
                        _append(log_path, f"\n# {seg.id} HUMAN FEEDBACK\n{human}\n")
                        feedback = (
                            _segment_feedback(seg.id, session.state.drone_count)
                            + "\n\n## 导演反馈（权威，必须满足）\n" + human
                        )
                        continue  # 重做本段（消耗一个 cycle）
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
                    run_meta=run_meta,
                )
                if approval.locked:
                    segment_record["locked"] = True
                    segment_record["final_validation"] = lock_summary["validation"]
                    locked = True
                    _write_partial_result(project_root, records, session, started_at, provider=run_provider, run_meta=run_meta)
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

    session = Session(project_root, gate_profile=gate_profile)
    completed = session.state.current_segment is None
    convergence = _convergence_summary(records, completed)
    attempt_counts = _attempt_counts(records)
    summary = {
        "project": str(project_root),
        "provider": run_provider,
        "completed": completed,
        "converged": convergence["converged"],
        "locked_segment_ids": session.state.locked_segment_ids,
        "elapsed_s": round(time.time() - started_at, 1),
        "failed_segment": None if completed else session.state.current_segment.id,
        "run": _run_status(run_meta, "completed" if completed else "failed", started_at),
        "attempt_counts": attempt_counts,
        "convergence": convergence,
        "token_usage": _token_usage_summary(records),
        "records": records,
    }
    if review_segments:
        if director_script is not None:
            verdict = str(director_script.get("session_verdict") or "").strip()
        else:
            verdict = input(
                f"\nSession 验收（locked: {summary['locked_segment_ids']}）"
                "[回车=通过 / 文本=评语（'否'开头=否决）]: "
            ).strip()
        summary["human_verdict"] = verdict or "approved"
        if verdict:
            from core.design_memory import record as _dm_record

            _dm_record(project_root, "session_verdict", verdict)
    result = {"summary": summary}
    _write_json_atomic(project_root / "stability_result.json", result)
    _write_state_last_run(project_root, session, summary["run"], attempt_counts, convergence)
    _append(
        log_path,
        "\n# FULL FLOW RESULT\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
    )
    return result


def _auto_land(session: Session, segment_record: dict, log_path: Path) -> bool:
    """Write fixed LAND code, validate, and lock. No LLM needed."""
    from core.script_editor import replace_active_segment, lock_segment

    seg = session.state.current_segment
    if seg is None:
        return False

    land_code = (
        "    auto_init(drones)\n"
        "    # role: landing\n"
        "    # motifs: fade-out\n"
        "    # beat: N/A\n"
        "    # formation: hold entry positions\n"
        "    # lighting: brief white flash before landing\n"
        "    prev = [(d.x, d.y, d.z) for d in drones]\n"
        "    flash_group(drones, '#ffffff', times=2, on_ms=300, off_ms=200)\n"
        "    for d in drones:\n"
        "        d.land()\n"
    )

    script_path = session.project_root / "scripts" / "design.py"
    if not replace_active_segment(script_path, seg.id, land_code, session.state.locked_segment_ids):
        _append(log_path, "# AUTO-LAND: replace_active_segment failed\n")
        segment_record["failure_category"] = "land_protocol"
        return False

    result = session.validate()
    _append(log_path, f"# AUTO-LAND: passed={result.passed} minD={result.min_distance_cm}\n")

    segment_record["cycles"].append({
        "cycle": 1,
        "rounds": [{"round": 1, "auto_land": True,
                     "validation": _validation_summary(result)}],
    })

    if not result.passed:
        _append(log_path, f"# AUTO-LAND: validation failed: {result.error_message}\n")
        segment_record["locked"] = False
        segment_record["failure_category"] = "land_protocol"
        return False

    approval = session.approve_and_lock()
    segment_record["locked"] = approval.locked
    if approval.locked:
        _append(log_path, "# AUTO-LAND: locked\n")
        return True
    _append(log_path, f"# AUTO-LAND: lock failed: {approval.reason}\n")
    segment_record["failure_category"] = "lock_failed"
    return False


class _StreamLog:
    def __init__(self, log_path: Path, segment_id: str, cycle: int,
                 on_activity=None):
        self.log_path = log_path
        self.segment_id = segment_id
        self.cycle = cycle
        self._reasoning_open = False
        self._content_open = False
        self._last_heartbeat = 0.0
        self._on_activity = on_activity
        self._last_activity_write = time.monotonic()

    def _notify_activity(self) -> None:
        # 长轮期间 stability_result 的 updated_at 也要跳，否则从文件上
        # 无法区分"卡死"和"正常长流"。60s 节流，写失败不打断流。
        if self._on_activity is None:
            return
        now = time.monotonic()
        if now - self._last_activity_write >= 60:
            self._last_activity_write = now
            try:
                self._on_activity()
            except Exception:
                pass

    def round_start(self, index: int) -> None:
        _append(self.log_path, f"\n# {self.segment_id} CYCLE {self.cycle} ROUND {index} START\n")

    def reasoning_delta(self, text: str) -> None:
        if not self._reasoning_open:
            _append(self.log_path, f"\n# {self.segment_id} CYCLE {self.cycle} REASONING\n")
            self._reasoning_open = True
        _append(self.log_path, text)
        self._notify_activity()

    def delta(self, text: str) -> None:
        if not self._content_open:
            _append(self.log_path, f"\n# {self.segment_id} CYCLE {self.cycle} CONTENT\n")
            self._content_open = True
        _append(self.log_path, text)
        self._notify_activity()

    def heartbeat(self) -> None:
        now = time.monotonic()
        if now - self._last_heartbeat >= 15:
            _append(self.log_path, f"\n# {self.segment_id} CYCLE {self.cycle} HEARTBEAT\n")
            self._last_heartbeat = now
        self._notify_activity()


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


def _build_run_metadata(
    project_root: Path,
    provider: str,
    max_cycles_per_segment: int,
    max_attempts_per_cycle: int,
    use_planning_pass: bool,
    parallel_candidates: int,
    review_segments: bool,
    max_api_exceptions_per_segment: int,
) -> dict:
    now = time.time()
    return {
        "run_id": f"{time.strftime('%Y%m%d_%H%M%S', time.localtime(now))}_{uuid.uuid4().hex[:8]}",
        "started_at": _iso_ts(now),
        "project": str(project_root),
        "provider": provider,
        "git_head": _git_head(),
        "max_cycles_per_segment": int(max_cycles_per_segment),
        "max_attempts_per_cycle": int(max_attempts_per_cycle),
        "convergence_round_limit": CONVERGENCE_ROUND_LIMIT,
        "use_planning_pass": bool(use_planning_pass),
        "parallel_candidates": int(parallel_candidates),
        "review_segments": bool(review_segments),
        "max_api_exceptions_per_segment": int(max_api_exceptions_per_segment),
    }


def _run_status(run_meta: dict | None, status: str, started_at: float) -> dict:
    now = time.time()
    payload = dict(run_meta or {})
    payload.update(
        {
            "status": status,
            "elapsed_s": round(now - started_at, 1),
            "updated_at": _iso_ts(now),
        }
    )
    return payload


def _attempt_counts(records: list[dict]) -> dict:
    cycles = 0
    validation_rounds = 0
    llm_rounds = 0
    exceptions = 0
    rounds_by_segment: dict[str, int] = {}
    cycles_by_segment: dict[str, int] = {}
    exceptions_by_segment: dict[str, int] = {}
    failure_categories: dict[str, int] = {}

    for segment_record in records:
        sid = str(segment_record.get("segment") or "?")
        seg_rounds = 0
        seg_cycles = 0
        seg_exceptions = 0
        category = segment_record.get("failure_category")
        if category:
            failure_categories[str(category)] = failure_categories.get(str(category), 0) + 1
        for cycle_record in segment_record.get("cycles", []):
            cycles += 1
            seg_cycles += 1
            if cycle_record.get("exception"):
                exceptions += 1
                seg_exceptions += 1
                category = cycle_record.get("failure_category") or "exception"
                failure_categories[str(category)] = failure_categories.get(str(category), 0) + 1
            rounds = cycle_record.get("rounds") or []
            validation_rounds += len(rounds)
            seg_rounds += len(rounds)
            for round_record in rounds:
                if (
                    round_record.get("model")
                    or round_record.get("response_chars")
                    or round_record.get("reasoning_chars")
                    or round_record.get("input_tokens") is not None
                    or round_record.get("output_tokens") is not None
                ):
                    llm_rounds += 1
        rounds_by_segment[sid] = seg_rounds
        cycles_by_segment[sid] = seg_cycles
        if seg_exceptions:
            exceptions_by_segment[sid] = seg_exceptions

    return {
        "segments_started": len(records),
        "cycles": cycles,
        "validation_rounds": validation_rounds,
        "llm_rounds": llm_rounds,
        "exceptions": exceptions,
        "rounds_by_segment": rounds_by_segment,
        "cycles_by_segment": cycles_by_segment,
        "exceptions_by_segment": exceptions_by_segment,
        "failure_categories": failure_categories,
    }


def _convergence_summary(records: list[dict], completed: bool,
                         round_limit: int = CONVERGENCE_ROUND_LIMIT) -> dict:
    rounds_by_segment = {
        str(segment_record.get("segment") or "?"): sum(
            len(cycle_record.get("rounds") or [])
            for cycle_record in segment_record.get("cycles", [])
        )
        for segment_record in records
    }
    over_limit = {
        sid: rounds
        for sid, rounds in rounds_by_segment.items()
        if rounds > int(round_limit)
    }
    locked_segments = [
        str(segment_record.get("segment"))
        for segment_record in records
        if segment_record.get("locked")
    ]
    return {
        "converged": bool(completed and not over_limit),
        "round_limit_per_segment": int(round_limit),
        "rounds_by_segment": rounds_by_segment,
        "over_limit_segments": over_limit,
        "locked_segments": locked_segments,
        "definition": "completed 且每段 validator/LLM round 数不超过 round_limit_per_segment",
    }


def _write_state_last_run(project_root: Path, session, run_status: dict,
                          attempt_counts: dict, convergence: dict) -> None:
    try:
        session.state.last_run = {
            **run_status,
            "attempt_counts": attempt_counts,
            "convergence": convergence,
        }
        session.state.save(project_root)
    except Exception:
        pass


def _git_head() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def _iso_ts(value: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(value))


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
        "window_fill_ok": _optional_bool(getattr(validation, "window_fill_ok", True)),
        "motion_quality_ok": validation.motion_quality_ok,
        "degradation_ok": validation.degradation_ok,
        "composition_ok": _optional_bool(getattr(validation, "composition_ok", True)),
        "code_quality_ok": validation.code_quality_ok,
        "expected_drone_count": _optional_int(getattr(validation, "expected_drone_count", None)),
        "actual_drone_count": _optional_int(getattr(validation, "actual_drone_count", None)),
        "errors": {
            "motion": validation.motion_envelope_errors[:3],
            "effective": validation.effective_motion_errors[:3],
            "window": _optional_list(getattr(validation, "window_fill_errors", []))[:3],
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
    if getattr(validation, "window_fill_errors", []) or getattr(validation, "window_fill_ok", True) is False:
        return "window_fill"
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
    plan_review: bool = False,
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
            plan_review=plan_review,
        )

    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _apply_music_plan(project_root: Path, state: dict, music: str, provider: str, title: str | None = None, plan_review: bool = False) -> None:
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
    review_trail = None
    if plan_review:
        from core.composition_planner import plan_review_loop

        if not sys.stdin.isatty():
            raise SystemExit("--plan-review needs an interactive terminal (stdin is not a tty)")
        result, review_trail = plan_review_loop(
            str(music_path), provider=provider,
            drone_count=int(state["drone_count"]), title=title,
            memory_root=str(project_root),
        )
    else:
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
    if review_trail is not None:
        (project_root / "plan_review.json").write_text(
            json.dumps(review_trail, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    show_end = windows.get("LAND", {}).get("end_s")
    print(f"[music plan] theme: {str(plan.get('theme'))[:60]} | show_end: {show_end}s")


def _segment_review_prompt(seg, validation, input_fn=input, print_fn=print) -> str:
    """段级评审（PLAN 12.3）：返回 '' = 锁定，文本 = 导演反馈重做，'__quit__' = 中止。"""
    print_fn(f"\n===== 段级评审 {seg.id} ({seg.start_time}-{seg.end_time}s) =====")
    print_fn(
        f"dist={validation.distance_warnings} act={validation.action_warnings} "
        f"minD={validation.min_distance_cm} dense_minD={validation.dense_min_distance_cm}"
    )
    card = (validation.composition or {}).get("design_card") or {}
    for key in ("role", "motifs", "beat", "formation", "lighting"):
        if card.get(key):
            print_fn(f"  #{key}: {card[key]}")
    answer = str(input_fn("[回车/a]=锁定  [文本]=导演反馈重做本段  [q]=中止: ")).strip()
    if answer.lower() in ("", "a", "y"):
        return ""
    if answer.lower() == "q":
        return "__quit__"
    return answer


def _apply_scripted_intent(script: dict, session: Session, seg, log_path: Path) -> None:
    """导演剧本：段成为当前段时应用其 intent（等价 REPL 的 i 命令）。"""
    entry = (script.get("segments") or {}).get(seg.id) or {}
    intent = str(entry.get("intent") or "").strip()
    if intent and seg.intent != intent:
        seg.intent = intent
        session.state.save(session.project_root)
        _append(log_path, f"\n# {seg.id} DIRECTOR INTENT\n{intent}\n")


def _scripted_review(script: dict, seg, log_path: Path) -> str:
    """导演剧本评审：按段依次弹出 feedback 队列；耗尽后返回 ''（锁定）。"""
    entry = (script.get("segments") or {}).get(seg.id)
    if not isinstance(entry, dict):
        return ""
    queue = entry.get("_queue")
    if queue is None:
        queue = [str(item) for item in (entry.get("feedback") or [])]
        entry["_queue"] = queue
    answer = queue.pop(0).strip() if queue else ""
    _append(log_path, f"\n# {seg.id} SCRIPTED REVIEW -> {answer or '(approve)'}\n")
    return answer


def _append(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)



def _write_partial_result(project_root: Path, records: list, session, started_at: float,
                          failed_segment: str | None = None,
                          provider: str | None = None,
                          last_failure_category: str | None = None,
                          last_exception: str | None = None,
                          run_meta: dict | None = None,
                          status: str = "running") -> None:
    """Write intermediate stability_result.json after each cycle."""
    try:
        attempt_counts = _attempt_counts(records)
        convergence = _convergence_summary(records, completed=False)
        run_status = _run_status(run_meta, status, started_at)
        summary = {
            "project": str(project_root),
            "provider": provider or session.state.provider,
            "completed": False,
            "converged": False,
            "current_segment": session.state.current_segment.id if session.state.current_segment else None,
            "locked_segment_ids": session.state.locked_segment_ids,
            "elapsed_s": round(time.time() - started_at, 1),
            "failed_segment": failed_segment or (session.state.current_segment.id if session.state.current_segment else None),
            "last_failure_category": last_failure_category,
            "last_exception": last_exception,
            "run": run_status,
            "attempt_counts": attempt_counts,
            "convergence": convergence,
            "token_usage": _token_usage_summary(records),
            "records": records,
        }
        _write_json_atomic(project_root / "stability_result.json", {"summary": summary})
        _write_state_last_run(project_root, session, run_status, attempt_counts, convergence)
    except Exception:
        pass


def _write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # 并行候选流式期间心跳可能从多个 worker 线程并发写，tmp 名必须含线程 id
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", help="Existing project path.")
    parser.add_argument("--fresh-name", help="Create a fresh project under agent_projects/.")
    parser.add_argument("--music", help="Music file (abs or repo-root relative); generates composition plan + segment windows from it.")
    parser.add_argument("--review-segments", action="store_true", help="HITL: pause after each gate-passing segment for approve/feedback; session verdict at the end (PLAN 12.3/12.4). Rejections consume cycles.")
    parser.add_argument("--director-script", help="JSON script of per-segment intent + feedback rounds; drives the review loop non-interactively with gate_profile=safety (real-API director acceptance).")
    parser.add_argument("--plan-review", action="store_true", help="HITL: review the generated plan interactively; reject with director notes to regenerate (PLAN 12.1).")
    parser.add_argument("--music-title", help="Human-provided track title/character hint (e.g. 春节序曲); overrides audio-feature mood inference.")
    parser.add_argument("--provider", help="Provider name from ai_providers.local.json.")
    parser.add_argument("--mode", choices=["manual", "fast"], default="manual")
    parser.add_argument("--drone-count", type=int, default=7)
    parser.add_argument("--max-cycles-per-segment", type=int, default=DEFAULT_MAX_CYCLES_PER_SEGMENT)
    parser.add_argument("--max-attempts-per-cycle", type=int, default=DEFAULT_MAX_ATTEMPTS_PER_CYCLE)
    parser.add_argument("--no-planning-pass", action="store_true")
    parser.add_argument("--parallel-candidates", type=int, default=2, help="K parallel candidate generations per repair round (1=serial); hedges slow/dead streams and halves repair wall-time.")
    parser.add_argument("--retry-sleep-s", type=int, default=30)
    parser.add_argument("--max-api-exceptions-per-segment", type=int, default=5)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
