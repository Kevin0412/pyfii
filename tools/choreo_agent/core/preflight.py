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

FORBIDDEN_GEO_TEMPLATES = {
    "geo_wide_v", "geo_arrow", "geo_box", "geo_diagonal", "geo_wave", "geo_grid",
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
    # 5. Deprecated geometry templates
    _check_no_geo_templates(code, r)
    # 6. Handwritten geometry contract
    _check_custom_points_contract(code, r)
    # 7. Syntax / indentation
    _check_syntax(code, r)
    # 8. Bare API calls (d.move2 / d.VelXY)
    _check_no_bare_api(code, r)
    # 9. inittime calls
    _check_no_inittime(code, r)
    # 10. Single-drone timing after group move
    _check_no_single_drone_timing(code, r)
    # 11. Cheap coordinate literal range guard
    _check_coordinate_literals(code, r)

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


def _check_no_geo_templates(code, r):
    tokens = set(re.findall(r'\b([a-zA-Z_]\w*)\s*\(', code))
    leaked = tokens & FORBIDDEN_GEO_TEMPLATES
    for name in sorted(leaked):
        r.add(
            f"几何模板已下线: {name}() — 改用 custom_points([...], n=len(drones), min_xy_cm=90) "
            "手写目标点表，再用 best_assign/far_assign 做路径分配"
        )
    if "jitter_points(" in code:
        r.add(
            "禁止 jitter_points() 出现在 final segment — 它会在 custom_points 校验后再次扰动坐标，"
            "可能绕过安全点表检查；请直接手写最终 numeric targets，并使用 custom_points(..., min_xy_cm=90 或刻意密集时 51-90 字面量)"
        )


def _check_custom_points_contract(code, r):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "custom_points":
            continue
        for keyword in node.keywords:
            if keyword.arg != "min_xy_cm":
                continue
            value = _literal_number(keyword.value)
            if value is None:
                r.add(
                    "custom_points 的 min_xy_cm 必须是 51-90 之间的字面量；不要写变量或表达式"
                )
            elif not (51.0 <= value <= 90.0):
                r.add(
                    f"custom_points min_xy_cm={value:g} — 必须是 51-90 之间的字面量："
                    "90 是开阔队形默认值，51 是 pyfii core 碰撞警告硬下限；"
                    "刻意密集造型可用 55-75，不要调高到 90 以上导致可用点表被拒"
                )


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
        r.add("调用 inittime() — 时间游标由 takeoff/delay/move 链自然推进，删除此调用")


def _check_no_single_drone_timing(code, r):
    """Block common bad repair where only drones[0] gets light/delay after group moves."""
    if re.search(r'\b(?:drones|ds)\s*\[[^\]]+\]\s*\.\s*delay\s*\(', code):
        r.add("只给单架 drones[i].delay() 推进时间 — 每个 move2 后必须在同一个 per-drone loop 内给每架机留执行时间")
    if re.search(r'\bapply_light\s*\(\s*(?:drones|ds)\s*\[[^\]]+\]', code):
        r.add("只给单架 apply_light(drones[i]) — 正式段灯光/等待应在 per-drone loop 内作用到每架机或明确分组")


def _check_coordinate_literals(code, r):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Tuple, ast.List)) or len(node.elts) != 3:
            continue
        values = [_literal_number(elt) for elt in node.elts]
        if any(value is None for value in values):
            continue
        x, y, z = values
        errors = []
        if not 0 <= x <= 560:
            errors.append(f"x={x:g}")
        if not 0 <= y <= 560:
            errors.append(f"y={y:g}")
        if not 80 <= z <= 250:
            errors.append(f"z={z:g}")
        if errors:
            r.add(
                f"坐标常量超出 pyfii 场地范围(line {getattr(node, 'lineno', '?')}): "
                + ", ".join(errors)
                + "；XY 必须在 0-560，Z 必须在 80-250，或显式使用 clamp_xy/clamp_z。"
            )


def _literal_number(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = _literal_number(node.operand)
        return -value if value is not None else None
    return None


def preflight_feedback(result: PreflightResult) -> str:
    """Format preflight errors as LLM repair feedback."""
    if result.passed:
        return "PREFLIGHT OK — 进入完整 validator"
    lines = ["## Preflight 失败 (结构/协议/工具泄漏)"]
    for e in result.errors:
        lines.append(f"- {e}")
    lines.append("\n请修正后重新输出 Python 代码片段。")
    return "\n".join(lines)
