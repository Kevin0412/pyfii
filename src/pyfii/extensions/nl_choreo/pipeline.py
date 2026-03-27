# -*- coding: utf-8 -*-
# 该文件编排从自然语言到仿真输出的端到端流程

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from math import cos, pi, sin
from pathlib import Path
from typing import Any, Literal

from .audio_analyzer import analyze_music
from .choreo_planner import build_scene_plan
from .codegen import apply_nl_patch, build_segment_specs, emit_pyfii_program
from .contracts import (
    DroneOp,
    DroneTrackSpec,
    FleetSpec,
    MusicAnalysis,
    MusicSection,
    ScenePlan,
    SegmentIssue,
    SegmentSpec,
    to_dict,
    validate_scene_plan,
)
from .dialogue_manager import DialogueManager, DialogueTurn
from .inspector import InspectInput, inspect_with_qwen
from .qwen_client import QwenConfig, QwenVideoClient
from .refiner import refine_segments
from .renderer import cut_video_segment, render_project
from .safety import summarize_render_distance_warnings, validate_duration, validate_fleet_rule, validate_segment_specs


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
    fallback_video_path: str = ""
    force_duration_sec: float | None = None
    strict_render_source: bool = True
    render_fps: int = 30
    direct_python_codegen: bool = True
    max_python_regen_attempts: int = 3
    qwen_action_steps: int = 3
    qwen_step_patch_attempts: int = 2
    direct_fallback_mode: Literal["freeform_seed", "none", "pattern_seed"] = "none"


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


def _log_progress(message: str) -> None:
    # 控制台进度日志：便于长流程运行时观察状态
    print(f"[nl_choreo] {message}", flush=True)


def _freeform_start_positions(count: int) -> list[tuple[int, int]]:
    # 仅用于自由编舞初始脚手架，不绑定固定编队模板
    if count <= 1:
        return [(280, 280)]
    cx, cy = 280.0, 280.0
    radius = 140.0
    pts: list[tuple[int, int]] = []
    for i in range(count):
        ang = (2 * pi * i / count) - (pi / 2)
        x = int(round(cx + radius * cos(ang)))
        y = int(round(cy + radius * sin(ang)))
        pts.append((max(40, min(520, x)), max(40, min(520, y))))
    return pts


def _pyfii_bootstrap_lines() -> list[str]:
    # 兼容两种常见仓库布局，降低 Qwen 代码因导入失败而回退的概率
    return [
        "import os",
        "import sys",
        "",
        "sys.path.append(os.getcwd() + r'/src')",
        "sys.path.append(os.getcwd() + r'/src/pyfii')",
        "",
        "try:",
        "    import pyfii as pf",
        "except Exception:",
        "    from pyfii import pyfii as pf",
        "",
    ]


def _build_freeform_seed_program(
    output_path: str,
    fleet: FleetSpec,
    music_path: str,
    render_fps: int,
) -> str:
    # 极简可运行脚手架：只含起降与渲染，动作由 Qwen 自主改写
    ctor = "pf.Drone" if fleet.fleet_type == "F400" else "pf.Drone6"
    config_name = "pf.drone_config_6m"
    start_positions = _freeform_start_positions(fleet.drone_count)

    lines: list[str] = _pyfii_bootstrap_lines() + [
        "# Qwen 自由编舞初始脚手架（无固定图案库）",
    ]
    for idx in range(fleet.drone_count):
        lines.append(f"d{idx + 1}={ctor}(0,0,{config_name},\"192.168.51.{51 + idx}\")")
    lines.append("")
    lines.append("ds=[" + ",".join([f"d{i+1}" for i in range(fleet.drone_count)]) + "]")
    lines.append(f"start_positions={repr(start_positions)}")
    lines.append("for d,p in zip(ds,start_positions):")
    lines.append("    d.X=p[0]")
    lines.append("    d.Y=p[1]")
    lines.append("    d.takeoff(1,80)")
    lines.append("")
    lines.append("for d in ds:")
    lines.append("    d.inittime(4)")
    lines.append("    d.VelXY(120,240)")
    lines.append("    d.VelZ(120,240)")
    lines.append("    d.move2(d.X,d.Y,100)")
    lines.append("")
    lines.append("for d in ds:")
    lines.append("    d.land()")
    lines.append("    d.end()")
    lines.append("")
    lines.append(f"name='{output_path}'")
    lines.append("F=pf.Fii(name,ds,music='" + music_path + "')")
    lines.append("F.save()")
    lines.append("data,t0,music,field,device=pf.read_fii(name)")
    lines.append(f"pf.show(data,t0,music,field=field,device=device,save=name,FPS={max(10, int(render_fps))})")
    return "\n".join(lines) + "\n"


