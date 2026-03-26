# -*- coding: utf-8 -*-
# 该文件编排从自然语言到仿真输出的端到端流程

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .audio_analyzer import analyze_music
from .choreo_planner import build_scene_plan
from .codegen import apply_nl_patch, build_segment_specs, emit_pyfii_program
from .contracts import FleetSpec, to_dict, validate_scene_plan
from .dialogue_manager import DialogueManager, DialogueTurn
from .refiner import refine_segments
from .safety import validate_duration, validate_fleet_rule, validate_segment_specs


@dataclass
class PipelineConfig:
    # 工作流配置：优先固定 F400，以满足本次测试需求
    audio_path: str
    output_dir: str
    user_intent: str
    fleet_type: str = "F400"
    dialogue_history_name: str = "dialogue_history.jsonl"


def _ensure_output_dir(path: str) -> Path:
    # 创建输出目录用于保存中间态与生成脚本
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _fleet_from_config(fleet_type: str) -> FleetSpec:
    # 构建机队规格并确保同构
    if fleet_type == "F600":
        fleet = FleetSpec(drone_count=7, fleet_type="F600", drone_class="Drone6")
    else:
        fleet = FleetSpec(drone_count=7, fleet_type="F400", drone_class="Drone")
    validate_fleet_rule(fleet)
    return fleet


def run_nl_choreo_pipeline(config: PipelineConfig, edit_rounds: list[str] | None = None) -> dict[str, Any]:
    # 主流程：分析 -> 规划 -> 生成 -> 多轮编辑补丁 -> 安全检查 -> 输出脚本
    out_dir = _ensure_output_dir(config.output_dir)
    fleet = _fleet_from_config(config.fleet_type)

    analysis = analyze_music(config.audio_path)
    validate_duration(analysis.duration)

    plan = build_scene_plan(config.user_intent, analysis, fleet)
    validate_scene_plan(plan)

    segments = build_segment_specs(plan)

    dialogue_manager = DialogueManager(out_dir / config.dialogue_history_name)
    rounds = edit_rounds or []
    for idx, patch_text in enumerate(rounds, start=1):
        segments, patch_summary, affected = apply_nl_patch(segments=segments, patch_text=patch_text)
        safety = validate_segment_specs(segments, fleet)
        dialogue_manager.append_turn(
            DialogueTurn(
                turn_id=idx,
                user_edit_text=patch_text,
                affected_segments=affected,
                patch_summary=patch_summary,
                safety_result="ok" if safety.ok else "failed",
                render_refs=[],
            )
        )
        if not safety.ok:
            raise ValueError("safety check failed after dialogue patch")

    # 生成一次脚本并保存结构化中间态
    program_text = emit_pyfii_program(
        output_path=str(out_dir / "nl_choreo_output"),
        fleet=fleet,
        segments=segments,
        program_name="nl_choreo_output",
        music_path=config.audio_path,
    )
    program_file = out_dir / "nl_choreo_generated.py"
    program_file.write_text(program_text, encoding="utf-8")

    (out_dir / "music_analysis.json").write_text(
        json.dumps(to_dict(analysis), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "scene_plan.json").write_text(
        json.dumps(to_dict(plan), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "segment_specs.json").write_text(
        json.dumps([to_dict(s) for s in segments], ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 预留细化接口：目前仅在需要时调用
    _ = refine_segments

    return {
        "analysis_path": str(out_dir / "music_analysis.json"),
        "scene_plan_path": str(out_dir / "scene_plan.json"),
        "segment_specs_path": str(out_dir / "segment_specs.json"),
        "dialogue_history_path": str(out_dir / config.dialogue_history_name),
        "program_path": str(program_file),
        "fleet_type": fleet.fleet_type,
        "drone_class": fleet.drone_class,
    }
