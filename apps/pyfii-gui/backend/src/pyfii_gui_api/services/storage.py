from dataclasses import dataclass
from pathlib import Path
import shutil

from ..config import settings


@dataclass
class ProjectWorkspace:
    root: Path
    upload_dir: Path
    extract_dir: Path


def project_root(project_id: str) -> Path:
    return settings.runtime_dir / project_id


def video_export_root(project_id: str) -> Path:
    return settings.runtime_dir / "_video_exports" / project_id


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
