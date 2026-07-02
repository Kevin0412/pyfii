"""Composition planner — 从音乐生成全局章法与段窗，取代模板里的手写 dramaturgy。

硬编码消除的核心（PLAN 11.11）：换音乐零手工编辑，产出连贯且彼此不同的演出。
计划由 LLM 根据 music_brief 生成，结构由确定性 validator 把关；
输出兼容现有 composition_plan 消费方（prompt_builder/_format_*），
另带 segments 窗口数组供 state.json 重写段窗。

约束哲学：只给音乐证据和结构硬约束，不给任何队形/主题建议——
渐强映射到队形复杂度/灯光密度/角色交换，而非位移幅度；
音乐没有高能段时不得伪造爆发段（cjxq 测试）。
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any, Callable

from .skills import composite_catalog_block

FORMAL_SEGMENT_IDS = ["S01", "S02", "S03", "S04", "S05", "S06"]
MIN_SHOW_S = 55.0
MAX_SHOW_S = 75.0
MIN_SEGMENT_S = 4.0
MAX_SEGMENT_S = 17.0
LAND_MIN_S = 4.0
LAND_MAX_S = 6.0
TAKEOFF_S = 4.0


def build_planner_prompt(
    brief: Mapping[str, Any],
    drone_count: int,
    title: str | None = None,
    human_directives: list[str] | None = None,
    prior_plan: Mapping[str, Any] | None = None,
    preferences: str = "",
) -> str:
    duration = float(brief.get("duration_s") or 0)
    source_name = str(brief.get("music_source", "")).rsplit("/", 1)[-1]
    title_line = (
        f"- 曲目: {title}（人工提供的曲名/气质，**优先于音频特征推断**——文化与情绪语境是音频代理指标读不出来的）"
        if title
        else f"- 文件名: {source_name}（无人工曲名，气质只能从音频特征推断，注意不要把安静误读为黑暗、把克制误读为压抑）"
    )
    show_end_hint = min(duration, MAX_SHOW_S)
    sections = brief.get("sections") or []
    section_lines = "\n".join(
        f"  {s['time_range'][0]:.0f}-{s['time_range'][1]:.0f}s: 能量 {s['energy_label']}({s['energy']:.2f}), onset {s['onset_per_s']}/s"
        for s in sections
        if s["time_range"][0] < show_end_hint
    )
    cues = ", ".join(
        f"{c:.1f}" for c in (brief.get("hard_cues") or []) if c <= show_end_hint
    )
    has_high = any(s.get("energy_label") == "high" for s in sections)
    energy_note = (
        ""
        if has_high
        else "\n注意：这首音乐没有 high 能量段——不要伪造爆发/高潮段；强度变化用队形复杂度、灯光密度、角色交换表达。"
    )
    preferences_block = ""
    if preferences:
        from .design_memory import format_preferences_block

        preferences_block = "\n" + format_preferences_block(preferences)
    directives_block = ""
    if human_directives:
        numbered = "\n".join(f"{i+1}. {d}" for i, d in enumerate(human_directives))
        directives_block = (
            "\n## 人类导演意见（权威——与音频特征推断或默认原则冲突时，以导演意见为准）\n"
            + numbered
            + "\n"
        )
    prior_block = ""
    if prior_plan:
        prior_block = (
            "\n## 上一版计划（按导演意见修改；导演未提及的部分尽量保留）\n"
            + json.dumps(prior_plan, ensure_ascii=False)
            + "\n"
        )
    # 组合技能目录（从 core/skills.py 注册表生成，与段 prompt 的技能菜单同源）。
    catalog = composite_catalog_block()

    return f"""## 为这首音乐设计无人机灯光秀全局章法（{int(drone_count)} 机）
{preferences_block}{directives_block}{prior_block}
音乐证据（librosa 分析，节选至 {show_end_hint:.0f}s）：
{title_line}
- 总长 {duration:.1f}s，tempo {brief.get('tempo_bpm')} BPM（1 beat ≈ {brief.get('beat_interval_s')}s）
- 结构边界 (hard cues): {cues}
- 能量曲线:
{section_lines}{energy_note}

