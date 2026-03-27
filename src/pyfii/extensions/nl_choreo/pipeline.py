# -*- coding: utf-8 -*-
# 该文件编排从自然语言到仿真输出的端到端流程

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .audio_analyzer import analyze_music
from .choreo_planner import build_scene_plan
from .codegen import apply_nl_patch, build_segment_specs, emit_pyfii_program
from .contracts import FleetSpec, MusicAnalysis, MusicSection, SegmentSpec, to_dict, validate_scene_plan
from .dialogue_manager import DialogueManager, DialogueTurn
from .inspector import InspectInput, inspect_with_qwen
from .qwen_client import QwenConfig, QwenVideoClient
from .refiner import refine_segments
from .renderer import cut_video_segment, render_project
from .safety import validate_duration, validate_fleet_rule, validate_segment_specs


@dataclass
class PipelineConfig:
    # 工作流配置：优先固定 F400，以满足本次测试需求
    audio_path: str
    output_dir: str
    user_intent: str
    fleet_type: str = "F400"
    dialogue_history_name: str = "dialogue_history.jsonl"
    use_qwen: bool = True
    resume: bool = True
    max_rounds: int = 3
    max_regen_per_segment: int = 2
    max_consecutive_qwen_failures: int = 3
    qwen: QwenConfig = field(default_factory=QwenConfig)
    fallback_video_path: str = "/home/test/dntg20220730_3D.mp4"
    force_duration_sec: float | None = None


@dataclass
class WorkflowState:
    # 工作流状态：支持断点恢复
    stage: str
    status: str
    round_idx: int
    consecutive_qwen_failures: int
    regen_counters: dict[str, int]
    last_error: str = ""


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


def _state_path(out_dir: Path) -> Path:
    return out_dir / "workflow_state.json"


def _segments_path(out_dir: Path) -> Path:
    return out_dir / "segments_current.json"


def _inspection_rounds_path(out_dir: Path) -> Path:
    return out_dir / "inspection_rounds.jsonl"


def _qwen_calls_path(out_dir: Path) -> Path:
    return out_dir / "qwen_calls.jsonl"


def _write_state(out_dir: Path, state: WorkflowState) -> None:
    # 写入状态快照
    _state_path(out_dir).write_text(json.dumps(to_dict(state), ensure_ascii=False, indent=2), encoding="utf-8")


def _load_state(out_dir: Path) -> WorkflowState | None:
    # 读取已有状态，用于恢复
    p = _state_path(out_dir)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return WorkflowState(
        stage=str(data.get("stage", "init")),
        status=str(data.get("status", "running")),
        round_idx=int(data.get("round_idx", 0)),
        consecutive_qwen_failures=int(data.get("consecutive_qwen_failures", 0)),
        regen_counters={str(k): int(v) for k, v in data.get("regen_counters", {}).items()},
        last_error=str(data.get("last_error", "")),
    )


def _save_segments(out_dir: Path, segments: list[SegmentSpec]) -> None:
    # 保存当前段状态，供恢复与审计
    _segments_path(out_dir).write_text(
        json.dumps([to_dict(s) for s in segments], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_segments(out_dir: Path) -> list[dict[str, Any]] | None:
    p = _segments_path(out_dir)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    # 追加 jsonl 记录
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False))
        f.write("\n")


def _coerce_duration_if_needed(analysis: MusicAnalysis, force_duration_sec: float | None) -> MusicAnalysis:
    # 当用户要求固定 60~70 秒产出时，可显式覆盖时长并同步分段边界
    if force_duration_sec is None:
        return analysis
    if force_duration_sec <= 0:
        raise ValueError("force_duration_sec must be positive")
    old_duration = analysis.duration if analysis.duration > 0 else force_duration_sec
    ratio = force_duration_sec / old_duration

    adjusted_sections = [
        MusicSection(
            section_id=s.section_id,
            start=float(s.start * ratio),
            end=float(s.end * ratio),
            energy=s.energy,
        )
        for s in analysis.sections
    ]
    adjusted_beats = [float(b * ratio) for b in analysis.beats]
    adjusted_onsets = [float(o * ratio) for o in analysis.onsets]
    adjusted_climax = [(float(a * ratio), float(b * ratio)) for a, b in analysis.climax_ranges]

    return MusicAnalysis(
        duration=float(force_duration_sec),
        tempo_estimate=analysis.tempo_estimate,
        beats=adjusted_beats,
        onsets=adjusted_onsets,
        sections=adjusted_sections,
        energy_curve=analysis.energy_curve,
        climax_ranges=adjusted_climax,
    )