def _build_minimal_segments_from_plan(plan: ScenePlan, fleet: FleetSpec) -> list[SegmentSpec]:
    # 仅为检查/分段闭环提供最小结构，不注入固定编队模板
    segments: list[SegmentSpec] = []
    anchors = _freeform_start_positions(fleet.drone_count)
    z_base = 90 if fleet.fleet_type == "F400" else 110
    for s_idx, scene in enumerate(plan.scenes):
        tracks: list[DroneTrackSpec] = []
        delay_ms = max(100, int((scene.end - scene.start) * 1000) - 800)
        for d_idx in range(fleet.drone_count):
            x0, y0 = anchors[d_idx]
            x = max(0, min(560, x0 + (10 * ((s_idx + d_idx) % 3 - 1))))
            y = max(0, min(560, y0 + (10 * ((s_idx * 2 + d_idx) % 3 - 1))))
            z = max(80 if fleet.fleet_type == "F400" else 100, min(250, z_base + (d_idx % 3) * 8))
            tracks.append(
                DroneTrackSpec(
                    drone_id=d_idx + 1,
                    ops=[
                        DroneOp(op="inittime", args=[int(scene.start)]),
                        DroneOp(op="VelXY", args=[120, 240]),
                        DroneOp(op="VelZ", args=[120, 240]),
                        DroneOp(op="move2", args=[int(x), int(y), int(z)]),
                        DroneOp(op="delay", args=[delay_ms]),
                    ],
                )
            )
        segments.append(
            SegmentSpec(
                segment_id=f"SG{s_idx + 1:02d}",
                scene_id=scene.scene_id,
                start=scene.start,
                end=scene.end,
                tracks=tracks,
            )
        )
    return segments


def _build_direct_edit_patch_prompt(current_code: str, edit_text: str, expected_fps: int) -> str:
    return (
        "请根据用户编辑要求修改下面 pyfii 脚本，并返回完整代码（只输出代码）。\n"
        "硬约束：\n"
        "1) 首个 inittime >= 4 且不回退。\n"
        "2) 每次 move2 前必须先 VelXY 和 VelZ。\n"
        "3) 保留结尾 land + end。\n"
        f"4) 使用 FPS={expected_fps}。\n"
        f"用户编辑: {edit_text}\n"
        "当前脚本:\n"
        "```python\n"
        f"{current_code}\n"
        "```\n"
    )


def _choose_direct_seed_program(
    config: PipelineConfig,
    deterministic_seed_program_text: str | None,
    fleet: FleetSpec,
) -> str | None:
    # direct_fallback_mode 仅决定 direct 模式最终兜底是否注入 pattern seed
    if config.direct_fallback_mode == "pattern_seed":
        return deterministic_seed_program_text
    if config.direct_fallback_mode == "freeform_seed":
        return _build_freeform_seed_program(
            output_path=str(Path(config.output_dir) / "nl_choreo_output"),
            fleet=fleet,
            music_path=config.audio_path,
            render_fps=max(40, int(config.render_fps)),
        )
    return None


def _ensure_render_project(out_dir: Path, program_file: Path, force: bool = False) -> None:
    # 执行生成脚本，确保输出目录中的 .fii 与渲染输入工件存在
    project_dir = out_dir / "nl_choreo_output"
    if project_dir.exists() and not force:
        return
    proc = subprocess.run(
        [sys.executable, str(program_file)],
        cwd=str(Path.cwd()),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"generated program execution failed: {proc.stderr.strip()}")
    if not project_dir.exists():
        raise RuntimeError("generated program finished but nl_choreo_output is missing")


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


def _normalize_report_segment_ids(report: Any, current_segment_id: str) -> Any:
    # 将无效段号归一到当前段，避免 SG00 等导致重整失效
    normalized_issues: list[SegmentIssue] = []
    for issue in report.issues:
        sid = issue.segment_id
        if sid == "SG00":
            sid = current_segment_id
        normalized_issues.append(
            SegmentIssue(
                segment_id=sid,
                severity=issue.severity,
                detail=issue.detail,
                recommendation_zh=issue.recommendation_zh,
            )
        )
    report.issues = normalized_issues
    return report


def _is_qwen_video_decode_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "video_reader.cc" in msg
        or "cannot find video stream" in msg
        or "error while loading video data" in msg
        or "st_nb >= 0" in msg
    )


def _strip_markdown_code_fence(text: str) -> str:
    # 清理 LLM 返回的 markdown 包裹，只保留 python 正文
    t = text.strip()
    m = re.match(r"^```(?:python)?\s*([\s\S]*?)\s*```$", t, flags=re.IGNORECASE)
    if m:
        t = m.group(1).strip()
    else:
        t = t

    # 某些模型会输出前导解释文本，截取首个 import/from/赋值风格代码起点
    marker = re.search(r"(?:^|\n)(?:import\s+|from\s+\w+\s+import\s+|path\s*=|d1\s*=)", t)
    if marker:
        t = t[marker.start() :]

    return t + ("\n" if not t.endswith("\n") else "")


def _normalize_generated_program_text(program_text: str, expected_fps: int) -> str:
    # 兼容 intime 写法，并补齐 FPS
    normalized = program_text
    normalized = re.sub(r"\.intime\(", ".inittime(", normalized)
    if f"FPS={expected_fps}" not in normalized:
        normalized = re.sub(
            r"FPS\s*=\s*\d+",
            f"FPS={expected_fps}",
            normalized,
        )

    if "import pyfii as pf" in normalized and "sys.path.append(os.getcwd() + r'/src/pyfii')" not in normalized:
        lines = normalized.splitlines()
        insert_at = 0
        for i, ln in enumerate(lines[:16]):
            if ln.startswith("import ") or ln.startswith("from ") or ln.strip() == "":
                insert_at = i + 1
        bootstrap = [
            "sys.path.append(os.getcwd() + r'/src')",
            "sys.path.append(os.getcwd() + r'/src/pyfii')",
        ]
        lines[insert_at:insert_at] = bootstrap
        normalized = "\n".join(lines) + "\n"

    # 仅在顶层导入语句出现时替换，避免误替换 try 块中的已缩进语句
    normalized = re.sub(
        r"(?m)^import\s+pyfii\s+as\s+pf\s*$",
        "try:\n    import pyfii as pf\nexcept Exception:\n    from pyfii import pyfii as pf",
        normalized,
    )
    return normalized


