"""Composition-level checks for choreo_agent output.

These checks are intentionally lightweight: they do not try to judge art, but
they force every generated segment to carry a clear dramaturgical contract and
catch obvious "safe but random" regressions before locking.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping, Sequence
from typing import Any


CARD_FIELDS = ("role", "motifs", "beat", "formation", "lighting")
STAGGER_WORDS = ("卡农", "错峰", "分组", "波次", "涟漪", "接力", "跟随", "canon", "stagger", "wave", "ripple", "relay")
CLIMAX_WORDS = ("高潮", "爆发", "爆点", "climax", "burst")
GEO_TEMPLATE_NAMES = ("geo_wide_v", "geo_arrow", "geo_box", "geo_diagonal", "geo_wave", "geo_grid")
# 母题执行器（function.py）：调用即真实时间错峰/动态灯光，门当作 per-drone 细节对待。
# safe_move 内部就是 ripple_move/group_relay（自带错峰），算真实时间错峰——否则推 safe_move 的
# 提示与"必须有时间错峰"的构图门冲突，逼模型回去手搓 drone.delay（正是想消除的）。
MOTIF_MOVE_NAMES = (
    "safe_move", "call_response_safe", "ripple_move",
    "follow_chain", "chain_follow_safe", "group_relay",
)
MOTIF_LIGHT_NAMES = ("light_wave", "fade_rgb", "fade_group", "breathe_group", "flash_group")
HANDWRITTEN_REQUIRED_SEGMENTS = {"S02", "S03", "S04", "S05"}
PER_DRONE_REQUIRED_SEGMENTS = {"S01", "S02", "S03", "S04", "S05", "S06"}
MONOTONE_PACING_SEGMENTS = {"S01", "S02", "S03", "S04", "S05"}
TIME_STAGGER_REQUIRED_SEGMENTS = {"S02", "S03", "S04", "S05"}


def evaluate_composition(
    code: str,
    composition_plan: Mapping[str, Any] | None,
    segment_id: str | None,
    motion_quality: Mapping[str, Any] | None = None,
    degradation: Mapping[str, Any] | None = None,
) -> tuple[dict, list[str]]:
    """Return composition features and blocking errors for a generated segment."""
    segment_id = (segment_id or "").upper()
    card = extract_design_card(code)
    features = extract_code_features(code)
    role = _segment_role(composition_plan, segment_id)
    role_text = _role_text(role)
    role_motifs = _role_motifs(role)
    avoid_terms = _role_avoid(role)
    full_card_text = " ".join(str(value) for value in card.values())
    full_reference_text = " ".join([role_text, " ".join(role_motifs)])

    result = {
        "segment_id": segment_id,
        "design_card": card,
        "features": features,
        "role": role_text,
        "role_motifs": role_motifs,
        "avoid": avoid_terms,
        "recommendations": [],
    }
    errors: list[str] = []

    if not card:
        errors.append(
            "缺少设计卡注释。当前段代码开头必须包含 # role/# motifs/# beat/# formation/# lighting，"
            "用于约束段落章法，避免随机续写。"
        )
        return result, errors

    missing = [field for field in CARD_FIELDS if not _text(card.get(field))]
    if missing:
        errors.append(
            "设计卡字段不完整：缺少 "
            + ", ".join(f"#{field}" for field in missing)
            + "。"
        )

    if role_motifs and not _mentions_any(full_card_text, role_motifs):
        errors.append(
            "设计卡没有承接当前段母题：需要在 #motifs/#beat/#formation 中明确使用或变奏 "
            + " / ".join(role_motifs[:4])
            + "。"
        )

    if avoid_terms and _mentions_any(_text(card.get("formation")), avoid_terms):
        errors.append(
            "设计卡 formation 命中了当前段避免项："
            + " / ".join(term for term in avoid_terms if term and term in _text(card.get("formation")))
            + "。"
        )

    needs_stagger = _mentions_any(full_reference_text, STAGGER_WORDS)
    if needs_stagger and not features["has_time_stagger"]:
        errors.append(
            "当前段章法要求卡农/错峰/分组，但代码只有颜色分组、没有真正的时间错峰；"
            "把移动改成 route-around 点表 + `prev = safe_move(drones, prev, geo, flying_ms, mode=\"wave\")`，"
            "或 `safe_assign(..., delays=..., flying_ms=...) + ripple_move(...)`。"
            "真对穿/relay 只用于明确 mirror-cross；若清不开就改两条 XY 带绕行。"
        )

    needs_climax = _needs_climax_gate(segment_id, role_text, role_motifs)
    if needs_climax:
        max_excursion = _float((motion_quality or {}).get("max_excursion_cm"))
        if max_excursion is not None and max_excursion < 150.0:
            errors.append(
                f"高潮段动作幅度不足：max_excursion={max_excursion:.1f}cm；"
                "高潮应有至少一组明确展开/爆发到 150cm 以上。"
            )

    colors = features["color_literals"]
    color_count = features["color_count"]
    has_dynamic_lighting = features["has_dynamic_lighting"]
    if (
        _text(card.get("lighting"))
        and features["apply_light_calls"] == 0
        and features["raw_turnonall_calls"] == 0
    ):
        errors.append("设计卡声明了灯光弧线，但代码没有 apply_light(...) 或 TurnOnAll(...)。")
    if needs_climax and color_count < 2 and not has_dynamic_lighting:
        errors.append("高潮/爆发段灯光过单一：至少使用两种颜色或一次明显亮度/色彩变化（渐变呼吸也算）。")

    if degradation:
        z_range = _float(degradation.get("window_z_range_cm"))
        if _mentions_any(full_reference_text, ("高低", "三层", "高度", "层")) and z_range is not None and z_range < 70:
            errors.append(
                f"章法要求高度层，但实际 Z range={z_range:.1f}cm；"
                "需要真实 low/mid/high 变化，不要只写在设计卡里。"
            )

    if segment_id in HANDWRITTEN_REQUIRED_SEGMENTS and features["geo_template_call_count"] > 0:
        used = ", ".join(
            f"{name} x{count}" for name, count in features["geo_template_calls"].items() if count
        )
        errors.append(
            f"{segment_id} 使用了已下线几何模板（{used}）。"
            "正式主体段必须写 custom_points([...]) 或明确坐标表，再交给 best_assign/far_assign；"
            "不要用 geo_* 参数变体替代编舞构图。"
        )

    if segment_id in PER_DRONE_REQUIRED_SEGMENTS and features["uses_group_only_execution"]:
        errors.append(
            f"{segment_id} 只使用 move_group/move_group_staggered 执行 keyframe。"
            "正式段应展开 per-drone loop：move2(drone, target, flying_ms) → "
            "apply_light(drone, color, ticks) → drone.delay(...)；"
            "move_group 只作为 smoke/兜底工具，不能替代编舞执行细节。"
        )

    # S06/尾声允许刻意的平静收束，所以单调节奏门只看 S01-S05。
    if (
        segment_id in MONOTONE_PACING_SEGMENTS
        and features["estimated_keyframe_count"] >= 2
        and features["uniform_move2_duration"]
        and color_count <= 1
        and not has_dynamic_lighting
        and not features["has_indexed_stagger"]
    ):
        errors.append(
            "节奏完全单调：所有 keyframe 同一 flying_ms、整段只有一种灯光颜色、无任何错峰。"
            "至少做一项：让一个 keyframe 明显短促或延展、换灯光颜色/做颜色渐变、"
            "或在 per-drone loop 内按 i % group_mod 加小错峰。"
        )

    # 同起同停门：正式编舞段(S02-S05)必须有真正的时间错峰，
    # 颜色分组(i % 3 选色)不算 — 观感上全队仍然同起同停。
    if (
        segment_id in TIME_STAGGER_REQUIRED_SEGMENTS
        and features["estimated_keyframe_count"] >= 1
        and not features["has_time_stagger"]
    ):
        errors.append(
            f"{segment_id} 全段所有无人机同起同停 — 至少一个 keyframe 要打破时间同步："
            "把移动改成 route-around 点表 + `prev = safe_move(drones, prev, geo, flying_ms, mode=\"wave\")`，"
            "或 `safe_assign(..., delays=..., flying_ms=...) + ripple_move(...)`；"
            "不要手搓对穿 delay。"
        )

    if segment_id == "S04" and features["estimated_keyframe_count"] < 4:
        errors.append(
            "S04 是抒情展开段，至少需要 4 个明确 keyframe 或 4 组目标点，"
            "不要退化成少量同步大块移动。"
        )
    if segment_id == "S04" and color_count < 3 and not has_dynamic_lighting:
        errors.append("S04 灯光过单一：抒情展开段至少需要 3 种颜色或三段明显色彩变化（渐变呼吸也算）。")

    if segment_id == "S06" and features["estimated_keyframe_count"] < 2:
        errors.append(
            "S06 尾声应为两段式收尾：先到中继/呼应姿态，再到最终署名位置；"
            "单 keyframe 容易变成小挪动或过早悬停。"
        )

    # ---- 品质建议（非阻塞） ----
    recs: list[str] = result["recommendations"]
    if errors:
        pass  # 有阻塞错误时不输出品质建议
    elif segment_id in PER_DRONE_REQUIRED_SEGMENTS:
        if not features["has_math_geometry"] and not features["has_indexed_stagger"]:
            recs.append(
                "品质提升：本段只有整数坐标表，没有 math 构造几何和交错启动。"
                "考虑加一个 sin/cos 圆形/弧线 keyframe，或 per-drone delay(i*ms) 分层启动。"
            )
        if features["lighting_tick_estimate"] < 30 and segment_id in {"S04", "S05"}:
            recs.append(
                "灯光密度偏低（约 " + str(features["lighting_tick_estimate"])
                + " ticks）。S04/S05 推荐 30-80 ticks 的渐变/呼吸灯光：一行 "
                "`fade_group(drones, c1, c2, duration_ms)` / `breathe_group(drones, color, cycles, period_ms)` "
                "/ `light_wave(drones, ripple_delays(prev), palette)`，"
                "或 `for a in range(N): TurnOnAll((r,g,b)); d.delay(100)` 手写长渐变。"
            )
        if features["z_range_cm"] is not None and features["z_range_cm"] < 60:
            recs.append(
                f"Z 跨度仅 {features['z_range_cm']:.0f}cm。推荐适当增大高度层范围（≥90cm）"
                "或加入 per-drone Z 个性偏移 (move2 内 +dz*sin(i))。"
            )

    return result, errors


def extract_design_card(code: str) -> dict[str, str]:
    """Parse leading design-card comments from generated segment code."""
    card: dict[str, str] = {}
    for raw_line in code.splitlines()[:30]:
        stripped = raw_line.strip()
        if not stripped:
            continue
        if not stripped.startswith("#"):
            # Stop once real code starts; the card belongs at the top.
            if card:
                break
            continue
        match = re.match(r"#\s*(role|motifs?|beat|formation|lighting|light)\s*[:：]\s*(.*)$", stripped, re.I)
        if not match:
            continue
        key = match.group(1).lower()
        if key == "motif":
            key = "motifs"
        if key == "light":
            key = "lighting"
        card[key] = match.group(2).strip()
    return card


def extract_code_features(code: str) -> dict:
    """Extract cheap static features from a generated segment."""
    colors = sorted(set(re.findall(r"#[0-9a-fA-F]{6}\b", code)))
    has_indexed_stagger = bool(
        re.search(r"\.delay\s*\([^)]*\bi\b", code)
        or re.search(r"\bi\s*(?:%|//|\*)", code)
        or re.search(r"\bgroup(?:s|_id)?\b", code, re.I)
        or re.search(r"\bmove_group_staggered\s*\(", code)
        or re.search(rf"\b(?:{'|'.join(MOTIF_MOVE_NAMES)})\s*\(", code)
    )
    move_group_calls = len(re.findall(r"\bmove_group\s*\(", code))
    staggered_group_calls = len(re.findall(r"\bmove_group_staggered\s*\(", code))
    motif_move_counts = {
        name: len(re.findall(rf"\b{name}\s*\(", code)) for name in MOTIF_MOVE_NAMES
    }
    motif_light_counts = {
        name: len(re.findall(rf"\b{name}\s*\(", code)) for name in MOTIF_LIGHT_NAMES
    }
    motif_move_calls = sum(motif_move_counts.values())
    motif_light_calls = sum(motif_light_counts.values())
    raw_apply_light_calls = len(re.findall(r"\bapply_light\s*\(", code))
    raw_turnonall_calls = len(re.findall(r"\.TurnOnAll\s*\(", code))
    # RGB 三元组字面量颜色：d.TurnOnAll((255, 200, 40)) 及灯光母题参数里的 (r,g,b)
    rgb_tuple_colors = set(
        re.findall(r"TurnOnAll\s*\(\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", code)
    )
    light_motif_line = re.compile(rf"\b(?:{'|'.join(MOTIF_LIGHT_NAMES)})\s*\(")
    for line in code.splitlines():
        if light_motif_line.search(line):
            for triple in re.findall(r"\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)", line):
                if all(int(v) <= 255 for v in triple):
                    rgb_tuple_colors.add(triple)
    rgb_tuple_colors = sorted(rgb_tuple_colors)
    # 计算式灯光（渐变/呼吸）：TurnOnAll 参数含 int()/sin()/cos()，或灯光母题执行器
    # gradient_to= 把动作母题的灯光变成逐 tick 渐变（dntg 式持续变色），算动态灯光。
    uses_gradient = bool(re.search(r"\bgradient_to\s*=", code))
    has_dynamic_lighting = bool(
        re.search(r"TurnOnAll\s*\([^)]*(?:int\s*\(|sin\s*\(|cos\s*\()", code)
        or motif_light_calls
        or uses_gradient
    )
    geo_template_calls = {
        name: len(re.findall(rf"\b{name}\s*\(", code))
        for name in GEO_TEMPLATE_NAMES
    }
    xyz_literal_count = _count_coordinate_literals(code)
    move2_calls = len(re.findall(r"\bmove2\s*\(", code))
    delay_calls = len(re.findall(r"\.delay\s*\(", code))
    custom_points_calls = len(re.findall(r"\bcustom_points\s*\(", code))
    move2_durations = _extract_move2_durations(code)
    motif_keyframe_bonus = (
        motif_move_counts["safe_move"]
        + 2 * motif_move_counts["call_response_safe"]
        + motif_move_counts["ripple_move"]
        + 2 * motif_move_counts["group_relay"]
        + 3 * motif_move_counts["follow_chain"]
        + 3 * motif_move_counts["chain_follow_safe"]
    )
    features = {
        "move2_calls": move2_calls,
        "move_group_calls": move_group_calls,
        "move_group_staggered_calls": staggered_group_calls,
        "motif_move_calls": motif_move_calls,
        "motif_light_calls": motif_light_calls,
        "motif_calls": {**motif_move_counts, **motif_light_counts},
        "raw_apply_light_calls": raw_apply_light_calls,
        "raw_turnonall_calls": raw_turnonall_calls,
        "apply_light_calls": (
            raw_apply_light_calls + move_group_calls + staggered_group_calls
            + motif_move_calls + motif_light_calls
        ),
        "has_dynamic_lighting": has_dynamic_lighting,
        "uses_gradient": uses_gradient,
        "delay_calls": delay_calls,
        "uses_group_only_execution": (
            (move_group_calls + staggered_group_calls) > 0
            and move2_calls == 0
            and motif_move_calls == 0
        ),
        "uses_best_assign": "best_assign(" in code,
        "uses_far_assign": "far_assign(" in code,
        "custom_points_calls": custom_points_calls,
        "uses_custom_points": custom_points_calls > 0,
        "uses_jitter_points": "jitter_points(" in code,
        "geo_template_calls": geo_template_calls,
        "geo_template_call_count": sum(geo_template_calls.values()),
        "xyz_literal_count": xyz_literal_count,
        "estimated_keyframe_count": max(move2_calls, custom_points_calls) + motif_keyframe_bonus,
        "has_handwritten_geometry": "custom_points(" in code or xyz_literal_count >= 6,
        "has_indexed_stagger": has_indexed_stagger,
        "has_time_stagger": _has_time_stagger(code),
        "has_math_geometry": _has_math_geometry(code),
        "color_literals": colors,
        "rgb_tuple_color_count": len(rgb_tuple_colors),
        "color_count": len(colors) + len(rgb_tuple_colors),
        "move2_duration_values": move2_durations,
        "uniform_move2_duration": len(move2_durations) == 1,
        "lighting_tick_estimate": _estimate_lighting_ticks(code),
        "z_literal_range_cm": None,
        # 品质建议用的别名
        "z_range_cm": None,
    }
    z_values = _extract_target_z_literals(code)
    if z_values:
        zr = round(max(z_values) - min(z_values), 1)
        features["z_literal_range_cm"] = zr
        features["z_range_cm"] = zr
    return features


def _extract_move2_durations(code: str) -> list[float]:
    """Distinct flying_ms values: move2 3rd-arg literals + *_ms name assignments used in move2."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    ms_assignments: dict[str, float] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        value = _numeric_literal(node.value)
        if isinstance(target, ast.Name) and "ms" in target.id.lower() and value is not None:
            ms_assignments[target.id] = value

    durations: set[float] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "move2":
            continue
        if len(node.args) < 3:
            continue
        arg = node.args[2]
        value = _numeric_literal(arg)
        if value is not None:
            durations.add(value)
        elif isinstance(arg, ast.Name) and arg.id in ms_assignments:
            durations.add(ms_assignments[arg.id])
    return sorted(durations)


