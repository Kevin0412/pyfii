import argparse
import runpy
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / "src"))
sys.path.append(str(REPO_ROOT / "src" / "pyfii"))

from pyfii.extensions.nl_choreo.keyframe_workflow import emit_gpt55_burst_recompose_program


OUTPUT_DIR = REPO_ROOT / "output" / "gpt55_burst_recompose_60s"
PROJECT_NAME = "gpt55_burst_recompose_60s"
PROJECT_PATH = OUTPUT_DIR / PROJECT_NAME
GENERATED_SCRIPT = OUTPUT_DIR / f"{PROJECT_NAME}_generated.py"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--music", default="")
    parser.add_argument("--preview-fps", type=int, default=20)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_SCRIPT.write_text(
        emit_gpt55_burst_recompose_program(
            output_path=str(PROJECT_PATH),
            music_path=args.music,
            render_fps=args.preview_fps,
        ),
        encoding="utf-8",
    )
    runpy.run_path(str(GENERATED_SCRIPT), run_name="__main__")

    print("GPT-5.5 choreography generated")
    print(f"project: {PROJECT_PATH}")
    print(f"preview: {PROJECT_PATH}.mp4")
    print(f"generated script: {GENERATED_SCRIPT}")


if __name__ == "__main__":
    main()