def _validate_generated_program_text(program_text: str, expected_fps: int) -> list[str]:
    # 代码级快速安全门：时间单调、首动作时刻、关键动作完整性 + 基础编舞质量约束
    errors: list[str] = []
    lower = program_text.lower()

    required_tokens = ["takeoff(", ".velxy(", ".velz(", ".move2(", ".land()", ".end()"]
    for token in required_tokens:
        if token not in lower:
            errors.append(f"missing required action token: {token}")

    times = [int(x) for x in re.findall(r"\.inittime\((\d+)\)", program_text)]
    if times:
        if min(times) < 4:
            errors.append(f"first inittime must be >= 4, got min={min(times)}")
        for i in range(1, len(times)):
            if times[i] < times[i - 1]:
                errors.append(
                    f"inittime must be monotonic non-decreasing: {times[i - 1]} -> {times[i]} at index {i}"
                )
                break

    if f"FPS={expected_fps}" not in program_text:
        errors.append(f"missing target FPS setting: FPS={expected_fps}")

    # 至少应有多段 move2，避免“起飞后仅一次动作”的空洞脚本
    move2_calls = len(re.findall(r"\.move2\(", lower))
    if move2_calls < 3:
        errors.append(f"insufficient choreography complexity: move2 calls={move2_calls}, require >=3")

    # 禁止盲目同路径：for d in ds 内直接 move2(d.X,d.Y,...) 风险极高
    if re.search(r"for\s+\w+\s+in\s+ds\s*:[\s\S]{0,220}?\.move2\(\s*\w+\.x\s*,\s*\w+\.y\s*,", lower):
        errors.append("unsafe same-path pattern: blind loop move2(d.X,d.Y,...) detected")

    # 若使用常量 move2 目标，至少应有 2 组不同目标，避免全体同目标
    literal_targets = re.findall(r"\.move2\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)", lower)
    if literal_targets and len(set(literal_targets)) < 2:
        errors.append("insufficient target diversity: all literal move2 targets are identical")

    return errors


def _build_direct_codegen_prompt(
    config: PipelineConfig,
    fleet: FleetSpec,
    analysis: MusicAnalysis,
    output_path: str,
    music_path: str,
    render_fps: int,
    current_script: str | None,
) -> str:
    # 直接代码生成提示词：不注入固定编队模板，仅给安全/运行硬约束与上下文
    analysis_payload = json.dumps(to_dict(analysis), ensure_ascii=False)
    prompt = (
        "你是 pyfii 编舞工程师。请基于输入上下文生成完整可执行 Python 脚本（只输出代码）。\n"
        "硬约束：\n"
        "1) 首个 inittime 必须 >= 4。\n"
        "2) 全部 inittime 必须单调不回退。\n"
        "3) 每次 move2 前必须先 VelXY 和 VelZ。\n"
        "4) 结尾必须 land + end。\n"
        "5) 输出 fps 必须使用 FPS="
        f"{render_fps}。\n"
        "6) 保持 6m 场地安全余量，避免明显碰撞风险。\n"
        "7) 优先原创编队与高频动作变化，不要套固定图案库。\n"
        "8) 严禁全机同路径、同目标点同步飞行（现实高风险）。\n"
        "9) 至少 3 个不同 inittime 的动作层，且每层要有可见队形变化。\n"
        "\n"
        f"用户意图: {config.user_intent}\n"
        f"机队: {to_dict(fleet)}\n"
        f"音乐分析: {analysis_payload}\n"
        f"输出目录: {output_path}\n"
        f"音乐路径: {music_path}\n"
    )
    if current_script:
        prompt += (
            "\n"
            "当前脚本（可在此基础上重写/增强）：\n"
            "```python\n"
            f"{current_script}\n"
            "```\n"
        )
    prompt += "请直接返回完整 Python 代码，不要额外解释。"
    return prompt


def _build_codegen_fix_prompt(previous_code: str, errors: list[str]) -> str:
    # 根据失败原因回传修复指令，要求返回完整代码
    errs = "\n".join([f"- {e}" for e in errors])
    return (
        "请修复下面 pyfii Python 脚本，并返回完整修复后代码（只输出代码）。\n"
        "必须修复以下问题：\n"
        f"{errs}\n\n"
        "强约束（必须同时满足）：\n"
        "1) 严禁所有无人机共享同一路径或同一目标点。\n"
        "2) 至少包含 3 个时间层（3 个不同 inittime）和明显编队变化。\n"
        "3) 每个动作层至少 2 组不同目标坐标。\n"
        "4) move2 前必须 VelXY + VelZ；保留 land+end；保留正确 FPS。\n\n"
        "脚本如下：\n"
        "```python\n"
        f"{previous_code}\n"
        "```"
    )


