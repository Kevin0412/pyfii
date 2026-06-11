"""Preflight cheap gates — deterministic checks before expensive validator."""

import ast
import math
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


def preflight_check(
    code: str,
    segment_id: str | None = None,
    drone_count: int | None = None,
) -> PreflightResult:
    """Run all cheap checks on agent-generated code. Returns result with errors."""
    r = PreflightResult()
    if not code.strip():
        r.add("空代码")
        return r

    # 12. Position-attribute writes (teleport cheat) — S01 起飞前的
    #     `drone.X = drone.x = ...` 是合法协议，其他段直接改坐标属性
    #     会破坏 move2 的速度反算。
    _check_no_position_writes(code, r, segment_id)
    # 13. Math-geometry static evaluation — comprehension 算出的点表
    #     在 preflight 就按 custom_points 同样的裁剪+间距规则验一遍，
    #     违规直接回报精确数字，省掉一轮运行期 ValueError。
    _check_computed_geometry(code, r, drone_count)
    # 14. S01 起飞布局静态验算：任意构图都行，但 XY 间距必须 ≥51cm。
    _check_start_positions(code, r, segment_id, drone_count)
    # 15. LAND 协议硬门：必须 d.land()，不得 move2。
    _check_land_protocol(code, r, segment_id)

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


# ---------- Math-geometry static evaluation (calculator for computed point tables) ----------

_SAFE_FUNCS = {
    "sin": math.sin,
    "cos": math.cos,
    "sqrt": math.sqrt,
    "int": int,
    "round": round,
    "float": float,
    "abs": abs,
    "min": min,
    "max": max,
    "len": len,
}
_SAFE_MATH_ATTRS = {"sin", "cos", "pi", "tau", "sqrt"}
_MAX_RANGE = 64


class _UnsafeExpression(Exception):
    pass


def _safe_eval(node, env, depth=0):
    """Whitelist AST evaluator for geometry expressions. Raises _UnsafeExpression."""
    if depth > 24:
        raise _UnsafeExpression("depth")
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise _UnsafeExpression("non-numeric constant")
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        raise _UnsafeExpression(f"unknown name {node.id}")
    if isinstance(node, ast.Attribute):
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "math"
            and node.attr in _SAFE_MATH_ATTRS
        ):
            return getattr(math, node.attr)
        raise _UnsafeExpression("attribute")
    if isinstance(node, ast.BinOp) and isinstance(
        node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
    ):
        left = _safe_eval(node.left, env, depth + 1)
        right = _safe_eval(node.right, env, depth + 1)
        ops = {
            ast.Add: lambda a, b: a + b,
            ast.Sub: lambda a, b: a - b,
            ast.Mult: lambda a, b: a * b,
            ast.Div: lambda a, b: a / b,
            ast.FloorDiv: lambda a, b: a // b,
            ast.Mod: lambda a, b: a % b,
            ast.Pow: lambda a, b: a ** b if abs(b) <= 8 else _raise_unsafe(),
        }
        return ops[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _safe_eval(node.operand, env, depth + 1)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id == "range":
            args = [int(_safe_eval(a, env, depth + 1)) for a in node.args]
            result = range(*args)
            if len(result) > _MAX_RANGE:
                raise _UnsafeExpression("range too large")
            return result
        if isinstance(func, ast.Name) and func.id in _SAFE_FUNCS:
            args = [_safe_eval(a, env, depth + 1) for a in node.args]
            return _SAFE_FUNCS[func.id](*args)
        if isinstance(func, ast.Attribute):
            target = _safe_eval(func, env, depth + 1)
            args = [_safe_eval(a, env, depth + 1) for a in node.args]
            return target(*args)
        raise _UnsafeExpression("call")
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_safe_eval(elt, env, depth + 1) for elt in node.elts]
    if isinstance(node, (ast.ListComp, ast.GeneratorExp)):
        if len(node.generators) != 1:
            raise _UnsafeExpression("multi-generator")
        gen = node.generators[0]
        if not isinstance(gen.target, ast.Name):
            raise _UnsafeExpression("tuple target")
        iterable = _safe_eval(gen.iter, env, depth + 1)
        items = list(iterable)
        if len(items) > _MAX_RANGE:
            raise _UnsafeExpression("iterable too large")
        out = []
        for item in items:
            local_env = dict(env)
            local_env[gen.target.id] = item
            keep = all(
                _safe_eval(cond, local_env, depth + 1) for cond in gen.ifs
            )
            if keep:
                out.append(_safe_eval(node.elt, local_env, depth + 1))
        return out
    raise _UnsafeExpression(type(node).__name__)


def _raise_unsafe():
    raise _UnsafeExpression("pow exponent")


