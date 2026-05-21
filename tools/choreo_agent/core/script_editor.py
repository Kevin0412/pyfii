"""Marker-based design.py editor. 只允许修改当前未锁定段。"""
import hashlib
from pathlib import Path
from dataclasses import dataclass

MARKER_START = "# === PYFII_AGENT_SEGMENT_START"
MARKER_END = "# === PYFII_AGENT_SEGMENT_END"


@dataclass
class SegmentBlock:
    segment_id: str
    locked: bool
    start_line: int
    end_line: int
    content: str


def parse_markers(script_path: Path) -> list[SegmentBlock]:
    """解析 design.py 中所有段 marker"""
    lines = script_path.read_text(encoding="utf-8").splitlines()
    blocks = []
    current_id = None
    current_locked = False
    current_start = 0

    for i, line in enumerate(lines):
        if line.startswith(MARKER_START):
            current_id = _extract(line, "id")
            current_locked = "locked=true" in line
            current_start = i + 1
        elif line.startswith(MARKER_END) and current_id:
            blocks.append(SegmentBlock(
                segment_id=current_id,
                locked=current_locked,
                start_line=current_start,
                end_line=i,
                content="\n".join(lines[current_start:i]),
            ))
            current_id = None

    return blocks


def replace_active_segment(
    script_path: Path,
    segment_id: str,
    new_code: str,
    locked_segment_ids: list[str],
) -> bool:
    """
    替换当前段代码。如果任何 locked 段被修改则拒绝。
    返回 True 表示成功。
    """
    lines = script_path.read_text(encoding="utf-8").splitlines()

    # 确认目标段存在且未锁定
    target_start = None
    target_end = None
    for i, line in enumerate(lines):
        if line.startswith(MARKER_START) and _extract(line, "id") == segment_id:
            if segment_id in locked_segment_ids:
                return False
            target_start = i
        if target_start and line.startswith(MARKER_END) and i > target_start:
            target_end = i
            break

    if target_start is None or target_end is None:
        return False

    # 保存 locked 段 hash
    locked_hashes = _hash_locked_segments(lines, locked_segment_ids)

    # 替换
    new_lines = (
        lines[:target_start + 1]
        + new_code.splitlines()
        + lines[target_end:]
    )

    # 检查 locked 段是否被改动
    new_hashes = _hash_locked_segments(new_lines, locked_segment_ids)
    if locked_hashes != new_hashes:
        return False

    # 原子写入
    tmp = script_path.with_suffix(".tmp")
    tmp.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    tmp.replace(script_path)
    return True


def lock_segment(script_path: Path, segment_id: str) -> bool:
    """将段标记为 locked=true"""
    content = script_path.read_text(encoding="utf-8")
    old = f"{MARKER_START} {segment_id} locked=false"
    new = f"{MARKER_START} {segment_id} locked=true"
    if old in content:
        content = content.replace(old, new)
        tmp = script_path.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(script_path)
        return True
    return False


def _hash_locked_segments(lines: list[str], locked_ids: list[str]) -> dict[str, str]:
    hashes = {}
    in_segment = None
    in_locked = False
    buf = []

    for line in lines:
        if line.startswith(MARKER_START):
            in_segment = _extract(line, "id")
            in_locked = "locked=true" in line
            buf = []
        elif line.startswith(MARKER_END) and in_segment:
            if in_locked and in_segment in locked_ids:
                hashes[in_segment] = hashlib.sha256(
                    "\n".join(buf).encode()
                ).hexdigest()
            in_segment = None
            in_locked = False
        elif in_segment:
            buf.append(line)

    return hashes


def _extract(line: str, key: str) -> str | None:
    """从 marker 行提取 key=value"""
    for part in line.split():
        if part.startswith(f"{key}="):
            return part.split("=")[1]
    return None