def _build_action_plan_prompt(config: PipelineConfig, analysis: MusicAnalysis, total_steps: int) -> str:
    # 先让 Qwen 规划动作步骤，再按步骤写代码
    analysis_payload = json.dumps(to_dict(analysis), ensure_ascii=False)
    return (
        "你是 pyfii 编舞总导演。先做动作分步规划，不写完整代码。\n"
        f"将本次编舞拆成 {total_steps} 步，每一步写 1 行：StepN: 该步的编队变化与动作目标。\n"
        "要求动作频繁、队形变化明显、转场有层次。\n"
        "返回纯文本步骤列表。\n"
        f"用户意图: {config.user_intent}\n"
        f"音乐分析: {analysis_payload}\n"
    )


def _build_action_step_prompt(
    config: PipelineConfig,
    fleet: FleetSpec,
    analysis: MusicAnalysis,
    step_plan_text: str,
    step_idx: int,
    total_steps: int,
    current_code: str,
    expected_fps: int,
) -> str:
    # 要求 Qwen 仅返回完整脚本（在当前脚本基础上加一步动作）
    analysis_payload = json.dumps(to_dict(analysis), ensure_ascii=False)
    return (
        "你是 pyfii 编舞工程师。请基于当前脚本追加/修改一步动作，返回完整 Python 代码。\n"
        "硬约束：\n"
        "1) takeoff 后首个 inittime>=4；inittime 不回退。\n"
        "2) move2 前必须 VelXY 和 VelZ。\n"
        "3) 保留结尾 land+end。\n"
        "4) 动作要比上一版更丰富，且本步至少新增一次队形变化。\n"
        "4.1) 严禁全机同路径/同目标点；至少分成 2 组以上目标。\n"
        f"5) 必须使用 FPS={expected_fps}。\n"
        "6) 不要输出解释，只输出完整代码。\n"
        f"用户意图: {config.user_intent}\n"
        f"机队: {to_dict(fleet)}\n"
        f"音乐分析: {analysis_payload}\n"
        f"总步数: {total_steps}, 当前步: {step_idx}\n"
        "动作分步规划:\n"
        f"{step_plan_text}\n"
        "当前脚本:\n"
        "```python\n"
        f"{current_code}\n"
        "```"
    )


def _generate_safe_program_with_qwen(
    out_dir: Path,
    qwen_client: QwenVideoClient,
    prompt_zh: str,
    max_attempts: int,
    expected_fps: int,
    program_file: Path,
) -> str:
    # 代码生成-执行闭环：若不安全/不可执行则把问题回传给 Qwen 修复
    prompt = prompt_zh
    last_errors: list[str] = ["unknown generation failure"]

    for _ in range(max(1, int(max_attempts))):
        candidate_raw = qwen_client.generate_python_code(prompt)
        candidate = _strip_markdown_code_fence(candidate_raw)
        candidate = _normalize_generated_program_text(candidate, expected_fps=expected_fps)

        static_errors = _validate_generated_program_text(candidate, expected_fps=expected_fps)
        if static_errors:
            last_errors = static_errors
            prompt = _build_codegen_fix_prompt(candidate, static_errors)
            continue

        program_file.write_text(candidate, encoding="utf-8")
        try:
            _ensure_render_project(out_dir, program_file, force=True)
            return candidate
        except Exception as exc:
            last_errors = [f"program execution/render failed: {exc}"]
            prompt = _build_codegen_fix_prompt(candidate, last_errors)

    raise RuntimeError("qwen direct codegen failed after retries: " + "; ".join(last_errors))


def _apply_direct_edit_rounds(
    current_code: str,
    rounds: list[str],
    qwen_client: QwenVideoClient,
    expected_fps: int,
    dialogue_manager: DialogueManager,
    out_dir: Path,
    program_file: Path,
) -> str:
    patched = current_code
    for idx, patch_text in enumerate(rounds, start=1):
        prompt = _build_direct_edit_patch_prompt(
            current_code=patched,
            edit_text=patch_text,
            expected_fps=expected_fps,
        )
        summary = "direct patch applied"
        safety_result = "ok"
        try:
            patched = _generate_safe_program_with_qwen(
                out_dir=out_dir,
                qwen_client=qwen_client,
                prompt_zh=prompt,
                max_attempts=2,
                expected_fps=expected_fps,
                program_file=program_file,
            )
        except Exception as exc:
            summary = f"direct patch failed: {exc}"
            safety_result = "failed"
        dialogue_manager.append_turn(
            DialogueTurn(
                turn_id=idx,
                user_edit_text=patch_text,
                affected_segments=[],
                patch_summary=summary,
                safety_result=safety_result,
                render_refs=[],
            )
        )
    return patched