_LIGHT_CONTEXT_FUNCS = frozenset(MOTIF_LIGHT_NAMES) | {"TurnOnAll", "apply_light", "pulse_group"}
_COLOR_KWARGS = frozenset({"color", "colors", "alt_color", "c_from", "c_to"})


def _in_light_context(node: ast.AST) -> bool:
    """3 元组位于灯光函数参数/color 关键字/palette 命名赋值内 → 是颜色不是坐标。"""
    current = getattr(node, "parent", None)
    while current is not None:
        if isinstance(current, ast.keyword) and current.arg in _COLOR_KWARGS:
            return True
        if isinstance(current, ast.Call):
            func = current.func
            name = func.id if isinstance(func, ast.Name) else (
                func.attr if isinstance(func, ast.Attribute) else None
            )
            if name in _LIGHT_CONTEXT_FUNCS:
                return True
        if isinstance(current, ast.Assign) and len(current.targets) == 1:
            target = current.targets[0]
            if isinstance(target, ast.Name) and re.search(r"color|palette", target.id, re.I):
                return True
        current = getattr(current, "parent", None)
    return False


def _extract_target_z_literals(code: str) -> list[float]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    _attach_parents(tree)

    values: list[float] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Tuple, ast.List)) or len(node.elts) != 3:
            continue
        if _is_z_layers_literal(node) or _in_light_context(node):
            continue
        z = _numeric_literal(node.elts[2])
        if z is not None:
            values.append(z)
    return values


