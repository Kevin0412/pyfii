"""Pyfii Choreo Agent — CLI 原型"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "choreo_agent"))

from core import Session


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/choreo_agent/main.py agent_projects/<name>")
        return

    proj = Path(sys.argv[1])
    if not proj.is_absolute():
        proj = REPO_ROOT / proj
    proj = proj.resolve()

    if not (proj / "state.json").exists():
        print(f"No state.json in {proj}. Run init first.")
        return

    session = Session(proj)
    print(f"Project: {session.state.name}")
    print(f"Music: {session.state.music_path} ({session.state.music_duration}s)")
    print(f"Mode: {session.state.mode}")
    print(f"Locked: {session.state.locked_segment_ids}")

    while True:
        seg = session.state.current_segment
        if seg:
            print(f"\nCurrent: {seg.id} ({seg.start_time}-{seg.end_time}s) "
                  f"[{'locked' if seg.locked else 'unlocked'}]")
        else:
            print("\nAll segments done.")

        cmd = input("> ").strip().lower()
        if not cmd:
            continue

        if cmd == "q":
            session.save()
            break

        elif cmd == "v":
            result = session.validate()
            print(f"compile={result.compile_ok} run={result.run_ok}")
            print(f"dist={result.distance_warnings} act={result.action_warnings}")
            print(f"minD={result.min_distance_cm}cm XY={result.xy_span}")
            if result.error_message:
                print(f"error: {result.error_message[-200:]}")

        elif cmd == "a":
            if session.approve_and_lock():
                print(f"Locked {session.state.locked_segment_ids[-1]}")
            else:
                print("Approve failed — validate first?")

        elif cmd == "g":
            code = _fake_generate()
            if session.generate_segment(code):
                print("Generated.")
            else:
                print("Generate failed — segment locked?")

        elif cmd == "h":
            print(session.handoff())

        elif cmd == "s":
            session.save()
            print("Saved.")

        else:
            print("Commands: g=generate v=validate a=approve h=handoff s=save q=quit")


def _fake_generate() -> str:
    """临时：返回占位代码，Phase 5 替换为 LLM 调用"""
    return "print('TODO: AI generated code')"


if __name__ == "__main__":
    main()