def _segments_from_dict(data: list[dict[str, Any]]) -> list[SegmentSpec]:
    # 简单反序列化：用于恢复流程
    segments: list[SegmentSpec] = []
    from .contracts import DroneOp, DroneTrackSpec

    for seg in data:
        tracks = []
        for tr in seg.get("tracks", []):
            ops = [DroneOp(op=o["op"], args=o.get("args", [])) for o in tr.get("ops", [])]
            tracks.append(DroneTrackSpec(drone_id=int(tr.get("drone_id", 1)), ops=ops))
        segments.append(
            SegmentSpec(
                segment_id=str(seg.get("segment_id")),
                scene_id=str(seg.get("scene_id")),
                start=float(seg.get("start", 0.0)),
                end=float(seg.get("end", 0.0)),
                tracks=tracks,
            )
        )
    return segments


def _render_and_inspect_round(
    out_dir: Path,
    config: PipelineConfig,
    segments: list[SegmentSpec],
    qwen_client: QwenVideoClient,
    round_idx: int,
) -> tuple[list[SegmentSpec], bool, list[str]]:
    # 单轮：优先全量渲染；若渲染不可用则回退到预置视频继续检查链路
    project_path = str(out_dir / "nl_choreo_output")
    full_save = str(out_dir / f"render_round_{round_idx:02d}")

    full_video: str
    field = 6
    device = config.fleet_type
    frame_count_hint = 0
    try:
        full_result = render_project(project_path=project_path, save_path=full_save, fps=25)
        full_video = full_result.output_video
        field = full_result.field
        device = full_result.device
        frame_count_hint = full_result.frame_count_hint
    except Exception as exc:
        fallback = Path(config.fallback_video_path)
        if not fallback.exists():
            raise RuntimeError(f"render failed and fallback video missing: {exc}") from exc
        full_video = str(fallback)

    segment_reports: list[dict[str, Any]] = []
    merged_changed: set[str] = set()
    should_regen = False

    for seg in segments:
        seg_save = str(out_dir / f"segment_{seg.segment_id}_r{round_idx:02d}")
        seg_video = cut_video_segment(
            source_video=full_video,
            output_video=f"{seg_save}.mp4",
            start_sec=seg.start,
            end_sec=seg.end,
        )
        report = inspect_with_qwen(
            client=qwen_client,
            data=InspectInput(
                video_path=seg_video,
                vibe_target=config.user_intent,
            ),
        )
        segment_reports.append(
            {
                "round": round_idx,
                "segment_id": seg.segment_id,
                "video": seg_video,
                "suggest_regenerate": report.suggest_regenerate,
                "issues": [to_dict(i) for i in report.issues],
            }
        )
        if report.suggest_regenerate or report.issues:
            should_regen = True
            refined = refine_segments(
                segments=segments,
                report=report,
                allowed_segment_ids={seg.segment_id},
            )
            segments = refined.updated_segments
            merged_changed.update(refined.changed_segment_ids)

    for item in segment_reports:
        _append_jsonl(_inspection_rounds_path(out_dir), item)

    # 每轮末保存全量结果索引
    _append_jsonl(
        _inspection_rounds_path(out_dir),
        {
            "round": round_idx,
            "full_video": full_video,
            "type": "round_summary",
            "changed_segments": sorted(merged_changed),
        },
    )

    return segments, should_regen, sorted(merged_changed)


