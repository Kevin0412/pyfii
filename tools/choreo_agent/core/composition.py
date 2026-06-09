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
STAGGER_WORDS = ("卡农", "错峰", "分组", "canon", "stagger")
CLIMAX_WORDS = ("高潮", "爆发", "爆点", "climax", "burst")


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
    if needs_stagger and not features["has_indexed_stagger"]:
        errors.append(
            "当前段章法要求卡农/错峰/分组，但代码没有明显按 i/group 分批 delay 或分组推进；"
            "请在 per-drone loop 内加入安全的分组错峰，而不是全队完全同步。"
        )

    needs_climax = _mentions_any(full_reference_text, CLIMAX_WORDS)
    if needs_climax:
        max_excursion = _float((motion_quality or {}).get("max_excursion_cm"))
        if max_excursion is not None and max_excursion < 150.0:
            errors.append(
                f"高潮段动作幅度不足：max_excursion={max_excursion:.1f}cm；"
                "高潮应有至少一组明确展开/爆发到 150cm 以上。"
            )

    colors = features["color_literals"]
    if _text(card.get("lighting")) and features["apply_light_calls"] == 0:
        errors.append("设计卡声明了灯光弧线，但代码没有 apply_light(...)。")
    if needs_climax and len(colors) < 2:
        errors.append("高潮/爆发段灯光过单一：至少使用两种颜色或一次明显亮度/色彩变化。")

    if degradation:
        z_range = _float(degradation.get("window_z_range_cm"))
        if _mentions_any(full_reference_text, ("高低", "三层", "高度", "层")) and z_range is not None and z_range < 70:
            errors.append(
                f"章法要求高度层，但实际 Z range={z_range:.1f}cm；"
                "需要真实 low/mid/high 变化，不要只写在设计卡里。"
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
    )
    move_group_calls = len(re.findall(r"\bmove_group\s*\(", code))
    staggered_group_calls = len(re.findall(r"\bmove_group_staggered\s*\(", code))
    apply_light_calls = len(re.findall(r"\bapply_light\s*\(", code))
    features = {
        "move2_calls": len(re.findall(r"\bmove2\s*\(", code)),
        "move_group_calls": move_group_calls,
        "move_group_staggered_calls": staggered_group_calls,
        "apply_light_calls": apply_light_calls + move_group_calls + staggered_group_calls,
        "delay_calls": len(re.findall(r"\.delay\s*\(", code)),
        "uses_best_assign": "best_assign(" in code,
        "uses_far_assign": "far_assign(" in code,
        "has_indexed_stagger": has_indexed_stagger,
        "color_literals": colors,
        "z_literal_range_cm": None,
    }
    z_values = _extract_target_z_literals(code)
    if z_values:
        features["z_literal_range_cm"] = round(max(z_values) - min(z_values), 1)
    return features


def _extract_target_z_literals(code: str) -> list[float]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    values: list[float] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Tuple, ast.List)) or len(node.elts) != 3:
            continue
        z = _numeric_literal(node.elts[2])
        if z is not None:
            values.append(z)
    return values


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
