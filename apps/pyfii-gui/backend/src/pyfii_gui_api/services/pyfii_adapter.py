from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional
import contextlib
import io
import warnings


@dataclass
class ParsedFiiProject:
    data: Any
    t0: Any
    music: Any
    field: Optional[int]
    device: Optional[str]
    warnings: List[str]
    stdout: str


def _warning_messages(captured: List[warnings.WarningMessage]) -> List[str]:
    return [str(item.message) for item in captured]


def parse_fii_project(project_dir: Path, fps: int, ignore_acc: bool) -> ParsedFiiProject:
    # Import direct modules; avoid pyfii package-level imports that pull in unrelated GUI paths.
    from pyfii.read import read_fii
    from pyfii.show import show as validate_show
    from pyfii_gui_api.config import settings

    stdout = io.StringIO()
    warning_messages: List[str] = []

    with warnings.catch_warnings(record=True) as read_warnings:
        warnings.simplefilter("always")
        with contextlib.redirect_stdout(stdout):
            data, t0, music, field, device = read_fii(
                str(project_dir),
                fps=fps,
                ignore_acc=ignore_acc,
                workers=settings.trajectory_workers,
            )
    warning_messages.extend(_warning_messages(read_warnings))

    # show(show=False) is the current core path that performs distance warnings without rendering.
    with warnings.catch_warnings(record=True) as show_warnings:
        warnings.simplefilter("always")
        with contextlib.redirect_stdout(stdout):
            validate_show(
                data,
                t0,
                music,
                field=field,
                device=device,
                show=False,
                save="",
                FPS=fps,
                max_fps=fps,
                ThreeD=False,
            )
    warning_messages.extend(_warning_messages(show_warnings))

    return ParsedFiiProject(
        data=data,
        t0=t0,
        music=music,
        field=field,
        device=device,
        warnings=warning_messages,
        stdout=stdout.getvalue(),
    )