def _build_geometry_env(tree, drone_count):
    """Collect simple numeric/list assignments in source order so comprehensions can use them."""
    env = {"pi": math.pi, "PI": math.pi}
    if drone_count:
        env["drones"] = [None] * int(drone_count)
        env["N"] = int(drone_count)
    assigns = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    ]
    for node in sorted(assigns, key=lambda n: n.lineno):
        try:
            env[node.targets[0].id] = _safe_eval(node.value, env)
        except _UnsafeExpression:
            continue
    return env


def evaluate_static_points(node_or_code, env=None, drone_count=None):
    """Evaluate a geometry expression to a list of (x,y,z). Returns None if not evaluable."""
    if isinstance(node_or_code, str):
        try:
            tree = ast.parse(node_or_code, mode="eval")
        except SyntaxError:
            return None
        node = tree.body
        env = env or _build_geometry_env(tree, drone_count)
    else:
        node = node_or_code
        env = env or {}
    try:
        points = _safe_eval(node, env)
    except (_UnsafeExpression, ValueError, TypeError, ZeroDivisionError, OverflowError):
        return None
    if not isinstance(points, list) or not points:
        return None
    normalized = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 3:
            return None
        try:
            normalized.append(tuple(float(v) for v in point))
        except (TypeError, ValueError):
            return None
    return normalized


def _clamp_point(point):
    """Mirror function.py _target3: round + clamp XY 0-560, Z 80-250."""
    x, y, z = point
    return (
        max(0, min(560, int(round(x)))),
        max(0, min(560, int(round(y)))),
        max(80, min(250, int(round(z)))),
    )


def _is_xyz_listcomp(node):
    return isinstance(node, (ast.ListComp, ast.GeneratorExp)) and isinstance(
        node.elt, (ast.Tuple, ast.List)
    ) and len(node.elt.elts) == 3


def _is_computed_xyz_listcomp(node):
    """True only for comprehensions that *generate* geometry (contain arithmetic/calls).

    状态读取类 comprehension（`[(d.x, d.y, d.z) for d in drones]`、
    `[(t[0], t[1], t[2]) for t in targets]`）是段协议的标准写法，不算生成几何。
    """
    if not _is_xyz_listcomp(node):
        return False
    return any(
        isinstance(sub, (ast.BinOp, ast.Call))
        for elt in node.elt.elts
        for sub in ast.walk(elt)
    )


def _check_computed_geometry(code, r, drone_count):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return
    env = _build_geometry_env(tree, drone_count)

    # 1. custom_points(...) 的点表（直接 comprehension 或先赋值再传名字）静态验算
    wrapped_nodes: set[int] = set()
    wrapped_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "custom_points":
            continue
        if not node.args:
            continue
        arg = node.args[0]
        wrapped_nodes.add(id(arg))
        if isinstance(arg, ast.Name):
            wrapped_names.add(arg.id)
        min_xy_cm = 90.0
        for keyword in node.keywords:
            if keyword.arg == "min_xy_cm":
                value = _literal_number(keyword.value)
                if value is not None:
                    min_xy_cm = value
        if isinstance(arg, ast.Name):
            raw = env.get(arg.id)
        else:
            try:
                raw = _safe_eval(arg, env)
            except _UnsafeExpression:
                raw = None
        points = _coerce_points(raw)
        if not points:
            continue  # 静态算不出来就交给运行期 custom_points 兜底
        clamped = [_clamp_point(p) for p in points]
        if drone_count and len(clamped) != int(drone_count):
            r.add(
                f"custom_points 点表实际算出 {len(clamped)} 个点 != 机数 {int(drone_count)}"
                f"(line {getattr(node, 'lineno', '?')})"
            )
            continue
        if len(clamped) >= 2:
            md, pair = _static_min_xy(clamped)
            if md < float(min_xy_cm):
                r.add(
                    f"计算几何点表(line {getattr(node, 'lineno', '?')})裁剪后最小 XY 间距 "
                    f"{md:.0f}cm (点{pair[0]}-点{pair[1]}) < min_xy_cm={min_xy_cm:g}，"
                    "运行期 custom_points 会直接抛错 — 增大半径/间距后再提交"
                    "（9 机圆形建议 R≥150，弦距≈116cm）"
                )

    # 2. 没包 custom_points 的 computed 3 元组 comprehension 直接拒绝：
    #    raw comprehension 跳过裁剪和间距校验，等于裸坐标。
    assigned_comp_names = {
        node.targets[0].id: node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and _is_computed_xyz_listcomp(node.value)
    }
    for node in ast.walk(tree):
        if not _is_computed_xyz_listcomp(node):
            continue
        if id(node) in wrapped_nodes:
            continue
        owner = next(
            (name for name, value in assigned_comp_names.items() if value is node),
            None,
        )
        if owner is not None and owner in wrapped_names:
            continue
        r.add(
            f"computed 点表(line {getattr(node, 'lineno', '?')})没有经过 custom_points 包裹 — "
            "math 几何必须写 `geo = custom_points([...公式...], n=len(drones), min_xy_cm=90)`，"
            "由它统一裁剪坐标并校验间距；不要把 comprehension 直接传给 best_assign/far_assign/move2"
        )


