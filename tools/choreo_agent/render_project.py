"""Render 2D/3D videos for a choreo-agent project.

Usage:
    python tools/choreo_agent/render_project.py <project_dir>

Outputs are written to ``<project_dir>/videos/``. Agent project directories are
normally gitignored, so the generated videos are not tracked.
"""

import argparse
import json
import sys
from pathlib import Path


def find_repo_root(p):
    p = Path(p).resolve()
    for q in [p, *p.parents]:
        if (q / "src" / "pyfii").exists():
            return q
    return p


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path, help="Choreo-agent project directory")
    parser.add_argument("--fps", type=int, default=60, help="Read/render FPS, default: 60")
    parser.add_argument("--skip-2d", action="store_true", help="Do not render the 2D video")
    parser.add_argument("--skip-3d", action="store_true", help="Do not render the 3D video")
    parser.add_argument(
        "--imshow",
        nargs=2,
        type=float,
        default=(90, 3),
        metavar=("AZIMUTH", "ELEVATION"),
        help="3D view angle passed to pyfii.show, default: 90 3",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    project_root = args.project_dir.resolve()
    state_path = project_root / "state.json"
    output_dir = project_root / "output"
    if not state_path.exists():
        raise SystemExit(f"state.json not found: {state_path}")
    if not output_dir.exists():
        raise SystemExit(f"output directory not found: {output_dir}")

    repo_root = find_repo_root(project_root / "scripts")
    sys.path.insert(0, str(repo_root / "src"))
    import pyfii as pf  # noqa: PLC0415

    state = json.loads(state_path.read_text(encoding="utf-8"))
    music_path = state.get("music_path")
    music = str((project_root / music_path).resolve()) if music_path else ""
    music_list = [music] if music else []
    data, t0, *_ = pf.read_fii(str(output_dir), fps=args.fps, ignore_acc=False)

    video_dir = project_root / "videos"
    video_dir.mkdir(exist_ok=True)
    name = project_root.name

    if not args.skip_2d:
        base2d = str(video_dir / f"{name}_2D")
        print(f"[{name}] RENDER 2D ...", flush=True)
        pf.show(data, t0, music_list, save=base2d, FPS=args.fps, max_fps=args.fps, show=False)

    if not args.skip_3d:
        base3d = str(video_dir / f"{name}_3D")
        print(f"[{name}] RENDER 3D (imshow={list(args.imshow)}) ...", flush=True)
        pf.show(
            data,
            t0,
            music_list,
            save=base3d,
            ThreeD=True,
            imshow=list(args.imshow),
            d=(600, 500),
            FPS=args.fps,
            max_fps=args.fps,
            show=False,
        )

    print(f"[{name}] RENDER DONE", flush=True)


if __name__ == "__main__":
    main()