def _count_coordinate_literals(code: str) -> int:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0
    _attach_parents(tree)

    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Tuple, ast.List)) or len(node.elts) != 3:
            continue
        if _is_z_layers_literal(node) or _in_light_context(node):
            continue
        values = [_numeric_literal(elt) for elt in node.elts]
        if any(value is None for value in values):
            continue
        x, y, z = values
        if 0 <= x <= 560 and 0 <= y <= 560 and 80 <= z <= 250:
            count += 1
    return count


def _attach_parents(tree: ast.AST) -> None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child.parent = parent  # type: ignore[attr-defined]


_LOOP_VAR_NAMES = {"i", "j", "k", "idx", "gi"}


_STAGGER_CALL_NAMES = frozenset(MOTIF_MOVE_NAMES) | {"move_group_staggered"}


def _has_time_stagger(code: str) -> bool:
    """True if drones genuinely desynchronize in time, not just in color/grouping.

    认定为时间错峰的写法：
    - `drone.delay(<含循环变量的表达式>)`：起飞波次 / 尾部回正
    - `move2(drone, target, <含循环变量的时长>)`：到达波次（每架机不同 flying_ms）
    - 母题执行器 `ripple_move/call_response_safe/follow_chain/chain_follow_safe/group_relay/move_group_staggered`：内部真实错峰
    `targets[i]` 这种下标用法不算 — 那只是取目标点，时间仍然同步。
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "delay"
            and node.args
            and _contains_loop_var(node.args[0])
        ):
            return True
        if isinstance(node.func, ast.Name) and node.func.id in _STAGGER_CALL_NAMES:
            return True
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in ("move2", "move2autoz")
            and len(node.args) >= 3
            and _contains_loop_var(node.args[2])
        ):
            return True
    return False


def _contains_loop_var(node: ast.AST) -> bool:
    return any(
        isinstance(sub, ast.Name) and sub.id in _LOOP_VAR_NAMES
        for sub in ast.walk(node)
    )


def _has_math_geometry(code: str) -> bool:
    """Detect math-based geometry: sin/cos comprehensions or inline math expressions."""
    return bool(
        re.search(r"\bsin\s*\(", code)
        or re.search(r"\bcos\s*\(", code)
        or "cmath" in code
        or "math." in code
    )


def _estimate_lighting_ticks(code: str) -> int:
    """Estimate total lighting ticks.

    apply_light(d, color, ticks) → ticks（直接计入）
    `for a in range(N):` 循环体（同行或后 4 行）内含 TurnOnAll/TurnOffAll → 计 N 一次；
    apply_light 循环不重复计（其 ticks 参数已计入）。
    灯光母题执行器按参数估算（缺省用默认值）。
    """
    ticks = 0
    for match in re.finditer(r"\bapply_light\s*\([^,]+,\s*[^,]+,\s*(\d+)\s*\)", code):
        ticks += int(match.group(1))
    lines = code.splitlines()
    for idx, line in enumerate(lines):
        match = re.search(r"for\s+\w+\s+in\s+range\s*\(\s*(\d+)\s*\)", line)
        if not match:
            continue
        window = " ".join(lines[idx : idx + 5])
        if re.search(r"TurnOnAll|TurnOffAll", window) and "apply_light" not in window:
            ticks += int(match.group(1))
    return ticks + _motif_light_ticks(code)


def _motif_light_ticks(code: str) -> int:
    """灯光母题执行器的 tick 估算（AST 取数字字面量参数，缺省用签名默认值）。"""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0

    def arg_num(node: ast.Call, pos: int, name: str, default: float) -> float:
        if len(node.args) > pos:
            value = _numeric_literal(node.args[pos])
            if value is not None:
                return value
        for keyword in node.keywords:
            if keyword.arg == name:
                value = _numeric_literal(keyword.value)
                if value is not None:
                    return value
        return default

    ticks = 0.0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        name = node.func.id
        if name == "fade_rgb":
            ticks += arg_num(node, 3, "steps", 12)
        elif name == "fade_group":
            ticks += arg_num(node, 3, "duration_ms", 1500) / max(
                50, arg_num(node, 4, "interval_ms", 100)
            )
        elif name == "breathe_group":
            ticks += arg_num(node, 2, "cycles", 2) * arg_num(node, 3, "period_ms", 1600) / max(
                50, arg_num(node, 5, "interval_ms", 100)
            )
        elif name == "flash_group":
            ticks += arg_num(node, 2, "times", 3) * (
                arg_num(node, 3, "on_ms", 250) + arg_num(node, 4, "off_ms", 150)
            ) / 100
        elif name == "light_wave":
            ticks += arg_num(node, 3, "hold_ticks", 6) + 4
        elif name == "ripple_move":
            ticks += arg_num(node, 5, "hold_ticks", 4)
        elif name == "follow_chain":
            ticks += arg_num(node, 6, "hold_ticks", 2)
        elif name == "chain_follow_safe":
            ticks += arg_num(node, 8, "hold_ticks", 2)
        elif name == "call_response_safe":
            ticks += 12
        elif name == "group_relay":
            ticks += 12
    return int(round(ticks))


def _is_z_layers_literal(node: ast.AST) -> bool:
    parent = getattr(node, "parent", None)
    return isinstance(parent, ast.keyword) and parent.arg == "z_layers"


def _numeric_literal(node: ast.AST) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = _numeric_literal(node.operand)
        return -value if value is not None else None
    return None


def _segment_role(plan: Mapping[str, Any] | None, segment_id: str) -> Any:
    if not isinstance(plan, Mapping):
        return None
    roles = plan.get("segment_roles")
    if not isinstance(roles, Mapping):
        return None
    return roles.get(segment_id)


def _role_text(role: Any) -> str:
    if isinstance(role, Mapping):
        return _text(role.get("role") or role.get("intent"))
    return _text(role)


def _role_motifs(role: Any) -> list[str]:
    if isinstance(role, Mapping):
        return _items(role.get("motifs"))
    return []


def _role_avoid(role: Any) -> list[str]:
    if isinstance(role, Mapping):
        return _items(role.get("avoid"))
    return []


def _mentions_any(text: str, needles: Sequence[str]) -> bool:
    lowered = text.lower()
    return any(needle and needle.lower() in lowered for needle in needles)


def _needs_climax_gate(segment_id: str, role_text: str, role_motifs: Sequence[str]) -> bool:
    """Return whether climax-specific amplitude/color rules apply.

    A tail segment often says "从高潮回收" to describe its source. That should
    not inherit S05's climax gate; otherwise S06 gets rejected for intentionally
    calming down.
    """
    text = " ".join([role_text, " ".join(role_motifs)]).lower()
    if segment_id == "S05":
        return True
    if _mentions_any(text, ("尾声", "收束", "署名", "降落", "安全落地", "回收", "回到")):
        return False
    return _mentions_any(
        text,
        (
            "高潮段",
            "明亮高潮",
            "视觉峰值",
            "全场尺度爆发",
            "最强视觉",
            "center burst",
            "climax",
            "burst",
        ),
    )


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _items(value: Any) -> list[str]:
    if isinstance(value, str):
        parts = re.split(r"[;,，；/、]+", value)
        return [part.strip() for part in parts if part.strip()]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_text(item) for item in value if _text(item)]
    return []


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