def _generate_program_stepwise_with_qwen(
    out_dir: Path,
    qwen_client: QwenVideoClient,
    config: PipelineConfig,
    fleet: FleetSpec,
    analysis: MusicAnalysis,
    seed_program_text: str,
    expected_fps: int,
    program_file: Path,
) -> str:
    # 动作级迭代生成：先规划步骤，再逐步改写完整脚本并执行反馈
    current_code = seed_program_text
    program_file.write_text(current_code, encoding="utf-8")
    _ensure_render_project(out_dir, program_file, force=True)

    try:
        step_plan_text = qwen_client.generate_python_code(
            _build_action_plan_prompt(config=config, analysis=analysis, total_steps=max(1, int(config.qwen_action_steps)))
        )
    except Exception:
        step_plan_text = "Step1: 强化队形变化并增加动作频率"

    for step_idx in range(1, max(1, int(config.qwen_action_steps)) + 1):
        _log_progress(f"direct step {step_idx}/{config.qwen_action_steps}")
        step_prompt = _build_action_step_prompt(
            config=config,
            fleet=fleet,
            analysis=analysis,
            step_plan_text=step_plan_text,
            step_idx=step_idx,
            total_steps=max(1, int(config.qwen_action_steps)),
            current_code=current_code,
            expected_fps=expected_fps,
        )
        prompt = step_prompt
        step_ok = False
        last_errors: list[str] = []

        for attempt in range(1, max(1, int(config.qwen_step_patch_attempts)) + 1):
            try:
                candidate_raw = qwen_client.generate_python_code(prompt)
                candidate = _strip_markdown_code_fence(candidate_raw)
                candidate = _normalize_generated_program_text(candidate, expected_fps=expected_fps)
                static_errors = _validate_generated_program_text(candidate, expected_fps=expected_fps)
                if static_errors:
                    last_errors = static_errors
                    prompt = _build_codegen_fix_prompt(candidate, static_errors)
                    continue

                program_file.write_text(candidate, encoding="utf-8")
                _ensure_render_project(out_dir, program_file, force=True)
                step_file = out_dir / f"nl_choreo_step_{step_idx:02d}.py"
                step_file.write_text(candidate, encoding="utf-8")
                _append_jsonl(
                    _inspection_rounds_path(out_dir),
                    {
                        "type": "direct_codegen_step",
                        "step": step_idx,
                        "attempt": attempt,
                        "ok": True,
                        "step_file": str(step_file),
                    },
                )
                current_code = candidate
                step_ok = True
                break
            except Exception as exc:
                last_errors = [f"step execution failed: {exc}"]
                prompt = _build_codegen_fix_prompt(candidate if 'candidate' in locals() else current_code, last_errors)

        if not step_ok:
            _append_jsonl(
                _inspection_rounds_path(out_dir),
                {
                    "type": "direct_codegen_step",
                    "step": step_idx,
                    "ok": False,
                    "errors": last_errors,
                },
            )
            break

    program_file.write_text(current_code, encoding="utf-8")
    _ensure_render_project(out_dir, program_file, force=True)
    return current_code


def _render_full_videos(out_dir: Path, config: PipelineConfig, tag: str) -> tuple[str, str, bool, int, str, int, list[str]]:
    # 渲染完整 2D/3D 成片并返回索引信息
    project_path = str(out_dir / "nl_choreo_output")
    full_save = str(out_dir / tag)
    field = 6
    device = config.fleet_type
    frame_count_hint = 0
    render_warnings: list[str] = []

    try:
        full_result_2d = render_project(
            project_path=project_path,
            save_path=full_save,
            fps=max(10, int(config.render_fps)),
            three_d=False,
        )
        full_result_3d = render_project(
            project_path=project_path,
            save_path=f"{full_save}_3d",
            fps=max(10, int(config.render_fps)),
            three_d=True,
        )
        full_video_2d = full_result_2d.output_video
        full_video_3d = full_result_3d.output_video
        field = full_result_2d.field
        device = full_result_2d.device
        frame_count_hint = full_result_2d.frame_count_hint
        render_warnings = full_result_2d.warnings + full_result_3d.warnings
        return full_video_2d, full_video_3d, False, field, device, frame_count_hint, render_warnings
    except Exception as exc:
        if not str(config.fallback_video_path).strip():
            raise RuntimeError(f"render failed without fallback video: {exc}") from exc
        fallback = Path(config.fallback_video_path)
        if not fallback.exists():
            raise RuntimeError(f"render failed and fallback video missing: {exc}") from exc
        full_video_2d = str(fallback)
        full_video_3d = str(fallback)
        return full_video_2d, full_video_3d, True, field, device, frame_count_hint, render_warnings


