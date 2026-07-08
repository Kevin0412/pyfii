"""项目导出——把 agent_projects/<name> 打包成 zip，供 REPL/TUI/oneshot 复用。"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

# checkpoints/ 是纯备份历史，单个项目可能积累几千个文件（真实项目里见过 5881 个），
# 默认排除；需要的话调用方可显式 include_checkpoints=True。
_EXCLUDED_DIR_NAMES = {"checkpoints", "__pycache__", ".pytest_cache"}


def build_project_archive(project_root: Path, *, include_checkpoints: bool = False) -> bytes:
    """把 project_root 打包为 zip 字节串（内存中构建，不落盘临时文件）。"""
    project_root = Path(project_root)
    excluded = set(_EXCLUDED_DIR_NAMES)
    if include_checkpoints:
        excluded.discard("checkpoints")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(project_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(project_root)
            if excluded.intersection(rel.parts):
                continue
            zf.write(path, arcname=str(rel))
    return buf.getvalue()
