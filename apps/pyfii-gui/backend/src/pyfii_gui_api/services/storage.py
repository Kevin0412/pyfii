from dataclasses import dataclass
from pathlib import Path
import shutil

from ..config import settings


@dataclass
class ProjectWorkspace:
    root: Path
    upload_dir: Path
    extract_dir: Path


def _runtime_child(root: Path, name: str) -> Path:
    """Return a direct child of a runtime directory, never an escaped path."""

    resolved_root = root.resolve()
    child = (resolved_root / name).resolve()
    if child.parent != resolved_root:
        raise ValueError("Runtime path must be a direct child of its configured root.")
    return child


def project_root(project_id: str) -> Path:
    return _runtime_child(settings.runtime_dir, project_id)


def video_export_root(project_id: str) -> Path:
    return _runtime_child(settings.runtime_dir / "_video_exports", project_id)


def create_project_workspace(project_id: str) -> ProjectWorkspace:
    root = project_root(project_id)
    upload_dir = root / "upload"
    extract_dir = root / "extracted"
    upload_dir.mkdir(parents=True, exist_ok=False)
    extract_dir.mkdir(parents=True, exist_ok=False)
    return ProjectWorkspace(root=root, upload_dir=upload_dir, extract_dir=extract_dir)


def cleanup_project(project_id: str) -> None:
    root = project_root(project_id)
    if root.exists():
        shutil.rmtree(root)
    export_root = video_export_root(project_id)
    if export_root.exists():
        shutil.rmtree(export_root)