def _render_and_inspect_round(
    out_dir: Path,
    config: PipelineConfig,
    segments: list[SegmentSpec],
    qwen_client: QwenVideoClient,
    round_idx: int,
    frozen_segment_ids: set[str] | None = None,
) -> tuple[list[SegmentSpec], bool, list[str], bool, str, str]:
    # 单轮：优先全量渲染；若渲染不可用则回退到预置视频继续检查链路
    (
        full_video_2d,
        full_video_3d,
        fallback_used,
        field,
        device,
        frame_count_hint,
        render_warnings,
    ) = _render_full_videos(out_dir=out_dir, config=config, tag=f"render_round_{round_idx:02d}")

    segment_reports: list[dict[str, Any]] = []
    merged_changed: set[str] = set()
    should_regen = False
    frozen = frozen_segment_ids or set()

    for seg in segments:
        if seg.segment_id in frozen:
            segment_reports.append(
                {
                    "round": round_idx,
                    "segment_id": seg.segment_id,
                    "video_2d": "",
                    "video_3d": "",
                    "suggest_regenerate": False,
                    "issues": [],
                    "frozen": True,
                }
            )
            continue
        seg_save = str(out_dir / f"segment_{seg.segment_id}_r{round_idx:02d}")
        seg_video_2d = cut_video_segment(
            source_video=full_video_2d,
            output_video=f"{seg_save}_2d.mp4",
            start_sec=seg.start,
            end_sec=seg.end,
        )
        seg_video_3d = cut_video_segment(
            source_video=full_video_3d,
            output_video=f"{seg_save}_3d.mp4",
            start_sec=seg.start,
            end_sec=seg.end,
        )
        try:
            report = inspect_with_qwen(
                client=qwen_client,
                data=InspectInput(
                    video_path=seg_video_2d,
                    vibe_target=config.user_intent,
                    video_paths=[seg_video_2d, seg_video_3d],
                ),
            )
        except Exception as exc:
            if not _is_qwen_video_decode_error(exc):
                raise
            # sglang 视频解码故障降级：保留本轮渲染结果，跳过该段 inspect 触发
            report = type("_R", (), {"issues": [], "suggest_regenerate": False})()
            segment_reports.append(
                {
                    "round": round_idx,
                    "segment_id": seg.segment_id,
                    "video_2d": seg_video_2d,
                    "video_3d": seg_video_3d,
                    "suggest_regenerate": False,
                    "issues": [],
                    "actionable_change": False,
                    "inspect_degraded": True,
                    "inspect_error": str(exc),
                }
            )
            continue
        report = _normalize_report_segment_ids(report, seg.segment_id)
        refined = refine_segments(
            segments=segments,
            report=report,
            allowed_segment_ids={seg.segment_id},
        )
        changed_local = bool(refined.changed_segment_ids)
        segments = refined.updated_segments
        if changed_local:
            should_regen = True
            merged_changed.update(refined.changed_segment_ids)

        segment_reports.append(
            {
                "round": round_idx,
                "segment_id": seg.segment_id,
                "video_2d": seg_video_2d,
                "video_3d": seg_video_3d,
                "suggest_regenerate": report.suggest_regenerate,
                "issues": [to_dict(i) for i in report.issues],
                "actionable_change": changed_local,
            }
        )

    for item in segment_reports:
        _append_jsonl(_inspection_rounds_path(out_dir), item)

    # 每轮末保存全量结果索引
    _append_jsonl(
        _inspection_rounds_path(out_dir),
        {
            "round": round_idx,
            "full_video_2d": full_video_2d,
            "full_video_3d": full_video_3d,
            "fallback_used": fallback_used,
            "type": "round_summary",
            "changed_segments": sorted(merged_changed),
            "render_distance_warning_summary": summarize_render_distance_warnings(render_warnings),
            "field": field,
            "device": device,
            "frame_count_hint": frame_count_hint,
        },
    )

    return segments, should_regen, sorted(merged_changed), fallback_used, full_video_2d, full_video_3d


