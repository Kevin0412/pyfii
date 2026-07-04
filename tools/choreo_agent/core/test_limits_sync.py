"""三份真相同步测试（P1）：function.py / pyfii_guide.md 的数字钉死到 core/limits.py。

function.py 因"零依赖纯标准库"是承重属性（六处 spec_from_file_location 加载，
含生产 skills.py 注册表校验）不能 import limits——用 AST 断言其内部字面量与
单一来源一致；guide.md 的三行结构化数字用锚定 regex 断言（各恰好匹配一次）。
启发式建议数字（R≥85 等派生经验）刻意不测。
"""

import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.limits import (
    COLLISION_FLOOR_CM,
    FIELD_XY_MAX,
    FIELD_XY_MIN,
    MIN_SHOW_END_S,
    Z_MAX_CM,
    Z_MIN_CM,
)

TOOL_ROOT = Path(__file__).resolve().parent.parent
FUNCTION_PY = TOOL_ROOT / "project_template" / "scripts" / "function.py"
GUIDE_MD = TOOL_ROOT / "context_packs" / "pyfii_guide.md"

# min_xy_cm 默认值必须等于碰撞地板的函数（jitter_points 合法默认 70，刻意不纳入）
FLOOR_DEFAULT_FUNCS = {"custom_points", "follow_chain", "chain_lane", "chain_follow_safe"}


def _function_tree() -> ast.Module:
    return ast.parse(FUNCTION_PY.read_text(encoding="utf-8"))


def _numeric(node) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    return None


def test_function_py_floor_defaults_match_limits():
    tree = _function_tree()
    seen: dict[str, float] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in FLOOR_DEFAULT_FUNCS:
            continue
        args = node.args
        names = [a.arg for a in args.args + args.kwonlyargs]
        defaults = list(args.defaults) + list(args.kw_defaults)
        # 对齐尾部默认值（positional defaults 靠右对齐）
        pos_names = [a.arg for a in args.args][-len(args.defaults):] if args.defaults else []
        for name, default in zip(pos_names, args.defaults):
            if name == "min_xy_cm":
                value = _numeric(default)
                assert value == COLLISION_FLOOR_CM, (
                    f"{node.name}.min_xy_cm 默认 {value} != 单一来源 {COLLISION_FLOOR_CM}"
                )
                seen[node.name] = value
        for name, default in zip([a.arg for a in args.kwonlyargs], args.kw_defaults):
            if name == "min_xy_cm" and default is not None:
                value = _numeric(default)
                assert value == COLLISION_FLOOR_CM, (
                    f"{node.name}.min_xy_cm 默认 {value} != {COLLISION_FLOOR_CM}"
                )
                seen[node.name] = value
    missing = FLOOR_DEFAULT_FUNCS - set(seen)
    assert not missing, f"未找到 min_xy_cm 默认值的函数: {missing}"
    print("PASSED: function.py floor defaults match limits")


def _comparisons_in(func_name: str) -> list[tuple[str, float]]:
    tree = _function_tree()
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            for cmp_node in ast.walk(node):
                if isinstance(cmp_node, ast.Compare) and len(cmp_node.ops) == 1:
                    value = _numeric(cmp_node.comparators[0])
                    if value is not None and value == COLLISION_FLOOR_CM:
                        out.append((type(cmp_node.ops[0]).__name__, value))
    return out


def test_function_py_floor_comparisons_and_operators():
    # safe_assign 的硬地板比较存在且值一致
    safe_assign = _comparisons_in("safe_assign")
    assert any(v == COLLISION_FLOOR_CM for _op, v in safe_assign), safe_assign
    # verify_timed_clearance 与门同为严格大于（P1 修复的算符漂移不许回退）
    vtc = _comparisons_in("verify_timed_clearance")
    assert ("Gt", COLLISION_FLOOR_CM) in vtc, (
        f"verify_timed_clearance 必须用严格 > {COLLISION_FLOOR_CM}（与验证门一致），实际 {vtc}"
    )
    assert ("GtE", COLLISION_FLOOR_CM) not in vtc, "算符漂移回退：>= 又出现了"
    print("PASSED: function.py floor comparisons and strict-greater operator")


def test_function_py_clamp_bounds_match_limits():
    tree = _function_tree()
    bounds: dict[str, list[float]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ("clamp_xy", "clamp_z"):
            values = sorted(
                {v for n in ast.walk(node) if (v := _numeric(n)) is not None}
            )
            bounds[node.name] = values
    assert bounds.get("clamp_xy") == sorted({FIELD_XY_MIN, FIELD_XY_MAX}), bounds
    assert bounds.get("clamp_z") == sorted({Z_MIN_CM, Z_MAX_CM}), bounds
    print("PASSED: function.py clamp bounds match limits")


def test_guide_md_structured_numbers_match_limits():
    text = GUIDE_MD.read_text(encoding="utf-8")
    checks = [
        (r"clamp_xy\(v\)\s*#\s*\[(\d+),\s*(\d+)\]", (FIELD_XY_MIN, FIELD_XY_MAX)),
        (r"clamp_z\(v\)\s*#\s*\[(\d+),\s*(\d+)\]", (Z_MIN_CM, Z_MAX_CM)),
        (r"##\s*(\d+)s 后再 LAND", (MIN_SHOW_END_S,)),
    ]
    for pattern, expected in checks:
        matches = re.findall(pattern, text)
        assert len(matches) == 1, f"guide.md 锚点 {pattern!r} 应恰好匹配一次，实际 {len(matches)}"
        got = matches[0] if isinstance(matches[0], tuple) else (matches[0],)
        assert tuple(float(v) for v in got) == tuple(float(v) for v in expected), (
            f"guide.md {pattern!r}: {got} != {expected}"
        )
    print("PASSED: guide.md structured numbers match limits")


def test_skill_doc_header_floor_matches_limits():
    from core.skills import render_full_skill_doc

    doc = render_full_skill_doc()
    assert f"dense_minD > {int(COLLISION_FLOOR_CM)}cm" in doc
    print("PASSED: SKILL doc header floor matches limits")


if __name__ == "__main__":
    test_function_py_floor_defaults_match_limits()
    test_function_py_floor_comparisons_and_operators()
    test_function_py_clamp_bounds_match_limits()
    test_guide_md_structured_numbers_match_limits()
    test_skill_doc_header_floor_matches_limits()
    print("\nALL LIMITS SYNC TESTS PASSED")
