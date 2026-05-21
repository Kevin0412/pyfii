"""Checkpoint — 自动备份 design.py"""
from pathlib import Path
import shutil
from datetime import datetime


def save(project_root: Path) -> Path:
    """备份 design.py 到 checkpoints/"""
    src = project_root / "scripts" / "design.py"
    if not src.exists():
        return None

    checkpoint_dir = project_root / "checkpoints"
    checkpoint_dir.mkdir(exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = checkpoint_dir / f"design_{ts}.py"
    shutil.copy2(src, dst)
    return dst


def restore(project_root: Path, checkpoint_name: str) -> bool:
    """从 checkpoint 恢复 design.py"""
    src = project_root / "checkpoints" / checkpoint_name
    dst = project_root / "scripts" / "design.py"
    if not src.exists():
        return False
    shutil.copy2(src, dst)
    return True


def list_checkpoints(project_root: Path) -> list[str]:
    """列出所有 checkpoint 文件名"""
    cdir = project_root / "checkpoints"
    if not cdir.exists():
        return []
    return sorted([p.name for p in cdir.glob("design_*.py")])