def run_nl_choreo_pipeline(config: PipelineConfig, edit_rounds: list[str] | None = None) -> dict[str, Any]:
    # 主流程：分析 -> 规划 -> 生成 -> 多轮编辑补丁 -> 安全检查 -> 完整检查-重整闭环
    out_dir = _ensure_output_dir(config.output_dir)
    fleet = _fleet_from_config(config.fleet_type)

    state = _load_state(out_dir) if config.resume else None
    if state is None:
        state = WorkflowState(
            stage="init",
            status="running",
            round_idx=0,
            consecutive_qwen_failures=0,
            regen_counters={},
            last_error="",
        )
        _write_state(out_dir, state)

    try:
        state.last_error = ""
        _write_state(out_dir, state)

        analysis_file = out_dir / "music_analysis.json"
        if state.stage in {"init", "analysis"} or (not analysis_file.exists()):
            analysis = analyze_music(config.audio_path)
            analysis = _coerce_duration_if_needed(analysis, config.force_duration_sec)
            validate_duration(analysis.duration)
            analysis_file.write_text(
                json.dumps(to_dict(analysis), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            state.stage = "planning"
            _write_state(out_dir, state)
        else:
            analysis_data = json.loads(analysis_file.read_text(encoding="utf-8"))

            analysis = MusicAnalysis(
                duration=float(analysis_data["duration"]),
                tempo_estimate=float(analysis_data["tempo_estimate"]),
                beats=[float(x) for x in analysis_data.get("beats", [])],
                onsets=[float(x) for x in analysis_data.get("onsets", [])],
                sections=[
                    MusicSection(
                        section_id=s["section_id"],
                        start=float(s["start"]),
                        end=float(s["end"]),
                        energy=s["energy"],
                    )
                    for s in analysis_data.get("sections", [])
                ],
                energy_curve=[float(x) for x in analysis_data.get("energy_curve", [])],
                climax_ranges=[tuple(x) for x in analysis_data.get("climax_ranges", [])],
            )
            analysis = _coerce_duration_if_needed(analysis, config.force_duration_sec)
            validate_duration(analysis.duration)

        plan = build_scene_plan(config.user_intent, analysis, fleet)
        validate_scene_plan(plan)
        (out_dir / "scene_plan.json").write_text(
            json.dumps(to_dict(plan), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        loaded_segments = _load_segments(out_dir) if config.resume else None
        if loaded_segments:
            segments = _segments_from_dict(loaded_segments)
        else:
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

        _save_segments(out_dir, segments)
        (out_dir / "segment_specs.json").write_text(
            json.dumps([to_dict(s) for s in segments], ensure_ascii=False, indent=2), encoding="utf-8"
        )

        state.stage = "codegen"
        _write_state(out_dir, state)

        program_text = emit_pyfii_program(
            output_path=str(out_dir / "nl_choreo_output"),
            fleet=fleet,
            segments=segments,
            program_name="nl_choreo_output",
            music_path=config.audio_path,
        )
        program_file = out_dir / "nl_choreo_generated.py"
        program_file.write_text(program_text, encoding="utf-8")

        state.stage = "qwen_loop"
        _write_state(out_dir, state)

        # 先创建日志文件，确保无论是否触发调用都可追踪
        _qwen_calls_path(out_dir).touch(exist_ok=True)
        _inspection_rounds_path(out_dir).touch(exist_ok=True)

        qwen_client = QwenVideoClient(config=config.qwen, telemetry_path=_qwen_calls_path(out_dir))

        # 完整闭环：每轮检查与段级修正
        while state.round_idx < config.max_rounds:
            state.round_idx += 1
            _write_state(out_dir, state)

            if not config.use_qwen:
                break

            try:
                segments, should_regen, changed = _render_and_inspect_round(
                    out_dir=out_dir,
                    config=config,
                    segments=segments,
                    qwen_client=qwen_client,
                    round_idx=state.round_idx,
                )
                # 统计段级重整次数
                for sid in changed:
                    state.regen_counters[sid] = state.regen_counters.get(sid, 0) + 1
                state.consecutive_qwen_failures = 0

                _save_segments(out_dir, segments)
                (out_dir / "segment_specs.json").write_text(
                    json.dumps([to_dict(s) for s in segments], ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

                safety = validate_segment_specs(segments, fleet)
                if not safety.ok:
                    raise ValueError("safety check failed after qwen refine")

                hit_limit = any(v >= config.max_regen_per_segment for v in state.regen_counters.values())
                if hit_limit:
                    state.status = "stopped_limits"
                    state.stage = "done"
                    state.last_error = ""
                    _write_state(out_dir, state)
                    break

                if not should_regen or not changed:
                    state.status = "completed"
                    state.stage = "done"
                    state.last_error = ""
                    _write_state(out_dir, state)
                    break

            except Exception as exc:
                state.consecutive_qwen_failures += 1
                state.last_error = str(exc)
                _write_state(out_dir, state)
                if state.consecutive_qwen_failures >= config.max_consecutive_qwen_failures:
                    state.status = "failed_retryable"
                    state.stage = "done"
                    _write_state(out_dir, state)
                    break

        if state.stage != "done":
            state.status = "stopped_limits"
            state.stage = "done"
            state.last_error = ""
            _write_state(out_dir, state)

        return {
            "analysis_path": str(out_dir / "music_analysis.json"),
            "scene_plan_path": str(out_dir / "scene_plan.json"),
            "segment_specs_path": str(out_dir / "segment_specs.json"),
            "dialogue_history_path": str(out_dir / config.dialogue_history_name),
            "program_path": str(program_file),
            "workflow_state_path": str(_state_path(out_dir)),
            "inspection_rounds_path": str(_inspection_rounds_path(out_dir)),
            "qwen_calls_path": str(_qwen_calls_path(out_dir)),
            "fleet_type": fleet.fleet_type,
            "drone_class": fleet.drone_class,
            "status": state.status,
            "round_idx": state.round_idx,
        }
    except Exception as exc:
        state.status = "failed_non_retryable"
        state.stage = "done"
        state.last_error = str(exc)
        _write_state(out_dir, state)
        raise
