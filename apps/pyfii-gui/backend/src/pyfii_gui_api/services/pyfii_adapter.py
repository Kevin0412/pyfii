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


def parse_fii_project(project_dir: Path, fps: int, ignore_acc: bool) -> ParsedFiiProject:
    # Import directly from pyfii.read so the backend never touches pyfii.show GUI/video deps.
    from pyfii.read import read_fii

    stdout = io.StringIO()
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        with contextlib.redirect_stdout(stdout):
            data, t0, music, field, device = read_fii(
                str(project_dir),
                fps=fps,
                ignore_acc=ignore_acc,
            )

    return ParsedFiiProject(
        data=data,
        t0=t0,
        music=music,
        field=field,
        device=device,
        warnings=[str(item.message) for item in captured],
        stdout=stdout.getvalue(),
    )
