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

    new_hashes = _hash_locked(new_lines, locked_segment_ids)
    if locked_hashes != new_hashes:
        return False

    tmp = script_path.with_suffix(".tmp")
    tmp.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    tmp.replace(script_path)
    return True


def lock_segment(script_path: Path, segment_id: str) -> bool:
    """将段标记为 locked=true"""
    content = script_path.read_text(encoding="utf-8")
    old = f"{MARKER_START} id={segment_id} locked=false"
    new = f"{MARKER_START} id={segment_id} locked=true"
    if old in content:
        content = content.replace(old, new)
        tmp = script_path.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(script_path)
        return True
    return False


def _hash_locked(lines: list[str], locked_ids: list[str]) -> dict[str, str]:
    hashes = {}
    in_segment = None
    in_locked = False
    buf = []
    for line in lines:
        if line.startswith(MARKER_START):
            in_segment = _extract(line, "id")
            in_locked = _extract(line, "locked") == "true"
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
    for part in line.split():
        if part.startswith(f"{key}="):
            return part.split("=", 1)[1]
    return None


def _auto_fix_perms(code_lines, prev_lines):
    """检测恒等映射 perm=(0,1,...,6)，尝试从 prev 和 geo 推断更好排列"""
    import re
    fixed = list(code_lines)
    
    # 找 perm = (0, 1, 2, 3, 4, 5, 6) 模式
    ident_pattern = re.compile(r'perm\s*=\s*\(\s*0\s*,\s*1\s*,\s*2\s*,\s*3\s*,\s*4\s*,\s*5\s*,\s*6\s*\)')
    
    for i, line in enumerate(fixed):
        if ident_pattern.search(line):
            # 替换为 TODO 注释，让 agent 下次修复
            fixed[i] = line.replace(
                '(0, 1, 2, 3, 4, 5, 6)',
                '(?, ?, ?, ?, ?, ?, ?)  # FIXME: 用条件分支或 best_assign 替换恒等映射'
            )
    
    return fixed

def _inject_best_assign(lines):
    """如果代码中没有 best_assign 调用，自动注入"""
    code = "\n".join(lines)
    if "best_assign(" not in code:
        return lines
    
    # 找 for gi in range 循环，在 targets 赋值前插入 best_assign
    import re
    new = []
    for line in lines:
        # 替换 patterns: 硬编码 perm 或直接索引
        if "perm" in line and ("(0," in line or "(0,1,2," in line):
            new.append("    # AUTO-FIX: best_assign below")
            new.append("    targets = best_assign(prev, geo[gi])")
            continue
        if "targets = geo[gi]" in line and "best_assign" not in line:
            new.append("    targets = best_assign(prev, geo[gi])")
            continue
        new.append(line)
    return new