设计原则（语料库蒸馏）：
- 主题、母题、灯光弧线、空间叙事完全由你根据音乐气质决定；不要套用任何过往演出的主题。
- 强度映射到队形复杂度/灯光密度/角色交换，不映射到位移幅度。
- 段边界尽量贴 hard cues（±1.5s 容差）；大动作按 phrase 走，灯光按 beat 走。
- 质心可以迁移（启程/回归/钉守），是空间叙事工具。
- 每段给出灯光语体：motion（稀疏短提示）/ light_clock（灯光占满飞行窗，渐变呼吸）/ identity（每机独立色相）。
- 母题词汇可直接用（代码层有对应执行器，写进 motifs 会被照做）：波次涟漪、链式跟随/蛇形、分组问答接力、光波扫过、渐变收束、呼吸明暗、同步频闪；灯光可绑定动作意图（扩张配中心光波、问答配双色、收尾齐闪/渐隐）。
{catalog}
- 音乐比演出长时，演出用开头部分即可（结构上收束在你选的 show_end_s）。

硬约束：
- 正式段固定 6 个：S01-S06；之后 LAND {LAND_MIN_S:.0f}-{LAND_MAX_S:.0f}s。
- LAND 不编舞：只写 id/start_s/end_s，不要给 LAND 写 role/motifs——LAND 协议是原地降落，收束动作放进 S06。
- S01 从 {TAKEOFF_S:.0f}s 开始（前 {TAKEOFF_S:.0f}s 起飞）；每段 {MIN_SEGMENT_S:.0f}-{MAX_SEGMENT_S:.0f}s；窗口连续不重叠。
- show_end_s（LAND 结束）在 {MIN_SHOW_S:.0f}-{min(duration, MAX_SHOW_S):.0f}s 内。

