# -*- coding: utf-8 -*-
# 该文件把用户意图和音乐结构转成场景计划

from __future__ import annotations

from .contracts import FleetSpec, MusicAnalysis, Scene, ScenePlan


def _formation_for_index(idx: int) -> str:
    # 小规模 7 机适合的编队序列模板
    templates = ["line", "arc", "double_triangle", "spiral", "ring", "fan"]
    return templates[idx % len(templates)]


def _motion_style_for_energy(level: str) -> str:
    # 能量等级映射到动作风格
    if level == "low":
        return "smooth_glide"
    if level == "mid":
        return "rhythm_pulse"
    return "strong_expansion"


def build_scene_plan(user_intent: str, analysis: MusicAnalysis, fleet: FleetSpec) -> ScenePlan:
    # 生成从头到尾单调时间的场景列表
    scenes: list[Scene] = []
    for idx, section in enumerate(analysis.sections):
        scenes.append(
            Scene(
                scene_id=f"SC{idx + 1:02d}",
                start=section.start,
                end=section.end,
                formation=_formation_for_index(idx),
                motion_style=_motion_style_for_energy(section.energy),
                transition_style="ease_in_out",
            )
        )
    return ScenePlan(user_intent=user_intent, fleet=fleet, scenes=scenes)
