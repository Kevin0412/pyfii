#!/usr/bin/env python3
"""Pyfii Choreo Agent — 一次性/脚本化 CLI。

跟 main.py 的常驻 REPL 和 tui/app.py 的常驻 Textual 界面不同：这里每次调用只
构造一个 Session、执行一个动作、退出，进程不保留任何状态——适合 shell 脚本里
串起来跑，或者只想快速看一眼某个项目状态。取代了旧的根目录 tui.py 原型（硬编码
单一项目路径+provider，用 subprocess -c 跑内联脚本，命令之间会丢内存状态，
check=False 还会吞掉失败）。

用法:
    python tools/choreo_agent/oneshot.py status agent_projects/<name>
    python tools/choreo_agent/oneshot.py validate agent_projects/<name>
    python tools/choreo_agent/oneshot.py generate agent_projects/<name> [--feedback TEXT] [--max-attempts N]
    python tools/choreo_agent/oneshot.py lock agent_projects/<name> [--reason TEXT]
    python tools/choreo_agent/oneshot.py sync agent_projects/<name>
    python tools/choreo_agent/oneshot.py handoff agent_projects/<name>
    python tools/choreo_agent/oneshot.py ckpt agent_projects/<name> save
    python tools/choreo_agent/oneshot.py ckpt agent_projects/<name> list
    python tools/choreo_agent/oneshot.py ckpt agent_projects/<name> restore <checkpoint_name>
    python tools/choreo_agent/oneshot.py export agent_projects/<name> [path]

每个子命令的退出码反映动作是否成功（0=成功/通过，1=失败/未通过），方便串进
shell 脚本判断。
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_ROOT))

from core import Session
from core.design_memory import record as design_memory_record
from core.export import build_project_archive
from main import (
    _resolve_project_path,
    _StreamPrinter,
    print_round_report,
    print_validation_report,
)


def _open_session(project_arg: str) -> Session:
    proj = _resolve_project_path(project_arg)
    if not (proj / "state.json").exists():
        raise SystemExit(f"No state.json in {proj}. Run main.py init first.")
    # 跟 main.py/tui/app.py 一样默认交互导演模式：审美门降为建议，物理安全/
    # 演出完整性门保持硬——oneshot 是给人用的快速动作，不是无人值守流水线。
    return Session(proj, gate_profile="safety")


def cmd_status(args: argparse.Namespace) -> int:
    session = _open_session(args.project)
    seg = session.state.current_segment
    print(f"Project: {session.state.name}")
    print(f"Music: {session.state.music_path} ({session.state.music_duration}s)")
    print(f"Mode: {session.state.mode}")
    print(f"Provider: {session.state.provider}")
    print(f"Gate profile: {session.gate_profile}")
    print(f"Drones: {session.state.drone_count}")
    print(f"Locked: {session.state.locked_segment_ids}")
    if seg:
        print(f"Current: {seg.id} ({seg.start_time}-{seg.end_time}s) [{'locked' if seg.locked else 'unlocked'}]")
        print(f"Intent: {seg.intent or '(empty)'}")
    else:
        print("Current: none (all segments done)")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    session = _open_session(args.project)
    result = session.validate()
    print_validation_report(result)
    return 0 if result.passed else 1


def cmd_generate(args: argparse.Namespace) -> int:
    session = _open_session(args.project)
    seg = session.state.current_segment
    if seg is None:
        print("No current segment.")
        return 1
    provider = session.state.provider
    feedback = args.feedback or ""
    if feedback:
        design_memory_record(session.project_root, "segment_feedback", feedback, context=seg.id)
        session._human_preferences = None
    print(f"Generating {seg.id} with {provider}; max_attempts={args.max_attempts}.")
    stream = _StreamPrinter()
    try:
        rounds = session.generate_until_safe_with_llm(
            provider=provider,
            feedback=feedback,
            max_attempts=args.max_attempts,
            use_planning_pass=True,
            on_delta=stream.delta,
            on_reasoning_delta=stream.reasoning_delta,
            on_heartbeat=stream.heartbeat,
            on_round_start=stream.begin_round,
        )
        stream.finish()
    except Exception as e:  # noqa: BLE001
        stream.finish()
        print(f"Generate failed: {e}")
        return 1
    if not rounds or rounds[-1].response is None:
        print("Generate failed. Segment locked or empty response.")
        return 1
    for round_result in rounds:
        print_round_report(round_result)
    validation = rounds[-1].validation
    return 0 if (validation and validation.passed) else 1


def cmd_lock(args: argparse.Namespace) -> int:
    session = _open_session(args.project)
    seg = session.state.current_segment
    if seg is None:
        print("No current segment.")
        return 1
    approval = session.approve_and_lock(allow_human_override=True)
    if approval.locked:
        if args.reason:
            design_memory_record(
                session.project_root, "segment_feedback",
                f"[导演 override 锁定] {args.reason}", context=seg.id,
            )
        print(f"Locked {session.state.locked_segment_ids[-1]}")
        if approval.human_override:
            print("Human override: validation did not pass, but manual approval locked the segment.")
        return 0
    print(f"Lock failed — {approval.reason or 'segment missing or marker lock failed.'}")
    return 1


def cmd_sync(args: argparse.Namespace) -> int:
    session = _open_session(args.project)
    session.sync_state_with_markers(save=True)
    print("Synced state from design.py markers.")
    return 0


def cmd_handoff(args: argparse.Namespace) -> int:
    session = _open_session(args.project)
    print(session.handoff())
    return 0


def cmd_ckpt(args: argparse.Namespace) -> int:
    session = _open_session(args.project)
    if args.action == "save":
        path = session.checkpoint_save()
        if path:
            print(f"Checkpoint saved: {path.name}")
            return 0
        print("Nothing to checkpoint yet (no design.py).")
        return 1
    if args.action == "list":
        names = session.checkpoint_list()
        shown = names[-10:]
        start = len(names) - len(shown) + 1
        for i, name in enumerate(shown, start=start):
            print(f"  [{i}] {name}")
        if len(names) > len(shown):
            print(f"  ... ({len(names) - len(shown)} older checkpoints not shown)")
        if not names:
            print("No checkpoints yet.")
        return 0
    # action == "restore"
    if not args.name:
        print("Usage: oneshot.py ckpt <project> restore <checkpoint_name>")
        return 1
    ok = session.checkpoint_restore(args.name)
    print("Restored and re-synced state from markers." if ok else f"Checkpoint '{args.name}' not found.")
    return 0 if ok else 1


def cmd_export(args: argparse.Namespace) -> int:
    session = _open_session(args.project)
    data = build_project_archive(session.project_root)
    if args.path:
        out_path = Path(args.path).expanduser()
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = session.project_root.parent / f"{session.project_root.name}_{ts}.zip"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    print(f"Exported to {out_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status", help="print project/segment status")
    p.add_argument("project")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("validate", help="validate the current segment")
    p.add_argument("project")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("generate", help="generate+repair the current segment")
    p.add_argument("project")
    p.add_argument("--feedback", default="")
    p.add_argument("--max-attempts", type=int, default=5)
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("lock", help="approve+lock the current segment")
    p.add_argument("project")
    p.add_argument("--reason", default="")
    p.set_defaults(func=cmd_lock)

    p = sub.add_parser("sync", help="re-sync state from design.py markers")
    p.add_argument("project")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("handoff", help="print a handoff summary")
    p.add_argument("project")
    p.set_defaults(func=cmd_handoff)

    p = sub.add_parser("ckpt", help="checkpoint save/list/restore")
    p.add_argument("project")
    p.add_argument("action", choices=("save", "list", "restore"))
    p.add_argument("name", nargs="?", default=None)
    p.set_defaults(func=cmd_ckpt)

    p = sub.add_parser("export", help="export the project as a zip")
    p.add_argument("project")
    p.add_argument("path", nargs="?", default=None)
    p.set_defaults(func=cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
