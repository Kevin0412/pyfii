"""Preflight cheap gates — deterministic checks before expensive validator."""

import ast
import re


# Agent-side tools that must NOT appear in design.py
FORBIDDEN_TOOLS = {
    "dist3", "flight_time_ms", "motion_budget", "budget_layer",
    "budget_layers", "timeline_cues", "assign_targets",
    "best_assign_local", "planning_tools", "safe_geo",
    "generate_safe_geo", "check_min_spacing", "predict_crossings",
}


class PreflightResult:
    def __init__(self):
        self.passed = True
        self.errors: list[str] = []

    def add(self, msg: str):
        self.passed = False
        self.errors.append(msg)

    def __bool__(self):
        return self.passed


def preflight_check(code: str) -> PreflightResult:
    """Run all cheap checks on agent-generated code. Returns result with errors."""
    r = PreflightResult()
    if not code.strip():
        r.add("空代码")
        return r

    # 1. Markdown / 中文解释残留
    _check_no_markdown(code, r)
    # 2. Import / from import
    _check_no_imports(code, r)
    # 3. def / class / nested helper
    _check_no_definitions(code, r)
    # 4. Agent tool leakage
    _check_no_tool_leakage(code, r)
    # 5. Syntax / indentation
    _check_syntax(code, r)
    # 6. Bare API calls (d.move2 / d.VelXY)
    _check_no_bare_api(code, r)
    # 7. inittime calls
    _check_no_inittime(code, r)

    return r


def _check_no_markdown(code, r):
    if "```" in code:
        r.add("包含 markdown fence ``` — 删除")
    if "设计说明" in code or "表格" in code or "方案" in code:
        r.add("包含中文解释文本 — 只输出 Python 代码")
    if re.search(r'^\s*\d+\.\s+\*\*', code, re.MULTILINE):
        r.add("包含 markdown 标题 — 删除")


def _check_no_imports(code, r):
    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            r.add(f"禁止 import: {stripped[:60]}")


def _check_no_definitions(code, r):
    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith("def ") or stripped.startswith("class "):
            r.add(f"禁止定义函数/类: {stripped[:60]}")


def _check_no_tool_leakage(code, r):
    tokens = set(re.findall(r'\b([a-zA-Z_]\w*)\b', code))
    leaked = tokens & FORBIDDEN_TOOLS
    for name in sorted(leaked):
        r.add(f"agent 侧工具泄漏: {name} — 替换为具体数值")


def _check_syntax(code, r):
    try:
        ast.parse(code)
    except SyntaxError as e:
        r.add(f"语法错误: {e.msg} (line {e.lineno})")


def _check_no_bare_api(code, r):
    """禁止 d.move2(x,y,z) / d.VelXY / d.VelZ 裸调"""
    # 检测 drone.move2(...) — 任何对象 .move2( 调用
    bare_move2 = re.findall(r'(\w+)\.move2\(', code)
    if bare_move2:
        r.add(f"裸调 move2: {', '.join(bare_move2[:3])}.move2() — 用 move2(d, (x,y,z), t_ms) 包装器")
    # 检测 VelXY/VelZ
    bare_vel = re.findall(r'(\w+)\.Vel(XY|Z)\(', code)
    if bare_vel:
        r.add(f"裸调 VelXY/VelZ: {', '.join([f'{m[0]}.Vel{m[1]}' for m in bare_vel[:3]])} — 用 move2 包装器")


def _check_no_inittime(code, r):
    if "inittime" in code:
        r.add("调用 inittime() — auto_init 已处理，删除此调用")


def preflight_feedback(result: PreflightResult) -> str:
    """Format preflight errors as LLM repair feedback."""
    if result.passed:
        return "PREFLIGHT OK — 进入完整 validator"
    lines = ["## Preflight 失败 (结构/协议/工具泄漏)"]
    for e in result.errors:
        lines.append(f"- {e}")
    lines.append("\n请修正后重新输出 Python 代码片段。")
    return "\n".join(lines)
