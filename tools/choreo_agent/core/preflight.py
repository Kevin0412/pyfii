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
    # 13. Narrow static geometry gate: only custom_points(...) inputs that can
    #     be evaluated exactly are checked here. Keep broad computed-geometry
    #     policing disabled to avoid the old repair-loop false positives.
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
    # 6a. Statically visible custom_points tables: catch exact runtime
    #     ValueErrors before pyfii execution.
    _check_static_custom_points(code, r, drone_count)
    # 6b. Narrow static check for raw follow_chain waypoint tables.
    #     This keeps the old broad computed-geometry preflight disabled, while
    #     catching the exact cannon failure mode: statically visible chain
    #     waypoints that are too dense for simultaneous occupancy.
    _check_follow_chain_waypoints(code, r, drone_count)
    # 7. Syntax / indentation
    _check_syntax(code, r)
    # 8. Bare API calls (d.move2 / d.VelXY)
    _check_no_bare_api(code, r)
    # 8b. Common runtime NameError/TypeError patterns
    _check_common_runtime_mistakes(code, r, segment_id=segment_id)
    # 8c. Sync-assign + staggered execution mismatch
    _check_assign_timing_mismatch(code, r, segment_id=segment_id)
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
        min_xy_cm = 51.0
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

    # 1b. follow_chain(...) 的波点表：路径语义（按 lag 间隔校验，不是全对间距），
    #     自带运行期校验，所以豁免 custom_points 包裹要求；这里做静态预检报准确数字。
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "follow_chain":
            continue
        if len(node.args) < 2:
            continue
        arg = node.args[1]
        wrapped_nodes.add(id(arg))
        if isinstance(arg, ast.Name):
            wrapped_names.add(arg.id)
        lag = 1.0
        min_xy_cm = 51.0
        if len(node.args) >= 4:
            value = _literal_number(node.args[3])
            if value is not None:
                lag = value
        for keyword in node.keywords:
            if keyword.arg == "lag_hops":
                value = _literal_number(keyword.value)
                if value is not None:
                    lag = value
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
            continue  # 静态算不出来交给运行期 follow_chain 兜底
        wps = [_clamp_point(p) for p in points]
        lag = max(1, int(lag))
        if drone_count:
            need = (int(drone_count) - 1) * lag + 1
            if len(wps) < need:
                r.add(
                    f"follow_chain 波点不足(line {getattr(node, 'lineno', '?')})："
                    f"{int(drone_count)} 机 lag_hops={lag} 需要至少 {need} 个波点，目前 {len(wps)} 个"
                )
                continue
        # 机数未知时只查相邻 lag 对（k=1），避免对闭环路径误报不会同时出现的远间隔。
        n_chain = int(drone_count) if drone_count else 2
        worst, pair = 1e9, (0, 0)
        for k in range(1, n_chain):
            gap = k * lag
            for j in range(gap, len(wps)):
                d = (
                    (wps[j][0] - wps[j - gap][0]) ** 2
                    + (wps[j][1] - wps[j - gap][1]) ** 2
                ) ** 0.5
                if d < worst:
                    worst, pair = d, (j - gap, j)
        if worst < float(min_xy_cm):
            r.add(
                f"follow_chain 链上间距不足(line {getattr(node, 'lineno', '?')})："
                f"波点{pair[0]}-波点{pair[1]} XY 距离 {worst:.0f}cm < {float(min_xy_cm):g}cm，"
                "两机会同时占据这两点，运行期会直接抛错 — 增大相邻波点间距或减小路径弯折重叠"
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
            "math 几何必须写 `geo = custom_points([...公式...], n=len(drones))`，"
            "由它统一裁剪坐标并校验间距；不要把 comprehension 直接传给 best_assign/far_assign/move2"
        )


