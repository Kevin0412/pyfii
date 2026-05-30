"""独立函数段编辑器 —— 用 # AGENT_CODE_START / # AGENT_CODE_END 标记可编辑区。"""

import re
from pathlib import Path


def replace_active_segment(script_path: Path, segment_id: str, code: str, locked_ids: list[str]) -> bool:
    """替换 sXX(drones) 函数中 AGENT_CODE_START/END 之间的代码。"""
    try:
        lines = script_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return False

    seg_idx = int(segment_id[1:])  # S02 → 2
    if segment_id == "LAND":
        fn_name = "land"
    else:
        fn_name = f"s{seg_idx:02d}"

    # 找函数定义行
    fn_start = None
    for i, line in enumerate(lines):
        if f"def {fn_name}(" in line:
            fn_start = i
            break
    if fn_start is None:
        return False

    # 在函数体里找 AGENT_CODE_START 和 AGENT_CODE_END
    code_start = None
    code_end = None
    for i in range(fn_start, len(lines)):
        if "# AGENT_CODE_START" in lines[i]:
            code_start = i
        elif "# AGENT_CODE_END" in lines[i] and code_start is not None:
            code_end = i
            break

    if code_start is None:
        # 没有标记——在 return 前插入
        for i in range(fn_start, len(lines)):
            if lines[i].strip().startswith("return ") or lines[i].strip() == "return":
                indent = len(lines[i]) - len(lines[i].lstrip())
                marker_prefix = " " * indent
                new_lines = (
                    lines[:i]
                    + [f"{marker_prefix}# AGENT_CODE_START"]
                    + [f"{marker_prefix}{cl}" for cl in code.strip().splitlines()]
                    + [f"{marker_prefix}# AGENT_CODE_END"]
                    + lines[i:]
                )
                break
        else:
            # 没找到 return——在函数末尾插入
            new_lines = lines + [f"    # AGENT_CODE_START"] + [f"    {cl}" for cl in code.strip().splitlines()] + [f"    # AGENT_CODE_END"]
    else:
        # 替换 AGENT_CODE_START 和 AGENT_CODE_END 之间的内容
        before = lines[: code_start + 1]
        after = lines[code_end:]
        indent = len(lines[code_start]) - len(lines[code_start].lstrip())
        marker_prefix = " " * indent if indent > 0 else "    "
        new_lines = before + [f"{marker_prefix}{cl}" for cl in code.strip().splitlines()] + after

    tmp = script_path.with_suffix(".tmp")
    tmp.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    tmp.replace(script_path)
    return True


def read_segment_code(script_path: Path, segment_id: str) -> str | None:
    """读取 sXX(drones) 函数中 AGENT_CODE 之间的代码。"""
    lines = script_path.read_text(encoding="utf-8").splitlines()
    seg_idx = int(segment_id[1:]) if segment_id != "LAND" else -1
    fn_name = "land" if segment_id == "LAND" else f"s{seg_idx:02d}"

    fn_start = None
    for i, line in enumerate(lines):
        if f"def {fn_name}(" in line:
            fn_start = i
            break
    if fn_start is None:
        return None

    code_lines = []
    in_code = False
    for i in range(fn_start, len(lines)):
        if "# AGENT_CODE_START" in lines[i]:
            in_code = True
            continue
        if "# AGENT_CODE_END" in lines[i]:
            break
        if in_code:
            code_lines.append(lines[i])
    return "\n".join(code_lines).strip() or None


def read_prev_from_docstring(script_path: Path, segment_id: str) -> list | None:
    """从函数 docstring 中读取 prev 坐标。"""
    lines = script_path.read_text(encoding="utf-8").splitlines()
    seg_idx = int(segment_id[1:]) if segment_id != "LAND" else -1
    fn_name = "land" if segment_id == "LAND" else f"s{seg_idx:02d}"

    for i, line in enumerate(lines):
        if f"def {fn_name}(" in line:
            # 找 docstring 中的 prev: 行
            for j in range(i + 1, min(i + 20, len(lines))):
                if "prev:" in lines[j] and "[" in lines[j]:
                    # 提取坐标
                    text = lines[j].split("prev:")[-1]
                    floats = re.findall(r"[-+]?\d*\.?\d+", text)
                    if len(floats) >= 21:
                        return [
                            (float(floats[k]), float(floats[k + 1]), float(floats[k + 2]))
                            for k in range(0, 21, 3)
                        ]
            break
    return None


def update_prev_in_docstring(script_path: Path, segment_id: str, prev: list) -> bool:
    """更新函数 docstring 中的 prev 坐标注释。"""
    if not prev or len(prev) != 7:
        return False

    seg_idx = int(segment_id[1:]) if segment_id != "LAND" else -1
    fn_name = "land" if segment_id == "LAND" else f"s{seg_idx:02d}"

    lines = script_path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if f"def {fn_name}(" in line:
            for j in range(i + 1, min(i + 20, len(lines))):
                if "prev:" in lines[j]:
                    prev_str = "prev: [" + ",".join(
                        f"({p[0]:.0f},{p[1]:.0f},{p[2]:.0f})" for p in prev
                    ) + "]"
                    indent = len(lines[j]) - len(lines[j].lstrip())
                    lines[j] = " " * indent + prev_str
                    script_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    return True
    return False
