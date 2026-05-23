#!/usr/bin/env python3
"""Batch smoke test the documented human choreography pool through GUI import services."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_SRC = REPO_ROOT / "apps" / "pyfii-gui" / "backend" / "src"
CORE_SRC = REPO_ROOT / "src"
for path in (BACKEND_SRC, CORE_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


POOL_ITEM_RE = re.compile(r"`(output/[^`]+)`")
ZIP_EXCLUDES = (
    "./.agents/*",
    "./.codex/*",
    "./__pycache__/*",
    "./gui.png",
    "./*.mp4",
    "./*.avi",
    "./*.mov",
    "./*.mkv",
    "*.mp4",
    "*.avi",
    "*.mov",
    "*.mkv",
)
KNOWN_INCOMPATIBLE_PROJECTS = {
    "output/d/比赛用无人机": "old Fii project format; current pyfii core parser is not expected to import it",
}


def extract_human_pool(doc_path: Path) -> list[Path]:
    lines = doc_path.read_text(encoding="utf-8").splitlines()
    in_pool = False
    projects: list[Path] = []

    for line in lines:
        if line.strip() == "## 人类作品经验池":
            in_pool = True
            continue
        if not in_pool:
            continue
        if projects and not line.strip().startswith("-"):
            break
        match = POOL_ITEM_RE.search(line)
        if match:
            projects.append(REPO_ROOT / match.group(1))

    return projects


def create_clean_zip(project_dir: Path, zip_path: Path) -> None:
    try:
        subprocess.run(
            ["zip", "-rq", str(zip_path), ".", "-x", *ZIP_EXCLUDES],
            cwd=project_dir,
            check=True,
        )
        return
    except FileNotFoundError:
        pass

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in project_dir.rglob("*"):
            if path.is_dir():
                continue
            relative = path.relative_to(project_dir)
            parts = set(relative.parts)
            if ".agents" in parts or ".codex" in parts or "__pycache__" in parts:
                continue
            if relative.name == "gui.png" or relative.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv"}:
                continue
            archive.write(path, relative.as_posix())


def run_import_case(project_dir: Path, fps: int, ignore_acc: bool) -> dict:
    from pyfii_gui_api.services.archive_importer import safe_extract_zip
    from pyfii_gui_api.services.pyfii_adapter import parse_fii_project
    from pyfii_gui_api.services.safety import analyze_safety
    from pyfii_gui_api.services.serializer import compute_duration_ms, compute_frame_count, serialize_tracks

    with tempfile.TemporaryDirectory(prefix="pyfii-gui-pool-") as temp_root:
        temp_dir = Path(temp_root)
        zip_path = temp_dir / "project.zip"
        extract_dir = temp_dir / "extracted"

        start = time.perf_counter()
        create_clean_zip(project_dir, zip_path)
        zip_seconds = time.perf_counter() - start

        start = time.perf_counter()
        imported_dir = safe_extract_zip(zip_path, extract_dir)
        extract_seconds = time.perf_counter() - start

        start = time.perf_counter()
        parsed = parse_fii_project(imported_dir, fps=fps, ignore_acc=ignore_acc)
        parse_seconds = time.perf_counter() - start

        duration_ms = compute_duration_ms(parsed.data)
        frame_count = compute_frame_count(parsed.data)
        safety = analyze_safety(
            parsed.data,
            warnings=parsed.warnings,
            source_fps=fps,
            field=parsed.field,
            device=parsed.device,
        )

        start = time.perf_counter()
        tracks = serialize_tracks(
            parsed.data,
            project_id="batch",
            fps=fps,
            source_fps=fps,
            duration_ms=duration_ms,
            field=parsed.field,
            device=parsed.device,
        )
        json.dumps(tracks, ensure_ascii=False)
        serialize_seconds = time.perf_counter() - start

        return {
            "ok": True,
            "ignore_acc": ignore_acc,
            "zip_bytes": zip_path.stat().st_size,
            "project_dir_after_extract": str(imported_dir),
            "field": parsed.field,
            "device": parsed.device,
            "drone_count": len(parsed.data or []),
            "duration_ms": duration_ms,
            "frame_count": frame_count,
            "warnings_count": len(parsed.warnings),
            "warnings_head": parsed.warnings[:5],
            "safety_summary": safety["summary"],
            "safety_events_count": len(safety["events"]),
            "track_count": len(tracks["drones"]),
            "first_track_samples": len(tracks["drones"][0]["samples"]) if tracks["drones"] else 0,
            "timing_seconds": {
                "zip": round(zip_seconds, 3),
                "extract": round(extract_seconds, 3),
                "parse": round(parse_seconds, 3),
                "serialize": round(serialize_seconds, 3),
            },
        }


def _worker(project_dir: str, fps: int, ignore_acc: bool, queue: mp.Queue) -> None:
    try:
        queue.put(run_import_case(Path(project_dir), fps=fps, ignore_acc=ignore_acc))
    except Exception as exc:
        queue.put(
            {
                "ok": False,
                "ignore_acc": ignore_acc,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )


def run_with_timeout(project_dir: Path, fps: int, ignore_acc: bool, timeout_seconds: int) -> dict:
    ctx = mp.get_context("fork")
    queue: mp.Queue = ctx.Queue()
    process = ctx.Process(target=_worker, args=(str(project_dir), fps, ignore_acc, queue))
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(5)
        return {
            "ok": False,
            "ignore_acc": ignore_acc,
            "error": "timeout after %ss" % timeout_seconds,
        }

    if queue.empty():
        return {
            "ok": False,
            "ignore_acc": ignore_acc,
            "error": "worker exited without a result",
            "exitcode": process.exitcode,
        }
    return queue.get()


def run_pool(projects: list[Path], fps: int, timeout_seconds: int, modes: list[bool]) -> list[dict]:
    results: list[dict] = []
    for project_dir in projects:
        source = str(project_dir.relative_to(REPO_ROOT))
        expected_failure_reason = KNOWN_INCOMPATIBLE_PROJECTS.get(source)
        project_result = {
            "source": source,
            "exists": project_dir.exists(),
            "expected_failure_reason": expected_failure_reason,
            "cases": [],
        }
        if not project_dir.exists():
            project_result["cases"].append({"ok": False, "error": "source directory does not exist"})
            results.append(project_result)
            continue

        print("==> %s" % project_result["source"], flush=True)
        for ignore_acc in modes:
            label = "ignore_acc=%s" % str(ignore_acc).lower()
            print("    %s ..." % label, end=" ", flush=True)
            case = run_with_timeout(project_dir, fps=fps, ignore_acc=ignore_acc, timeout_seconds=timeout_seconds)
            if expected_failure_reason and not case.get("ok"):
                case["expected_failure"] = True
                case["expected_failure_reason"] = expected_failure_reason
            project_result["cases"].append(case)
            if case["ok"]:
                summary = case["safety_summary"]
                print(
                    "ok drones=%s frames=%s warnings=%s safety=%s/%sE/%sW"
                    % (
                        case["drone_count"],
                        case["frame_count"],
                        case["warnings_count"],
                        summary["level"],
                        summary["error_count"],
                        summary["warning_count"],
                    ),
                    flush=True,
                )
            elif case.get("expected_failure"):
                print("XFAIL %s" % case.get("error"), flush=True)
            else:
                print("FAIL %s" % case.get("error"), flush=True)
        results.append(project_result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", type=Path, default=REPO_ROOT / "doc" / "ai_choreography_exploration.md")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--mode", choices=["both", "modern", "visual"], default="both")
    parser.add_argument("projects", nargs="*", type=Path)
    args = parser.parse_args()

    if args.projects:
        projects = [path if path.is_absolute() else REPO_ROOT / path for path in args.projects]
    else:
        projects = extract_human_pool(args.doc)

    modes = {
        "both": [False, True],
        "modern": [False],
        "visual": [True],
    }[args.mode]

    results = run_pool(projects, fps=args.fps, timeout_seconds=args.timeout, modes=modes)
    failed = [
        (result["source"], case)
        for result in results
        for case in result["cases"]
        if not case.get("ok") and not case.get("expected_failure")
    ]
    expected_failures = [
        (result["source"], case)
        for result in results
        for case in result["cases"]
        if case.get("expected_failure")
    ]

    payload = {
        "doc": str(args.doc),
        "fps": args.fps,
        "timeout_seconds": args.timeout,
        "mode": args.mode,
        "results": results,
        "failed_count": len(failed),
        "expected_failure_count": len(expected_failures),
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("wrote %s" % args.json, flush=True)

    print(
        "completed projects=%s failed_cases=%s expected_failures=%s"
        % (len(results), len(failed), len(expected_failures)),
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