def _check_follow_chain_waypoints(code, r, drone_count):
    """Statically reject raw follow_chain(...) waypoint lists when we can evaluate them.

    We intentionally do not revive the old broad computed-geometry preflight:
    custom_points and the runtime validator remain responsible for general point
    tables. Raw follow_chain is special because its safety rule is path-semantic
    (waypoint j and j-k*lag can be occupied simultaneously), and current cannon
    runs repeatedly fail only after expensive execution with this exact error.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return
    env = _build_geometry_env(tree, drone_count)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "follow_chain":
            continue
        if len(node.args) < 2:
            continue

        arg = node.args[1]
        lag = 1.0
        min_xy_cm = 51.0
        if len(node.args) >= 4:
            value = _literal_number(node.args[3])
            if value is not None:
                lag = value
        for keyword in node.keywords:
            if keyword.arg == "lag_hops":
                value = _literal_number(keyword.value)
                if value is not None:
                    lag = value
            elif keyword.arg == "min_xy_cm":
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
            continue  # dynamic path: runtime follow_chain still validates

        wps = [_clamp_point(p) for p in points]
        lag = max(1, int(lag))
        if drone_count:
            need = (int(drone_count) - 1) * lag + 1
            if len(wps) < need:
                r.add(
                    f"follow_chain 波点不足(line {getattr(node, 'lineno', '?')})："
                    f"{int(drone_count)} 机 lag_hops={lag} 需要至少 {need} 个波点，目前 {len(wps)} 个"
                )
                continue

        n_chain = int(drone_count) if drone_count else 2
        worst, pair = 1e9, (0, 0)
        for k in range(1, max(2, n_chain)):
            gap = k * lag
            for j in range(gap, len(wps)):
                d = (
                    (wps[j][0] - wps[j - gap][0]) ** 2
                    + (wps[j][1] - wps[j - gap][1]) ** 2
                ) ** 0.5
                if d < worst:
                    worst, pair = d, (j - gap, j)
        if worst < float(min_xy_cm):
            r.add(
                f"follow_chain 链上间距不足(line {getattr(node, 'lineno', '?')})："
                f"波点{pair[0]}-波点{pair[1]} XY 距离 {worst:.0f}cm < {float(min_xy_cm):g}cm，"
                "两机会同时占据这两点，运行期会直接抛错 — 增大相邻波点间距或改用 "
                "chain_follow_safe(control_points, spacing_cm=65)"
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
            f"几何模板已下线: {name}() — 改用 custom_points([...], n=len(drones)) "
            "手写目标点表，再用 best_assign/far_assign 做路径分配"
        )
    if "jitter_points(" in code:
        r.add(
            "禁止 jitter_points() 出现在 final segment — 它会在 custom_points 校验后再次扰动坐标，"
            "可能绕过安全点表检查；请直接手写最终 numeric targets，并使用 custom_points([...], n=len(drones))"
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
            if value is not None and value < 51.0:
                r.add(
                    f"custom_points min_xy_cm={value:g} — 不能低于 51（pyfii core 碰撞硬下限）"
                )


def _check_static_custom_points(code, r, drone_count):
    """Reject custom_points(...) calls whose point table is statically invalid.

    This intentionally checks only data that is already wrapped in
    custom_points, matching runtime semantics. It does not reject raw computed
    comprehensions, because the old broad geometry gate created false-positive
    repair loops.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return
    env = _build_geometry_env(tree, drone_count)

    checked_calls = {
        "custom_points": {"arg": 0, "min_xy_cm": 51.0, "n_arg": 1},
        "safe_move": {"arg": 2, "min_xy_cm": 51.0, "n_arg": None},
        "call_response_safe": {"arg": 2, "min_xy_cm": 51.0, "n_arg": None},
    }

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id not in checked_calls:
            continue
        spec = checked_calls[node.func.id]
        arg = _call_arg(node, int(spec["arg"]), "geo" if node.func.id != "custom_points" else "points")
        if arg is None:
            continue

        raw = env.get(arg.id) if isinstance(arg, ast.Name) else None
        if raw is None:
            try:
                raw = _safe_eval(arg, env)
            except _UnsafeExpression:
                raw = None
        points = _coerce_points(raw)
        if not points:
            continue

        min_xy_cm = float(spec["min_xy_cm"])
        n_arg = spec["n_arg"]
        if n_arg is not None and len(node.args) > int(n_arg) + 1:
            value = _literal_number(node.args[int(n_arg) + 1])
            if value is not None:
                min_xy_cm = value
        for keyword in node.keywords:
            if keyword.arg == "min_xy_cm":
                value = _literal_number(keyword.value)
                if value is not None:
                    min_xy_cm = value

        expected_n = None
        if n_arg is not None:
            if len(node.args) > int(n_arg):
                expected_n = _static_number(node.args[int(n_arg)], env)
            for keyword in node.keywords:
                if keyword.arg == "n":
                    expected_n = _static_number(keyword.value, env)
        if expected_n is None and drone_count:
            expected_n = int(drone_count)
        if expected_n is not None and len(points) != int(expected_n):
            r.add(
                f"{node.func.id} 静态点表有 {len(points)} 个点 != 期望 {int(expected_n)} "
                f"(line {getattr(node, 'lineno', '?')})"
            )
            continue

        clamped = [_clamp_point(point) for point in points]
        if len(clamped) >= 2:
            md, pair = _static_min_xy(clamped)
            if md < float(min_xy_cm):
                r.add(
                    f"{node.func.id} 静态点表(line {getattr(node, 'lineno', '?')}) "
                    f"最小 XY 间距 {md:.0f}cm (点{pair[0]}-点{pair[1]}) "
                    f"< min_xy_cm={float(min_xy_cm):g}；运行期会直接抛错，"
                    "请拉开点表或降低到不低于 51cm 的明确 min_xy_cm。"
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


def _check_common_runtime_mistakes(code, r, segment_id: str | None = None):
    """Catch recurring model mistakes that otherwise survive until full script execution."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return

    tick_duration_sources: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        duration_name = _duration_source_from_ticks_expr(node.value)
        if duration_name:
            tick_duration_sources[target.id] = duration_name

    if str(segment_id or "").upper() != "S01":
        _check_no_unbound_singular_drone(tree, r)

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "TurnOnAll"
        ):
            r.add(
                "裸调 TurnOnAll(...) 会 NameError — 它是 drone 方法；"
                "在 per-drone loop 中写 d.TurnOnAll(color)，或用 apply_light/flash_group"
            )
            break

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "turn_on"
        ):
            r.add(
                "Drone 没有 turn_on(...) 方法 — 用 `d.TurnOnAll(color)`，"
                "或优先用 `apply_light(d, color, ticks)` / `flash_group`"
            )
            break

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "TurnOff"
        ):
            r.add(
                "Drone 没有 TurnOff() 方法 — 用 `d.TurnOffAll()`，"
                "或优先用 apply_light/flash_group/fade_group 控制灯光收尾"
            )
            break

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        if node.func.id == "apply_light" and len(node.args) >= 3:
            ticks_arg = node.args[2]
            if (
                isinstance(ticks_arg, ast.BinOp)
                and isinstance(ticks_arg.op, ast.Mult)
                and max(
                    _literal_number(ticks_arg.left) or 0,
                    _literal_number(ticks_arg.right) or 0,
                ) >= 10
            ):
                r.add(
                    "apply_light 第三个参数是 ticks 数，不是毫秒；"
                    "不要写 `ticks * 100` / `ticks * 50` 或 `duration_ms`。例如 800ms 写 "
                    "`apply_light(d, color, 8)`"
                )
                break
        if node.func.id in {"apply_light", "fade_group", "flash_group"}:
            allowed_keywords = {
                "apply_light": {"interval_ms"},
                "fade_group": {"duration_ms", "interval_ms"},
                "flash_group": {"times", "on_ms", "off_ms", "alt_color"},
            }[node.func.id]
            bad_keywords = [
                keyword.arg
                for keyword in node.keywords
                if keyword.arg is not None and keyword.arg not in allowed_keywords
            ]
            if bad_keywords:
                r.add(
                    f"{node.func.id} 不支持关键字参数 {', '.join(bad_keywords)}；"
                    "按 helper 签名使用位置参数/合法关键字，避免运行时 TypeError。"
                )
                break
        if node.func.id == "light_wave" and len(node.args) >= 2:
            if any(keyword.arg == "delays" for keyword in node.keywords):
                r.add(
                    "light_wave 参数重复：签名是 light_wave(drones, delays, colors/palette, hold_ticks=...)；"
                    "不要写 light_wave(drones, prev, delays=...)。改成 "
                    "`light_wave(drones, delays3, palette=golden_palette, hold_ticks=8)`"
                )

    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        move_duration_names: set[str] = set()
        for stmt in node.body:
            for call in ast.walk(stmt):
                if not isinstance(call, ast.Call):
                    continue
                if not isinstance(call.func, ast.Name):
                    continue
                if call.func.id == "move2" and len(call.args) >= 3:
                    duration_key = _duration_expr_key(call.args[2])
                    if duration_key:
                        move_duration_names.add(duration_key)
        if not move_duration_names:
            continue
        for stmt in node.body:
            for call in ast.walk(stmt):
                if not isinstance(call, ast.Call):
                    continue
                if not isinstance(call.func, ast.Name):
                    continue
                if call.func.id == "apply_light" and len(call.args) >= 3:
                    light_duration_source = _duration_source_from_ticks_expr(
                        call.args[2], tick_duration_sources
                    )
                    if light_duration_source and light_duration_source in move_duration_names:
                        r.add(
                            "同一循环里 `move2(..., flying_ms)` 又用 "
                            "`apply_light(..., flying_ms//100)` 会把移动和灯效串行，"
                            "几乎等于把动作预算翻倍；请把 apply_light 改成 2-4 ticks、"
                            "或用 flash_group/fade_group 的短时灯效。"
                        )
                        return
                    continue
                if call.func.id == "move2" and len(call.args) >= 3:
                    # Already collected above. Keeping this branch explicit
                    # avoids accidentally treating move2 as a light call when
                    # future helpers add similarly shaped signatures.
                    continue

    sync_assign_names = set()
    sync_assign_funcs = {
        "best_assign", "far_assign", "mirror_assign", "swap_assign", "keep_assign",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        value = node.value
        if (
            isinstance(target, ast.Name)
            and isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id in sync_assign_funcs
        ):
            sync_assign_names.add(target.id)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "group_relay":
            continue
        targets_arg = node.args[1] if len(node.args) >= 2 else None
        for keyword in node.keywords:
            if keyword.arg == "targets":
                targets_arg = keyword.value
                break
        direct_sync_assign = (
            isinstance(targets_arg, ast.Call)
            and isinstance(targets_arg.func, ast.Name)
            and targets_arg.func.id in sync_assign_funcs
        )
        named_sync_assign = isinstance(targets_arg, ast.Name) and targets_arg.id in sync_assign_names
        if direct_sync_assign or named_sync_assign:
            r.add(
                "group_relay 只是底层接力执行器，不能搭配 best_assign/far_assign/mirror_assign "
                "这类同步分配直接飞；这是 S02 “算着安全、实跑相撞”的高频根因。"
                "问答段改用 `prev = call_response_safe(drones, prev, geo, flying_ms, gap_ms=...)`；"
                "若必须裸用 group_relay，targets 必须先由 `safe_assign(prev, geo, delays=relay_delays, "
                "flying_ms=flying_ms)` 产生。"
            )
            break

    split_group_names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        value = node.value
        if (
            isinstance(target, ast.Name)
            and isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "split_groups"
        ):
            split_group_names.add(target.id)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.comprehension)):
            continue
        iterable = node.iter
        if not isinstance(iterable, ast.Subscript):
            continue
        source = iterable.value
        assigned_result = isinstance(source, ast.Name) and source.id in split_group_names
        direct_result = (
            isinstance(source, ast.Call)
            and isinstance(source.func, ast.Name)
            and source.func.id == "split_groups"
        )
        if assigned_result or direct_result:
            r.add(
                "split_groups() 返回的是逐机 group_id 列表（如 [0,1,0,...]），"
                "gids[1] 是单个 int，不能 for 遍历；"
                "用 `for i, gid in enumerate(gids): if gid == 1: ...`，"
                "或直接调用 group_relay(..., group_ids=gids)"
            )
            break


def _check_no_unbound_singular_drone(tree, r):
    """Reject `drone.delay(...)` when `drone` is not a loop/local variable."""
    assigned_names: set[str] = set()
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
        if isinstance(parent, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = []
            if isinstance(parent, ast.Assign):
                targets = list(parent.targets)
            else:
                targets = [parent.target]
            for target in targets:
                assigned_names.update(_target_names(target))

    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "drone"
        ):
            continue
        if "drone" in assigned_names or _name_bound_by_enclosing_loop(node, parents, "drone"):
            continue
        r.add(
            "裸用 `drone.<method>(...)` 会 NameError：当前函数里没有名为 drone 的全局对象。"
            "写成 `for i, drone in enumerate(drones): ...` 并把 drone.delay/apply_light/move2 "
            "放进循环内；循环外请用 `for d in drones:` 或 helpers。"
        )
        return


def _target_names(target) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        out: set[str] = set()
        for elt in target.elts:
            out.update(_target_names(elt))
        return out
    return set()


def _name_bound_by_enclosing_loop(node, parents, name: str) -> bool:
    current = node
    while id(current) in parents:
        current = parents[id(current)]
        if isinstance(current, ast.For) and name in _target_names(current.target):
            return True
    return False


_SYNC_ASSIGN_FUNCS = {"best_assign", "far_assign", "keep_assign", "mirror_assign"}


def _check_assign_timing_mismatch(code, r, segment_id: str | None = None):
    """Block sync-assign results fed to staggered execution (ripple_move with delays
    or per-drone loop with drone.delay + move2).  S01 exempt — takeoff is synchronous."""
    if str(segment_id or "").upper() == "S01":
        return
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return

    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent

    sync_vars: dict[str, tuple[str, int]] = {}
    safe_assign_delays: dict[str, ast.expr | None] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        var = node.targets[0].id
        call = node.value
        if not isinstance(call, ast.Call):
            continue
        fname = _call_func_name(call)
        if fname in _SYNC_ASSIGN_FUNCS:
            sync_vars[var] = (fname, node.lineno)
        elif fname == "safe_assign":
            delays_node = _keyword_value(call, "delays")
            safe_assign_delays[var] = delays_node

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fname = _call_func_name(node)

        if fname == "ripple_move":
            targets_name = _positional_name(node, 1)
            delays_arg = _positional_or_kw(node, 3, "delays")
            has_delays = delays_arg is not None and not _is_literal_none(delays_arg)
            if targets_name and targets_name in sync_vars and has_delays:
                afn, aln = sync_vars[targets_name]
                r.add(
                    f"{afn}()(line {aln}) 的结果传给了带 delays 的 ripple_move — "
                    f"{afn} 用同步锁步模型验安全，但 ripple_move 错峰执行，时序不匹配会撞。"
                    "改成 `targets = safe_assign(prev, geo, delays=delays, flying_ms=...) "
                    "+ ripple_move(drones, targets, flying_ms, delays)`（同一 delays），"
                    "或直接 `prev = safe_move(drones, prev, geo, flying_ms, mode=\"wave\")`。"
                )
                return

            if targets_name and targets_name in safe_assign_delays and has_delays:
                sa_delays = safe_assign_delays[targets_name]
                if sa_delays is not None and not _ast_same(sa_delays, delays_arg):
                    r.add(
                        "safe_assign 和 ripple_move 使用了不同的 delays 变量 — "
                        "safe_assign 按传入的 delays 验证无碰撞时序，ripple_move 必须用同一份 delays 执行，"
                        "否则验证结果作废。把两处改成同一个 delays 变量，"
                        "或用 `prev = safe_move(drones, prev, geo, flying_ms)` 自动绑定。"
                    )
                    return

        if fname == "move2":
            for_node = _enclosing_for(node, parents)
            if for_node is None:
                continue
            targets_name = _loop_uses_sync_assign_target(for_node, sync_vars)
            if targets_name is None:
                continue
            if _loop_has_delay(for_node):
                afn, aln = sync_vars[targets_name]
                r.add(
                    f"{afn}()(line {aln}) 的结果在 per-drone 循环里配合 drone.delay 使用 — "
                    f"{afn} 假设全员同步起飞，手搓 delay 打破了这个前提，实跑会撞。"
                    "改成 `delays = ripple_delays(prev, ...); "
                    "targets = safe_assign(prev, geo, delays=delays, flying_ms=...); "
                    "prev = ripple_move(drones, targets, flying_ms, delays)`，"
                    "或 `prev = safe_move(drones, prev, geo, flying_ms, mode=\"wave\")`。"
                )
                return


def _call_func_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _keyword_value(call: ast.Call, kw: str) -> ast.expr | None:
    for k in call.keywords:
        if k.arg == kw:
            return k.value
    return None


def _positional_name(call: ast.Call, idx: int) -> str | None:
    if idx < len(call.args) and isinstance(call.args[idx], ast.Name):
        return call.args[idx].id
    for k in call.keywords:
        if k.arg == "targets" and isinstance(k.value, ast.Name):
            return k.value.id
    return None


def _positional_or_kw(call: ast.Call, idx: int, kw: str) -> ast.expr | None:
    if idx < len(call.args):
        return call.args[idx]
    return _keyword_value(call, kw)


def _is_literal_none(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _ast_same(a: ast.expr, b: ast.expr) -> bool:
    """Structural equality of two simple AST expressions (variable names, subscripts)."""
    if type(a) is not type(b):
        return False
    if isinstance(a, ast.Name):
        return a.id == b.id
    if isinstance(a, ast.Constant):
        return a.value == b.value
    if isinstance(a, ast.Subscript):
        return _ast_same(a.value, b.value) and _ast_same(a.slice, b.slice)
    return ast.dump(a) == ast.dump(b)


def _enclosing_for(node, parents) -> ast.For | None:
    current = node
    while id(current) in parents:
        current = parents[id(current)]
        if isinstance(current, ast.For):
            return current
    return None


def _loop_uses_sync_assign_target(for_node: ast.For, sync_vars: dict) -> str | None:
    """Check if the for-loop body subscripts or references a sync-assigned variable."""
    for node in ast.walk(for_node):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            if node.value.id in sync_vars:
                return node.value.id
    return None


def _loop_has_delay(for_node: ast.For) -> bool:
    """Check if the for-loop body has a stagger delay (index-dependent, before move2).

    Post-move constant delays (same value for all drones) are safe — they are
    just wait-for-completion, not a timing stagger.  A delay is a stagger if its
    argument references the loop variable (e.g. ``i * 120``, ``delays[i]``).
    """
    loop_vars = _target_names(for_node.target)
    for node in ast.walk(for_node):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "delay"
            and node.args
        ):
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and arg.value == 0:
            continue
        if _expr_references_names(arg, loop_vars):
            return True
    return False


def _expr_references_names(node: ast.expr, names: set[str]) -> bool:
    """Return True if any Name node in the expression tree matches ``names``."""
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id in names:
            return True
    return False


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


_LIGHT_FUNC_NAMES = {
    "TurnOnAll", "apply_light", "pulse_group", "fade_rgb", "fade_group",
    "breathe_group", "flash_group", "light_wave",
}
_COLOR_KWARG_NAMES = {"color", "colors", "alt_color", "c_from", "c_to"}


def _collect_light_tuple_ids(tree) -> set[int]:
    """RGB 三元组出现的合法位置：灯光函数参数 / color 类关键字 / palette·color 命名赋值。

    这些 3 元组是颜色不是坐标，坐标范围检查必须跳过它们。
    """
    light_ids: set[int] = set()

    def _mark(node):
        for sub in ast.walk(node):
            if isinstance(sub, (ast.Tuple, ast.List)) and len(sub.elts) == 3:
                light_ids.add(id(sub))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else (
                func.attr if isinstance(func, ast.Attribute) else None
            )
            if name in _LIGHT_FUNC_NAMES:
                for arg in node.args:
                    _mark(arg)
            for keyword in node.keywords:
                if keyword.arg in _COLOR_KWARG_NAMES:
                    _mark(keyword.value)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and re.search(
                r"color|palette", target.id, re.I
            ):
                _mark(node.value)
    return light_ids


def _check_coordinate_literals(code, r):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return
    parents = {
        id(child): parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    light_tuple_ids = _collect_light_tuple_ids(tree)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Tuple, ast.List)) or len(node.elts) != 3:
            continue
        if id(node) in light_tuple_ids:
            continue
        parent = parents.get(id(node))
        if (
            isinstance(parent, ast.Assign)
            and parent.value is node
            and any(isinstance(target, (ast.Tuple, ast.List)) for target in parent.targets)
        ):
            # 标量解包（如 `cx, cy, R = 280, 280, 70`）不是坐标点；
            # 真正的点表通常是 list 内的三元组，仍会被下面检查。
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


def _duration_source_from_ticks_expr(node, known_sources=None):
    """Return the duration variable name for expressions like flying_ms // 100."""
    known_sources = known_sources or {}
    if isinstance(node, ast.Name):
        return known_sources.get(node.id)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"int", "round"}:
        if len(node.args) == 1:
            return _duration_source_from_ticks_expr(node.args[0], known_sources)
    if not isinstance(node, ast.BinOp):
        return None
    if not isinstance(node.op, (ast.FloorDiv, ast.Div)):
        return None
    if _literal_number(node.right) != 100:
        return None
    return _duration_expr_key(node.left)


def _duration_expr_key(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        try:
            return ast.unparse(node)
        except Exception:
            return ast.dump(node, include_attributes=False)
    return None


def _call_arg(call, pos: int, keyword_name: str):
    if len(call.args) > pos:
        return call.args[pos]
    for keyword in call.keywords:
        if keyword.arg == keyword_name:
            return keyword.value
    return None


def _static_number(node, env):
    value = _literal_number(node)
    if value is not None:
        return value
    try:
        value = _safe_eval(node, env)
    except (_UnsafeExpression, ValueError, TypeError, ZeroDivisionError, OverflowError):
        return None
    return value if isinstance(value, (int, float)) else None


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