def run_nl_choreo_pipeline(config: PipelineConfig, edit_rounds: list[str] | None = None) -> dict[str, Any]:
    # 主流程：分析 -> 规划 -> 生成 -> 多轮编辑补丁 -> 安全检查 -> 完整检查-重整闭环
    _log_progress("pipeline start")
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
            _log_progress("analyzing music")
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

        _log_progress("building scene plan")
        plan = build_scene_plan(config.user_intent, analysis, fleet)
        validate_scene_plan(plan)
        (out_dir / "scene_plan.json").write_text(
            json.dumps(to_dict(plan), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        dialogue_manager = DialogueManager(out_dir / config.dialogue_history_name)
        loaded_segments = _load_segments(out_dir) if config.resume else None
        if loaded_segments:
            segments = _segments_from_dict(loaded_segments)
        else:
            if config.direct_python_codegen:
                segments = _build_minimal_segments_from_plan(plan, fleet)
            else:
                segments = build_segment_specs(plan)

            rounds = edit_rounds or []
            if rounds and (not (config.direct_python_codegen and config.use_qwen)):
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
        _log_progress("entering codegen stage")

        # 先创建日志文件，确保无论是否触发调用都可追踪
        _qwen_calls_path(out_dir).touch(exist_ok=True)
        _inspection_rounds_path(out_dir).touch(exist_ok=True)

        qwen_client = QwenVideoClient(config=config.qwen, telemetry_path=_qwen_calls_path(out_dir))
        _append_jsonl(
            _qwen_calls_path(out_dir),
            {
                "type": "pipeline_config",
                "use_local_video_path": bool(config.qwen.use_local_video_path),
                "local_video_mode": str(config.qwen.local_video_mode),
                "inspect_auto_fallback_to_upload": bool(config.qwen.inspect_auto_fallback_to_upload),
            },
        )
        program_file = out_dir / "nl_choreo_generated.py"

        deterministic_seed_program_text: str | None = None
        if (not config.direct_python_codegen) or config.direct_fallback_mode == "pattern_seed":
            deterministic_seed_program_text = emit_pyfii_program(
                output_path=str(out_dir / "nl_choreo_output"),
                fleet=fleet,
                segments=segments,
                program_name="nl_choreo_output",
                music_path=config.audio_path,
                render_fps=max(40, int(config.render_fps)),
            )

        if config.direct_python_codegen:
            seed_program_text = _build_freeform_seed_program(
                output_path=str(out_dir / "nl_choreo_output"),
                fleet=fleet,
                music_path=config.audio_path,
                render_fps=max(40, int(config.render_fps)),
            )
        else:
            if deterministic_seed_program_text is None:
                raise RuntimeError("deterministic seed unavailable")
            seed_program_text = deterministic_seed_program_text

        if config.direct_python_codegen and config.use_qwen:
            _log_progress("direct mode: iterative action-by-action generation")
            try:
                program_text = _generate_program_stepwise_with_qwen(
                    out_dir=out_dir,
                    qwen_client=qwen_client,
                    config=config,
                    fleet=fleet,
                    analysis=analysis,
                    seed_program_text=seed_program_text,
                    expected_fps=max(40, int(config.render_fps)),
                    program_file=program_file,
                )
            except Exception:
                _log_progress("direct mode stepwise failed, fallback to one-shot full script")
                prompt_zh = _build_direct_codegen_prompt(
                    config=config,
                    fleet=fleet,
                    analysis=analysis,
                    output_path=str(out_dir / "nl_choreo_output"),
                    music_path=config.audio_path,
                    render_fps=max(40, int(config.render_fps)),
                    current_script=program_text if "program_text" in locals() else seed_program_text,
                )
                try:
                    program_text = _generate_safe_program_with_qwen(
                        out_dir=out_dir,
                        qwen_client=qwen_client,
                        prompt_zh=prompt_zh,
                        max_attempts=config.max_python_regen_attempts,
                        expected_fps=max(40, int(config.render_fps)),
                        program_file=program_file,
                    )
                except Exception:
                    fallback_seed = _choose_direct_seed_program(
                        config=config,
                        deterministic_seed_program_text=deterministic_seed_program_text,
                        fleet=fleet,
                    )
                    if fallback_seed is None:
                        raise
                    _log_progress("direct mode fallback: use configured direct seed")
                    program_text = fallback_seed
                    program_file.write_text(program_text, encoding="utf-8")
                    _ensure_render_project(out_dir, program_file, force=True)

            rounds = edit_rounds or []
            if rounds:
                program_text = _apply_direct_edit_rounds(
                    current_code=program_text,
                    rounds=rounds,
                    qwen_client=qwen_client,
                    expected_fps=max(40, int(config.render_fps)),
                    dialogue_manager=dialogue_manager,
                    out_dir=out_dir,
                    program_file=program_file,
                )
        else:
            program_text = seed_program_text
            program_file.write_text(program_text, encoding="utf-8")
            _ensure_render_project(out_dir, program_file)

        state.stage = "qwen_loop"
        _write_state(out_dir, state)

        last_full_video_2d = ""
        last_full_video_3d = ""

        # 完整闭环：每轮检查与段级修正
        while state.round_idx < config.max_rounds:
            state.round_idx += 1
            _write_state(out_dir, state)
            _log_progress(f"inspection round {state.round_idx}/{config.max_rounds}")

            if not config.use_qwen:
                break

            try:
                frozen_segment_ids = {
                    sid for sid, cnt in state.regen_counters.items() if cnt >= config.max_regen_per_segment
                }
                segments, should_regen, changed, fallback_used, full_video_2d, full_video_3d = _render_and_inspect_round(
                    out_dir=out_dir,
                    config=config,
                    segments=segments,
                    qwen_client=qwen_client,
                    round_idx=state.round_idx,
                    frozen_segment_ids=frozen_segment_ids,
                )
                last_full_video_2d = full_video_2d
                last_full_video_3d = full_video_3d
                # 统计段级重整次数
                if fallback_used and config.strict_render_source:
                    raise RuntimeError("render fallback used in strict mode")

                for sid in changed:
                    state.regen_counters[sid] = state.regen_counters.get(sid, 0) + 1
                state.consecutive_qwen_failures = 0

                _save_segments(out_dir, segments)
                (out_dir / "segment_specs.json").write_text(
                    json.dumps([to_dict(s) for s in segments], ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

                if changed:
                    deterministic_seed_program_text_round: str | None = None
                    if (not config.direct_python_codegen) or config.direct_fallback_mode == "pattern_seed":
                        deterministic_seed_program_text_round = emit_pyfii_program(
                            output_path=str(out_dir / "nl_choreo_output"),
                            fleet=fleet,
                            segments=segments,
                            program_name="nl_choreo_output",
                            music_path=config.audio_path,
                            render_fps=max(40, int(config.render_fps)),
                        )
                    if config.direct_python_codegen:
                        seed_program_text = _build_freeform_seed_program(
                            output_path=str(out_dir / "nl_choreo_output"),
                            fleet=fleet,
                            music_path=config.audio_path,
                            render_fps=max(40, int(config.render_fps)),
                        )
                    else:
                        if deterministic_seed_program_text_round is None:
                            raise RuntimeError("deterministic round seed unavailable")
                        seed_program_text = deterministic_seed_program_text_round
                    if config.direct_python_codegen:
                        try:
                            program_text = _generate_program_stepwise_with_qwen(
                                out_dir=out_dir,
                                qwen_client=qwen_client,
                                config=config,
                                fleet=fleet,
                                analysis=analysis,
                                seed_program_text=seed_program_text,
                                expected_fps=max(40, int(config.render_fps)),
                                program_file=program_file,
                            )
                        except Exception:
                            prompt_zh = _build_direct_codegen_prompt(
                                config=config,
                                fleet=fleet,
                                analysis=analysis,
                                output_path=str(out_dir / "nl_choreo_output"),
                                music_path=config.audio_path,
                                render_fps=max(40, int(config.render_fps)),
                                current_script=program_text if "program_text" in locals() else seed_program_text,
                            )
                            try:
                                program_text = _generate_safe_program_with_qwen(
                                    out_dir=out_dir,
                                    qwen_client=qwen_client,
                                    prompt_zh=prompt_zh,
                                    max_attempts=config.max_python_regen_attempts,
                                    expected_fps=max(40, int(config.render_fps)),
                                    program_file=program_file,
                                )
                            except Exception:
                                fallback_seed = _choose_direct_seed_program(
                                    config=config,
                                    deterministic_seed_program_text=deterministic_seed_program_text,
                                    fleet=fleet,
                                )
                                if fallback_seed is None:
                                    raise
                                program_text = fallback_seed
                                program_file.write_text(program_text, encoding="utf-8")
                                _ensure_render_project(out_dir, program_file, force=True)
                    else:
                        program_text = seed_program_text
                        program_file.write_text(program_text, encoding="utf-8")
                        _ensure_render_project(out_dir, program_file, force=True)

                safety = validate_segment_specs(segments, fleet)
                if not safety.ok:
                    raise ValueError("safety check failed after qwen refine")

                if not should_regen or not changed:
                    state.status = "completed"
                    state.stage = "done"
                    state.last_error = ""
                    _write_state(out_dir, state)
                    break

                hit_limit = any(v >= config.max_regen_per_segment for v in state.regen_counters.values())
                if hit_limit:
                    saturated_ids = {sid for sid, cnt in state.regen_counters.items() if cnt >= config.max_regen_per_segment}
                    if all(seg.segment_id in saturated_ids for seg in segments):
                        state.status = "stopped_limits"
                        state.stage = "done"
                        state.last_error = ""
                        _write_state(out_dir, state)
                        break

            except Exception as exc:
                state.consecutive_qwen_failures += 1
                state.last_error = str(exc)
                if "render fallback used in strict mode" in state.last_error:
                    state.status = "failed_retryable"
                    state.stage = "done"
                    _write_state(out_dir, state)
                    break
                _write_state(out_dir, state)
                if state.consecutive_qwen_failures >= config.max_consecutive_qwen_failures:
                    state.status = "failed_retryable"
                    state.stage = "done"
                    _write_state(out_dir, state)
                    break

        if state.stage != "done":
            state.status = "stopped_max_rounds"
            state.stage = "done"
            state.last_error = ""
            _write_state(out_dir, state)

        _log_progress("rendering final 2D/3D videos")
        (
            final_full_video_2d,
            final_full_video_3d,
            final_fallback_used,
            final_field,
            final_device,
            final_frame_count_hint,
            final_render_warnings,
        ) = _render_full_videos(out_dir=out_dir, config=config, tag="render_final")
        if final_fallback_used and config.strict_render_source:
            state.status = "failed_retryable"
            state.stage = "done"
            state.last_error = "final render fallback used in strict mode"
            _write_state(out_dir, state)
        _append_jsonl(
            _inspection_rounds_path(out_dir),
            {
                "type": "final_summary",
                "final_full_video_2d": final_full_video_2d,
                "final_full_video_3d": final_full_video_3d,
                "fallback_used": final_fallback_used,
                "render_distance_warning_summary": summarize_render_distance_warnings(final_render_warnings),
                "field": final_field,
                "device": final_device,
                "frame_count_hint": final_frame_count_hint,
                "render_fps": max(10, int(config.render_fps)),
            },
        )
        if not last_full_video_2d:
            last_full_video_2d = final_full_video_2d
        if not last_full_video_3d:
            last_full_video_3d = final_full_video_3d

        _log_progress(f"pipeline done: status={state.status}, rounds={state.round_idx}")
        qwen_token_usage = qwen_client.token_usage
        return {
            "analysis_path": str(out_dir / "music_analysis.json"),
            "scene_plan_path": str(out_dir / "scene_plan.json"),
            "segment_specs_path": str(out_dir / "segment_specs.json"),
            "dialogue_history_path": str(out_dir / config.dialogue_history_name),
            "program_path": str(program_file),
            "workflow_state_path": str(_state_path(out_dir)),
            "inspection_rounds_path": str(_inspection_rounds_path(out_dir)),
            "qwen_calls_path": str(_qwen_calls_path(out_dir)),
            "qwen_token_usage": qwen_token_usage,
            "fleet_type": fleet.fleet_type,
            "drone_class": fleet.drone_class,
            "status": state.status,
            "round_idx": state.round_idx,
            "final_full_video_2d": final_full_video_2d,
            "final_full_video_3d": final_full_video_3d,
            "last_round_full_video_2d": last_full_video_2d,
            "last_round_full_video_3d": last_full_video_3d,
            "render_fps": max(10, int(config.render_fps)),
        }
    except Exception as exc:
        state.last_error = str(exc)
        if "render fallback used in strict mode" in state.last_error:
            state.status = "failed_retryable"
        else:
            state.status = "failed_non_retryable"
        state.stage = "done"
        _write_state(out_dir, state)
        raise