# 起飞间距硬下限与全场一致：51cm 以下 pyfii core 报碰撞。构图密度是设计自由。
START_POSITION_MIN_XY_CM = 51.0


def _check_start_positions(code, r, segment_id, drone_count):
    """Statically verify takeoff layout spacing so any custom formation is safe."""
    if segment_id is None or str(segment_id).upper() != "S01":
        return
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return
    env = _build_geometry_env(tree, drone_count)
    raw = env.get("start_positions")
    if not isinstance(raw, list) or len(raw) < 2:
        return
    pairs = []
    for p in raw:
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            return  # 静态算不出来，交给运行期碰撞检测兜底
        try:
            pairs.append((float(p[0]), float(p[1])))
        except (TypeError, ValueError):
            return
    if drone_count and len(pairs) != int(drone_count):
        r.add(f"start_positions 有 {len(pairs)} 个点 != 机数 {int(drone_count)}")
        return
    oob = [
        f"({x:g},{y:g})" for x, y in pairs if not (0 <= x <= 560 and 0 <= y <= 560)
    ]
    if oob:
        r.add(f"start_positions 越界: {', '.join(oob[:3])} — XY 必须在 0-560")
    md, pair = _static_min_xy([(x, y, 0.0) for x, y in pairs])
    if md < START_POSITION_MIN_XY_CM:
        r.add(
            f"起飞布局最小 XY 间距 {md:.0f}cm (点{pair[0]}-点{pair[1]}) < 硬下限 51cm — "
            "拉开这两个起飞点；构图形状和密度随意，51cm 是 pyfii core 碰撞底线"
        )


def _coerce_points(raw):
    """Normalize an evaluated value to [(x,y,z), ...] floats, or None."""
    if not isinstance(raw, list) or not raw:
        return None
    points = []
    for p in raw:
        if not isinstance(p, (list, tuple)) or len(p) != 3:
            return None
        try:
            points.append(tuple(float(v) for v in p))
        except (TypeError, ValueError):
            return None
    return points


def _static_min_xy(points):
    md = 1e9
    pair = (0, 0)
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            d = (
                (points[i][0] - points[j][0]) ** 2
                + (points[i][1] - points[j][1]) ** 2
            ) ** 0.5
            if d < md:
                md = d
                pair = (i, j)
    return md, pair


def _check_land_protocol(code, r, segment_id):
    """LAND 只降落：必须有 d.land()，不得有 move2 编舞（协议硬门）。"""
    if segment_id is None or str(segment_id).upper() != "LAND":
        return
    if not re.search(r"\.\s*land\s*\(\s*\)", code):
        r.add("LAND 段缺少 d.land() — LAND 协议：auto_init + 短灯光提示 + 每架机 d.land()，缺一不可")
    if re.search(r"\bmove2\w*\s*\(", code):
        r.add("LAND 段出现 move2 — LAND 不编舞不移动，只降落；收束动作属于上一个正式段")


def _check_no_position_writes(code, r, segment_id):
    """Ban assignment to drone position attributes outside S01 (teleport cheat)."""
    if segment_id is None or str(segment_id).upper() == "S01":
        return
    match = re.search(r"\.\s*[xyzXYZ]\s*=(?!=)", code)
    if match:
        r.add(
            "禁止直接赋值 drone.x/y/z/X/Y/Z 位置属性 — 瞬移会破坏 move2 的速度反算；"
            "位置变化只能通过 move2/takeoff/land（起飞前设置初始位置只允许出现在 S01）"
        )


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
    """Block the bad-repair pattern where only drones[0] gets light/delay after group moves.

    `for i in range(...): drones[i].delay(...)` 是合法的 per-drone 写法（循环覆盖全队），
    只有 *循环外* 的下标式 delay/apply_light 才是给单架机开小灶。
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return

    loop_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)):
            for sub in ast.walk(node):
                loop_nodes.add(id(sub))

    def _is_drones_subscript(node):
        return (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id in ("drones", "ds")
        )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or id(node) in loop_nodes:
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "delay"
            and _is_drones_subscript(node.func.value)
        ):
            r.add(
                "循环外只给单架 drones[i].delay() 推进时间 — "
                "每个 move2 后必须在同一个 per-drone loop 内给每架机留执行时间"
            )
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "apply_light"
            and node.args
            and _is_drones_subscript(node.args[0])
        ):
            r.add(
                "循环外只给单架 apply_light(drones[i]) — "
                "正式段灯光/等待应在 per-drone loop 内作用到每架机或明确分组"
            )


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
