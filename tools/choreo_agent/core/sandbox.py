"""Agent 计算沙箱 — 让 agent 在生成代码前执行 Python 计算"""

import math
import itertools
import json
import sys
from pathlib import Path

# 安全白名单
_ALLOWED_BUILTINS = {
    "abs": abs, "round": round, "int": int, "float": float,
    "min": min, "max": max, "len": len, "range": range,
    "list": list, "tuple": tuple, "dict": dict, "set": set,
    "str": str, "bool": bool, "True": True, "False": False,
    "None": None, "print": print, "enumerate": enumerate,
    "zip": zip, "sorted": sorted, "sum": sum, "any": any, "all": all,
    "math": math, "itertools": itertools, "json": json,
}

# 安全限制
_MAX_EXEC_TIME_S = 5
_MAX_OUTPUT_CHARS = 8000


def safe_exec(code: str, context: dict | None = None) -> dict:
    """在安全沙箱中执行 Python 代码，返回 locals 中的新变量。

    自动注入以下函数：
    - best_assign(starts, targets): 返回 (perm, min_d)
    - flight_time_ms(d, v, a): 返回飞行时间(ms)
    - distance_3d(p1, p2): 返回两点3D距离
    """
    from core.best_assign import best_assign as _best_assign

    def best_assign(starts, targets):
        perm, min_d = _best_assign(starts, targets)
        return {"perm": perm, "min_d_cm": round(min_d, 1)}

    def flight_time_ms(d, v, a):
        if d <= 0:
            return 0
        accel_dist = v * v / (2 * a)
        if d >= 2 * accel_dist:
            t = 2 * v / a + (d - 2 * accel_dist) / v
        else:
            t = 2 * math.sqrt(d / a)
        return int(math.ceil(t * 1000))

    def distance_3d(p1, p2):
        return math.sqrt(
            (p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2 + (p2[2] - p1[2]) ** 2
        )

    sandbox = {
        "best_assign": best_assign,
        "flight_time_ms": flight_time_ms,
        "distance_3d": distance_3d,
        "__builtins__": _ALLOWED_BUILTINS,
    }
    if context:
        sandbox.update(context)

    # 捕获 stdout
    import io
    stdout = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = stdout

    try:
        exec(code, sandbox, sandbox)
    except Exception as e:
        return {"__error__": str(e), "__output__": stdout.getvalue()[:_MAX_OUTPUT_CHARS]}
    finally:
        sys.stdout = old_stdout

    output = stdout.getvalue()
    result = {
        k: v for k, v in sandbox.items()
        if not k.startswith("__") and k not in _ALLOWED_BUILTINS
        and k not in ("best_assign", "flight_time_ms", "distance_3d")
    }
    if output.strip():
        result["__output__"] = output[:_MAX_OUTPUT_CHARS]
    return result


def sandbox_result_to_text(result: dict) -> str:
    """将沙箱执行结果转成 LLM 可读的文本"""
    if "__error__" in result:
        return f"沙箱执行错误: {result['__error__']}"
    lines = ["沙箱计算结果:"]
    if "__output__" in result:
        lines.append(f"输出: {result['__output__'][:500]}")
    for k, v in result.items():
        if k == "__output__":
            continue
        lines.append(f"  {k} = {json.dumps(v, ensure_ascii=False)}")
    return "\n".join(lines)
