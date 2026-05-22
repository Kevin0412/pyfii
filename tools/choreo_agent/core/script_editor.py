"""Marker-based design.py editor. 只允许修改当前未锁定段。"""
import hashlib
from pathlib import Path


MARKER_START = "# === PYFII_AGENT_SEGMENT_START"
MARKER_END = "# === PYFII_AGENT_SEGMENT_END"


def parse_markers(script_path: Path) -> list[dict]:
    """解析 design.py 中所有段 marker。返回 [{id, locked, start_line, end_line}]"""
    lines = script_path.read_text(encoding="utf-8").splitlines()
    blocks = []
    current_id = None
    current_locked = False
    current_start = 0

    for i, line in enumerate(lines):
        if line.startswith(MARKER_START):
            current_id = _extract(line, "id")
            current_locked = _extract(line, "locked") == "true"
            current_start = i + 1
        elif line.startswith(MARKER_END) and current_id:
            blocks.append({
                "id": current_id,
                "locked": current_locked,
                "start_line": current_start,
                "end_line": i,
            })
            current_id = None

    return blocks


def replace_active_segment(
    script_path: Path,
    segment_id: str,
    new_code: str,
    locked_segment_ids: list[str],
) -> bool:
    """替换当前段代码。locked 段被改动则拒绝。"""
    lines = script_path.read_text(encoding="utf-8").splitlines()

    target_start = None
    target_end = None
    for i, line in enumerate(lines):
        if line.startswith(MARKER_START) and _extract(line, "id") == segment_id:
            if segment_id in locked_segment_ids:
                return False
            target_start = i
        if target_start is not None and line.startswith(MARKER_END) and i > target_start:
            target_end = i
            break

    if target_start is None or target_end is None:
        return False

    locked_hashes = _hash_locked(lines, locked_segment_ids)

    # 过滤 agent 代码中可能含有的 marker 行
    clean_code = [l for l in new_code.splitlines()
                  if not l.strip().startswith(MARKER_START)
                  and not l.strip().startswith(MARKER_END)]

    new_lines = (
        lines[:target_start + 1]
        + clean_code
        + lines[target_end:]
    )