只输出 JSON（不解释）：
{{
  "theme": "...",
  "dramaturgy": "...",
  "light_arc": "...",
  "centroid_arc": "...",
  "movement_motifs": ["...", "..."],
  "continuity_rules": ["...", "..."],
  "segments": [
    {{"id": "S01", "start_s": {TAKEOFF_S:.1f}, "end_s": 13.0, "role": "...", "motifs": ["..."], "avoid": ["..."], "lighting_register": "motion|light_clock|identity", "music_cue": "对应哪个音乐事件/能量"}},
    ... S02-S06 ...,
    {{"id": "LAND", "start_s": 63.0, "end_s": 68.0}}
  ]
}}"""


def parse_planner_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        plan = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    return plan if isinstance(plan, dict) else None


def validate_music_plan(plan: Mapping[str, Any], brief: Mapping[str, Any]) -> tuple[bool, str]:
    """结构确定性校验；返回 (ok, 中文报告/修正指令)。"""
    duration = float(brief.get("duration_s") or 0)
    problems: list[str] = []
    segments = plan.get("segments")
    if not isinstance(segments, list) or not segments:
        return False, "缺少 segments 数组"

    by_id = {str(s.get("id", "")).upper(): s for s in segments if isinstance(s, Mapping)}
    expected = FORMAL_SEGMENT_IDS + ["LAND"]
    missing = [sid for sid in expected if sid not in by_id]
    if missing:
        problems.append(f"缺少段: {', '.join(missing)}（必须正好 S01-S06 + LAND）")
    extra = [sid for sid in by_id if sid not in expected]
    if extra:
        problems.append(f"多余段: {', '.join(extra)}")

    if not problems:
        prev_end = None
        for sid in expected:
            seg = by_id[sid]
            try:
                start = float(seg["start_s"])
                end = float(seg["end_s"])
            except (KeyError, TypeError, ValueError):
                problems.append(f"{sid}: start_s/end_s 必须是数字")
                continue
            length = end - start
            if sid == "S01" and abs(start - TAKEOFF_S) > 0.51:
                problems.append(f"S01 必须从 {TAKEOFF_S:.0f}s 开始（实际 {start:.1f}）")
            if prev_end is not None and abs(start - prev_end) > 0.01:
                problems.append(f"{sid} 起点 {start:.1f} 与上一段终点 {prev_end:.1f} 不连续")
            if sid == "LAND":
                if not (LAND_MIN_S - 0.01 <= length <= LAND_MAX_S + 0.01):
                    problems.append(f"LAND 时长 {length:.1f}s，应在 {LAND_MIN_S:.0f}-{LAND_MAX_S:.0f}s")
                if end > duration + 0.01:
                    problems.append(f"show_end {end:.1f}s 超出音乐 {duration:.1f}s")
                if not (MIN_SHOW_S - 0.01 <= end <= min(duration, MAX_SHOW_S) + 0.01):
                    problems.append(
                        f"show_end {end:.1f}s 应在 {MIN_SHOW_S:.0f}-{min(duration, MAX_SHOW_S):.0f}s"
                    )
            elif not (MIN_SEGMENT_S - 0.01 <= length <= MAX_SEGMENT_S + 0.01):
                problems.append(f"{sid} 时长 {length:.1f}s，应在 {MIN_SEGMENT_S:.0f}-{MAX_SEGMENT_S:.0f}s")
            prev_end = end

        for sid in FORMAL_SEGMENT_IDS:
            seg = by_id.get(sid, {})
            if not str(seg.get("role", "")).strip():
                problems.append(f"{sid} 缺少 role")

    if problems:
        return False, "结构修正（只改下列问题，其余保持）：\n- " + "\n- ".join(problems)
    return True, "PASS"


def to_legacy_plan(plan: Mapping[str, Any]) -> dict:
    """转换为 prompt_builder/_format_* 兼容的 composition_plan 形状。"""
    segment_roles = {}
    for seg in plan.get("segments", []):
        sid = str(seg.get("id", "")).upper()
        if sid == "LAND":
            continue
        segment_roles[sid] = {
            "role": seg.get("role", ""),
            "motifs": seg.get("motifs", []),
            "avoid": seg.get("avoid", []),
            "relationship": seg.get("music_cue", ""),
            "lighting_register": seg.get("lighting_register", ""),
            # 结构化审美要求（min_keyframes/min_colors/requires_*），
            # 缺省时 composition 门回退 DEFAULT_REQUIREMENTS。
            "requirements": dict(seg.get("requirements") or {}),
        }
    legacy = {
        "theme": plan.get("theme", ""),
        "dramaturgy": plan.get("dramaturgy", ""),
        "light_arc": plan.get("light_arc", ""),
        "centroid_arc": plan.get("centroid_arc", ""),
        "movement_motifs": plan.get("movement_motifs", []),
        "continuity_rules": plan.get("continuity_rules", []),
        "segment_roles": segment_roles,
    }
    return legacy


def format_plan_summary(plan: Mapping[str, Any], brief: Mapping[str, Any]) -> str:
    """一屏可读的 plan 评审摘要：主题/弧线 + 段窗-cue 对照表。"""
    cues = brief.get("hard_cues") or []
    lines = [
        f"主题: {plan.get('theme')}",
        f"戏剧结构: {plan.get('dramaturgy')}",
        f"灯光弧线: {plan.get('light_arc')}",
        f"质心叙事: {plan.get('centroid_arc')}",
        "",
        f"{'段':<5} {'窗口':<13} {'时长':<5} {'贴cue':<7} {'灯光语体':<12} 角色",
    ]
    for seg in plan.get("segments", []):
        sid = str(seg.get("id", "?"))
        start, end = float(seg.get("start_s", 0)), float(seg.get("end_s", 0))
        cue_delta = (
            f"{min(abs(c - start) for c in cues):.1f}s" if cues else "-"
        )
        role = str(seg.get("role", ""))[:34]
        register = str(seg.get("lighting_register", "-"))
        lines.append(
            f"{sid:<5} {start:>5.1f}-{end:<6.1f} {end-start:>4.1f}s {cue_delta:<7} {register:<12} {role}"
        )
    return "\n".join(lines)


def plan_review_loop(
    music_path: str,
    provider: str,
    drone_count: int,
    title: str | None = None,
    chat_fn: Callable[..., Any] | None = None,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
    max_rounds: int = 6,
    memory_root: str | None = None,
) -> tuple[dict, list[dict]]:
    """HITL plan 评审门（PLAN 12.1）：approve 或给导演意见重新生成，循环至接受。

    导演意见作为权威约束注入重新生成 prompt（优先于音频推断）；
    memory_root 给定时，意见与结论同步落入 design_memory（PLAN 12.2）。
    Returns (result, trail)。
    """
    preferences = ""
    if memory_root:
        from .design_memory import load_preferences

        preferences = load_preferences(memory_root)
    directives: list[str] = []
    prior_plan = None
    trail: list[dict] = []
    for round_i in range(1, max_rounds + 1):
        result = generate_composition_plan(
            music_path,
            provider=provider,
            drone_count=drone_count,
            chat_fn=chat_fn,
            title=title,
            human_directives=directives or None,
            prior_plan=prior_plan,
            preferences=preferences,
        )
        summary = format_plan_summary(result["plan"], result["brief"])
        print_fn("\n===== 章法评审 第 %d 轮 =====\n%s\n" % (round_i, summary))
        verdict = input_fn(
            "[回车/a]=接受并开始生成  [文本]=导演意见并重新生成  [q]=中止: "
        ).strip()
        if verdict.lower() in ("", "a", "y", "approve"):
            trail.append({"round": round_i, "plan": result["plan"], "verdict": "approved"})
            if memory_root:
                from .design_memory import record

                record(
                    memory_root, "plan_approved",
                    f"主题《{result['plan'].get('theme')}》第 {round_i} 轮通过"
                    + (f"；此前意见：{'；'.join(directives)}" if directives else ""),
                    context=title or "",
                )
            return result, trail
        if verdict.lower() == "q":
            trail.append({"round": round_i, "plan": result["plan"], "verdict": "aborted"})
            raise SystemExit("plan review aborted by human")
        directives.append(verdict)
        prior_plan = result["plan"]
        trail.append({"round": round_i, "plan": result["plan"], "verdict": "rejected", "directive": verdict})
        if memory_root:
            from .design_memory import record

            record(memory_root, "plan_directive", verdict, context=title or "")
    raise SystemExit(f"plan review: {max_rounds} 轮未达成接受")


def generate_composition_plan(
    music_path: str,
    provider: str,
    drone_count: int,
    chat_fn: Callable[..., Any] | None = None,
    max_revisions: int = 2,
    title: str | None = None,
    human_directives: list[str] | None = None,
    prior_plan: Mapping[str, Any] | None = None,
    preferences: str = "",
) -> dict:
    """音乐 → brief → LLM 章法 → 确定性校验（最多 2 轮修正）。

    返回 {"plan": 原始计划(含 segments 窗口), "legacy": 兼容形状, "brief": music_brief}
    校验最终失败时抛 ValueError —— 调用方决定是否回退模板。
    """
    from .music_brief import generate_music_brief

    brief = generate_music_brief(music_path)
    if not brief:
        raise ValueError(f"music analysis failed: {music_path}")

    if chat_fn is None:
        from .llm_client import chat

        def chat_fn(prompt: str) -> str:  # type: ignore[misc]
            if str(provider or "").lower().startswith("mimo"):
                prompt = _mimo_planner_contract() + "\n\n" + prompt
            return chat(system="", user=prompt, provider=provider, temperature=0.4).text

    prompt = build_planner_prompt(
        brief,
        drone_count,
        title=title,
        human_directives=human_directives,
        prior_plan=prior_plan,
        preferences=preferences,
    )
    text = chat_fn(prompt)
    plan = parse_planner_json(text)
    ok, report = (False, "JSON 解析失败，只输出 JSON") if plan is None else validate_music_plan(plan, brief)

    revision = 0
    while not ok and revision < max_revisions:
        revision += 1
        retry_prompt = (
            prompt
            + "\n\n## 上一版输出的问题\n"
            + report
            + ("\n上一版 JSON:\n" + json.dumps(plan, ensure_ascii=False) if plan else "")
        )
        text = chat_fn(retry_prompt)
        plan = parse_planner_json(text)
        ok, report = (False, "JSON 解析失败，只输出 JSON") if plan is None else validate_music_plan(plan, brief)

    if not ok:
        raise ValueError(f"composition plan validation failed: {report}")
    return {"plan": plan, "legacy": to_legacy_plan(plan), "brief": brief}


def _mimo_planner_contract() -> str:
    return (
        "## MIMO 输出纪律（硬要求）\n"
        "- 直接输出最终 JSON 对象；不要写长篇分析、不要复述音乐证据、不要反复自审。\n"
        "- 最多先写 3 行内部计划摘要；随后立刻给 JSON。\n"
        "- JSON 必须能被 parse；不要 markdown fence。输出过长导致超时/截断会视为失败。"
    )
