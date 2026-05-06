# -*- coding: utf-8 -*-
# 该文件编排从自然语言到仿真输出的端到端流程

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from math import ceil, cos, pi, sin
from pathlib import Path
from typing import Any, Callable, Literal

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
from .inspector import InspectInput, generate_final_design_narration, inspect_with_qwen
from .qwen_client import QwenConfig, QwenVideoClient
from .refiner import refine_segments
from .renderer import cut_video_segment, render_project, render_project_pair
from .safety import (
    classify_render_distance_warnings,
    summarize_render_distance_warnings,
    validate_duration,
    validate_fleet_rule,
    validate_segment_specs,
)


QUALITY_MIN_MOVE2_FINAL = 14
QUALITY_MIN_MOVE2_STEP = 3
QUALITY_MIN_LITERAL_TARGETS = 12
QUALITY_MIN_GROUP_LOOP_COUNT = 6
QUALITY_MIN_TIMELAYERS = 6
QUALITY_MAX_INTTIME_GAP_SEC = 4
QUALITY_MIN_MAIN_SPAN_CM = 320
QUALITY_MIN_SECONDARY_SPAN_CM = 120
QUALITY_LONGFORM_LAYER_BASE = 6
QUALITY_LONGFORM_LAYER_DIVISOR = 8
QUALITY_TIMELINE_END_MARGIN_SEC = 6.0


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
    max_python_regen_attempts: int = 5
    qwen_action_steps: int = 3
    qwen_step_patch_attempts: int = 4
    direct_wait_until_step_accepted: bool = True
    direct_use_structured_agent_fallback: bool = True
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


def _final_narration_path(out_dir: Path) -> Path:
    return out_dir / "final_design_narration.txt"


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
    radius = 220.0
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
    target_output_duration_sec: float | None = None,
) -> str:
    # 可运行自由编舞脚手架：默认使用分层分组循环，避免退化为单层短动作
    ctor = "pf.Drone" if fleet.fleet_type == "F400" else "pf.Drone6"
    config_name = "pf.drone_config_6m"
    start_positions = _freeform_start_positions(fleet.drone_count)
    target_output = max(10.0, float(target_output_duration_sec or 24.0))
    target_script = max(8.0, target_output - 3.0)
    layer_count = max(4, int(ceil(max(0.0, target_script - 6.0) / 4.0)) + 1)

    lines: list[str] = _pyfii_bootstrap_lines() + [
        "from math import cos, pi, sin",
        "# Qwen 自由编舞初始脚手架（分层+分组循环）",
    ]
    for idx in range(fleet.drone_count):
        lines.append(f"d{idx + 1}={ctor}(0,0,{config_name},\"192.168.51.{51 + idx}\")")
    lines.append("")
    lines.append("ds=[" + ",".join([f"d{i+1}" for i in range(fleet.drone_count)]) + "]")
    lines.append("group_a=ds[::2]")
    lines.append("group_b=ds[1::2]")
    lines.append(f"start_positions={repr(start_positions)}")
    lines.append("for d,p in zip(ds,start_positions):")
    lines.append("    d.X=d.x=p[0]")
    lines.append("    d.Y=d.y=p[1]")
    lines.append("    d.takeoff(1,100)")
    lines.append("")
    lines.append(f"for li in range({layer_count}):")
    lines.append("    t=6+li*4")
    lines.append("    phase=li*0.24")
    lines.append("    for gi,d in enumerate(group_a):")
    lines.append("        idx=ds.index(d)")
    lines.append("        d.inittime(t)")
    lines.append("        d.VelXY(150,260)")
    lines.append("        d.VelZ(130,250)")
    lines.append("        base=2*pi*idx/len(ds)-pi/2")
    lines.append("        ang=base+phase")
    lines.append("        r=226+8*sin(li*0.5+idx*0.3)")
    lines.append("        x=280+r*cos(ang)")
    lines.append("        y=280+r*sin(ang)")
    lines.append("        z=max(104,min(210,120+(li%5)*8+gi*2))")
    lines.append("        d.move2(int(max(28,min(532,x))),int(max(28,min(532,y))),int(z))")
    lines.append("        d.delay(420)")
    lines.append("    for gi,d in enumerate(group_b):")
    lines.append("        idx=ds.index(d)")
    lines.append("        d.inittime(t)")
    lines.append("        d.VelXY(150,260)")
    lines.append("        d.VelZ(130,250)")
    lines.append("        base=2*pi*idx/len(ds)-pi/2")
    lines.append("        ang=base+phase")
    lines.append("        r=162+10*cos(li*0.45+idx*0.35)")
    lines.append("        x=280+r*cos(ang)")
    lines.append("        y=280+r*sin(ang)")
    lines.append("        z=max(110,min(218,138+((li+1)%5)*7-gi*2))")
    lines.append("        d.move2(int(max(28,min(532,x))),int(max(28,min(532,y))),int(z))")
    lines.append("        d.delay(420)")
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
    prev_start_int = 4
    for s_idx, scene in enumerate(plan.scenes):
        tracks: list[DroneTrackSpec] = []
        scene_start_int = max(4, ceil(float(scene.start)), prev_start_int)
        scene_end_int = max(scene_start_int + 1, ceil(float(scene.end)))
        delay_ms = max(100, (scene_end_int - scene_start_int) * 1000 - 800)
        prev_start_int = scene_start_int
        for d_idx in range(fleet.drone_count):
            x0, y0 = anchors[d_idx]
            x = max(0, min(560, x0 + (10 * ((s_idx + d_idx) % 3 - 1))))
            y = max(0, min(560, y0 + (10 * ((s_idx * 2 + d_idx) % 3 - 1))))
            z = max(80 if fleet.fleet_type == "F400" else 100, min(250, z_base + (d_idx % 3) * 8))
            tracks.append(
                DroneTrackSpec(
                    drone_id=d_idx + 1,
                    ops=[
                        DroneOp(op="inittime", args=[scene_start_int]),
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
                start=float(scene_start_int),
                end=float(scene_end_int),
                tracks=tracks,
            )
        )
    return segments


def _build_pyfii_usage_guide_context() -> str:
    # 将文档+源码关键用法作为固定上下文注入，降低小众项目 hallucination
    return (
        "Pyfii 用法指南（必须遵守）：\n"
        "- 这是开发环境，不是 pip 安装环境：脚本开头必须先 import os,sys，再 append '/src' 和 '/src/pyfii'，然后再导入 pyfii。\n"
        "- 导入模板必须放在文件最前面：import os; import sys; sys.path.append(...); try import pyfii as pf except ...。\n"
        "- 运行方式：在 pyfii 仓库根目录执行 python output/.../nl_choreo_generated.py。\n"
        "- 无人机动作要按 Python class 对象语义写：先创建全部 Drone 对象，再逐个对象赋起飞点。\n"
        "- 每架机都要设置起飞坐标：d.X=d.x=x 与 d.Y=d.y=y（x,y 为起飞坐标）。\n"
        "- takeoff 必须带两个参数：d.takeoff(time,height)，其中 time>=1，80<=height<=250（F400）。禁止 d.takeoff()。\n"
        "- 首个动作层时间规则：first_inittime >= max_takeoff_time + 3（例如 takeoff(1,...) -> inittime>=4；takeoff(2,...) -> inittime>=5）。\n"
        "- 后续 inittime 必须单调不回退。\n"
        "- move2 前必须先设置 VelXY(v,a) 与 VelZ(v,a)。\n"
        "- 推荐封装 move2_by_time(d,target,duration_ms)：根据当前点到目标点的距离和期望到达时长，计算 VelXY/VelZ/Acc 后再 move2。\n"
        "- 参考 tests/function.py 的 Time/Vel/move2 思路：速度应服务于动作时长和音乐节奏，不应全片固定。\n"
        "- delay(ms) 用于动作间停顿/节奏控制，建议放在 move/move2 后；ms 必须为非负整数。\n"
        "- move2(x,y,z) = 绝对坐标移动到目标点；move(dx,dy,dz) = 相对位移。\n"
        "- d.x,d.y,d.z 表示当前目标点，可用于相对写法，例如 d.move(d.x+dx,d.y+dy,d.z+dz)。\n"
        "- 强烈建议采用‘按 inittime 分层 + for 循环’结构：每个时间层用 for d in groupA/groupB... 批量下发动作，清晰表达编队关系。\n"
        "- 每层至少分 2 组以上（例如内圈/外圈、左翼/右翼），禁止全体同路径同目标。\n"
        "- 全片应有足够动作层和转场，不要只做 2~3 次 move2。\n"
        "- 编舞必须有角色轮换：禁止长期使用一架固定中心机作为唯一锚点；中心/领舞/外圈角色应在不同时间层变化。\n"
        "- 每架无人机都应参与可见 XY 运动；不要让任何一架在全片长期只改变高度或原地等待。\n"
        "- 允许出现短暂中心构图，但必须让中心机离开中心、外圈机补位或分组互换视觉职责。\n"
        "- 转场必须显式规划避撞路径：可使用中间关键帧、错峰启动、分组通道或局部邻接保持；不要把避撞简化成固定中心+外圈旋转。\n"
        "- 允许多中心、双线、对角线、蛇形、符号笔画、前后场交换等非环形结构；关键是密采样路径不能对穿。\n"
        "- 复杂编排可参考 tests/dntg20220730_v3.py 的设计思路（场景分段、数学轨迹、角色映射、分组并行和灯光渐变），但不要模仿其随意编码风格或照抄坐标。\n"
        "- 生成代码应保持清晰命名、函数化组织、少用隐式全局状态，并便于关键帧审查和局部修改。\n"
        "- 编舞流程应是：先设计关键动作/关键队形，再设计衔接动作，最后按每段期望时长求解速度；不要从固定安全模板倒推动作。\n"
        "- 衔接动作可以包含中间关键帧、错峰启动、局部绕行、分组通道和速度变化；安全失败时优先修衔接，而不是牺牲关键动作。\n"
        "- 艺术参考：dntg20220730_3D.mp4（强调队形层次、呼应、对称与转场，而非随机位移）。\n"
        "- 6m 毯坐标范围：x,y ∈ [0,560]；F400 z ∈ [80,250]。\n"
        "- 脚本必须有 land() 与 end()，最后用 F=pf.Fii(name,ds,music='...'); F.save()。\n"
        "- 注意：pf.Fii(...) 不接受 fps 参数；帧率应在 pf.show(...,FPS=40) 中设置。\n"
        "- 参考源码语义：src/pyfii/drone.py 中 takeoff/inittime/move/move2/VelXY/VelZ/land/end。\n"
        "- 参考文档：doc/doc_zh_CN.md 与 doc/tutorial/principle.md。\n"
    )


def _build_direct_edit_patch_prompt(current_code: str, edit_text: str, expected_fps: int) -> str:
    return (
        "请根据用户编辑要求修改下面 pyfii 脚本，并返回完整代码（只输出代码）。\n"
        + _build_pyfii_usage_guide_context()
        + "硬约束：\n"
        "1) 首个 inittime >= max_takeoff_time+3（例如 takeoff(1)->>=4, takeoff(2)->>=5），且不回退。\n"
        "2) 每次 move2 前必须先 VelXY 和 VelZ。\n"
        "3) 允许并鼓励使用 delay(ms) 控节奏（非负整数）。\n"
        "4) 按 inittime 分层，并优先使用 for d in groupA/groupB 的分组写法表达编队关系。\n"
        "5) 必须避免固定中心锚点：若存在中心机，它也要参与 XY 运动，并在不同段落和其他无人机交换视觉职责。\n"
        "6) 保留结尾 land + end。\n"
        f"7) 使用 FPS={expected_fps}。\n"
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
    *,
    target_output_duration_sec: float | None = None,
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
            target_output_duration_sec=target_output_duration_sec,
        )
    return None


def _ensure_render_project(out_dir: Path, program_file: Path, force: bool = False) -> None:
    # 执行生成脚本，确保输出目录中的 .fii 与渲染输入工件存在
    project_dir = out_dir / "nl_choreo_output"
    if project_dir.exists() and not force:
        return

    backup_dir: Path | None = None
    if project_dir.exists() and force:
        backup_dir = out_dir / "nl_choreo_output__backup"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(project_dir, backup_dir)
        shutil.rmtree(project_dir)

    proc = subprocess.run(
        [sys.executable, str(program_file)],
        cwd=str(Path.cwd()),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        if backup_dir is not None:
            if project_dir.exists():
                shutil.rmtree(project_dir)
            shutil.move(str(backup_dir), str(project_dir))
        raise RuntimeError(f"generated program execution failed: {proc.stderr.strip()}")

    if not project_dir.exists():
        if backup_dir is not None:
            shutil.move(str(backup_dir), str(project_dir))
        raise RuntimeError("generated program finished but nl_choreo_output is missing")

    if backup_dir is not None and backup_dir.exists():
        shutil.rmtree(backup_dir)


def _probe_video_duration_sec(video_path: str) -> float:
    # 读取视频时长，供分段窗口与实际渲染长度对齐
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            video_path,
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return 0.0
    try:
        payload = json.loads(proc.stdout or "{}")
    except Exception:
        return 0.0
    return float((payload.get("format") or {}).get("duration") or 0.0)


def _duration_targets_sec(analysis: MusicAnalysis, force_duration_sec: float | None) -> tuple[float, float, float, float]:
    # 输出视频时长目标 + 脚本动作时长目标（show 会额外增加约 3 秒尾帧）
    target_output = float(force_duration_sec) if force_duration_sec is not None else float(analysis.duration)
    target_output = max(10.0, target_output)
    target_script = max(7.0, target_output - 3.0)
    if force_duration_sec is not None:
        out_min = max(10.0, target_output - 5.0)
        out_max = target_output + 6.0
    else:
        out_min = max(10.0, target_output * 0.85)
        out_max = target_output * 1.15
    return target_output, target_script, out_min, out_max


def _validate_output_duration(video_path: str, out_min_sec: float, out_max_sec: float) -> str | None:
    dur = _probe_video_duration_sec(video_path)
    if dur <= 0:
        return f"duration probe failed for output video: {video_path}"
    if dur < out_min_sec or dur > out_max_sec:
        return f"output duration out of range: got={dur:.2f}s, require=[{out_min_sec:.2f},{out_max_sec:.2f}]s"
    return None


def _validate_render_warnings_safe(render_warnings: list[str]) -> str | None:
    unsafe, details = classify_render_distance_warnings(render_warnings)
    if not unsafe:
        return None
    if not details:
        return "unsafe render distance warnings detected"
    return "unsafe render distance warnings detected: " + "; ".join(details)


def _probe_render_safety_for_project(out_dir: Path, config: PipelineConfig, tag: str) -> str | None:
    # 通过 2D/3D 渲染告警对候选脚本执行安全门
    project_path = str(out_dir / "nl_choreo_output")
    save_prefix = str(out_dir / tag)
    r2d, r3d = render_project_pair(
        project_path=project_path,
        save_path_2d=f"{save_prefix}_2d",
        save_path_3d=f"{save_prefix}_3d",
        fps=max(10, int(config.render_fps)),
    )
    return _validate_render_warnings_safe(list(r2d.warnings) + list(r3d.warnings))


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
        or "nframes should in interval" in msg
        or ("nframes" in msg and "got 0" in msg)
    )


def _strip_markdown_code_fence(text: str) -> str:
    # 清理/提取 LLM 返回内容中的 Python 正文，优先可解析代码块
    t = (text or "").strip()
    if not t:
        return "\n"

    candidates: list[str] = []

    # 1) 提取 markdown fenced code blocks
    fence_blocks = re.findall(r"```(?:python|py)?\s*([\s\S]*?)\s*```", t, flags=re.IGNORECASE)
    for block in fence_blocks:
        b = block.strip()
        if b:
            candidates.append(b)

    # 2) 提取 JSON 样式 code 字段
    code_field_match = re.search(r'"code"\s*:\s*"((?:\\.|[^"\\])*)"', t)
    if code_field_match:
        raw = code_field_match.group(1)
        try:
            decoded = ast.literal_eval('"' + raw + '"')
            if isinstance(decoded, str) and decoded.strip():
                candidates.append(decoded.strip())
        except Exception:
            pass

    # 3) 回退：整段文本
    candidates.append(t)

    def _trim_to_probable_python_start(s: str) -> str:
        marker = re.search(
            r"(?:^|\n)(?:import\s+|from\s+\w+\s+import\s+|try\s*:|d\d+\s*=|ds\s*=|for\s+\w+\s+in\s+ds\s*:|name\s*=)",
            s,
        )
        return s[marker.start() :].strip() if marker else s.strip()

    def _score_pyfii_script(s: str) -> int:
        low = s.lower()
        score = 0
        for token in ("takeoff(", ".inittime(", ".move2(", "pf.", "f=pf.fii("):
            if token in low:
                score += 1
        return score

    prepared: list[str] = []
    for c in candidates:
        c2 = _trim_to_probable_python_start(c)
        if c2:
            prepared.append(c2)

    prepared.sort(key=_score_pyfii_script, reverse=True)

    for c in prepared:
        try:
            ast.parse(c)
            return c + ("\n" if not c.endswith("\n") else "")
        except Exception:
            continue

    fallback = prepared[0] if prepared else t
    return fallback + ("\n" if not fallback.endswith("\n") else "")


def _normalize_generated_program_text(program_text: str, expected_fps: int) -> str:
    # 兼容 intime 写法，并补齐 FPS
    normalized = program_text
    normalized = re.sub(r"\.intime\(", ".inittime(", normalized)

    takeoff_times = [int(x) for x in re.findall(r"\.takeoff\(\s*(\d+)\s*,", normalized)]
    first_inittime_floor = (max(takeoff_times) + 3) if takeoff_times else 4

    # 自动修正不合规的 inittime：统一为 int、首个 >= max_takeoff+3，且全局不回退
    prev_init = first_inittime_floor

    def _fix_inittime(match: re.Match[str]) -> str:
        nonlocal prev_init
        raw_text = match.group(1).strip()
        try:
            raw = int(float(raw_text))
        except Exception:
            # 非常量表达式（如 inittime(t)）保留原样
            return match.group(0)
        fixed = max(first_inittime_floor, raw, prev_init)
        prev_init = fixed
        return f".inittime({fixed})"

    normalized = re.sub(r"\.inittime\(([^\)]+)\)", _fix_inittime, normalized)

    if f"FPS={expected_fps}" not in normalized:
        normalized = re.sub(
            r"FPS\s*=\s*\d+",
            f"FPS={expected_fps}",
            normalized,
        )

    has_pyfii_import = bool(
        re.search(r"(?m)^\s*(import\s+pyfii\s+as\s+pf|from\s+pyfii\s+import\s+pyfii\s+as\s+pf)\s*$", normalized)
    )
    has_src_path = "sys.path.append(os.getcwd() + r'/src')" in normalized
    has_pkg_path = "sys.path.append(os.getcwd() + r'/src/pyfii')" in normalized
    if has_pyfii_import and (not has_src_path or not has_pkg_path):
        lines = normalized.splitlines()
        insert_at = 0
        for i, ln in enumerate(lines[:40]):
            s = ln.strip()
            if (
                s.startswith("#!")
                or s.startswith("# -*-")
                or s.startswith("#")
                or s == ""
                or s.startswith("import ")
                or s.startswith("from ")
            ):
                insert_at = i + 1
                continue
            break

        bootstrap: list[str] = []
        if not re.search(r"(?m)^\s*import\s+os\s*$", normalized):
            bootstrap.append("import os")
        if not re.search(r"(?m)^\s*import\s+sys\s*$", normalized):
            bootstrap.append("import sys")
        if not has_src_path:
            bootstrap.append("sys.path.append(os.getcwd() + r'/src')")
        if not has_pkg_path:
            bootstrap.append("sys.path.append(os.getcwd() + r'/src/pyfii')")

        if bootstrap:
            lines[insert_at:insert_at] = bootstrap
            normalized = "\n".join(lines) + "\n"

    # 仅在顶层导入语句出现时替换，避免误替换 try 块中的已缩进语句
    normalized = re.sub(
        r"(?m)^(import\s+pyfii\s+as\s+pf|from\s+pyfii\s+import\s+pyfii\s+as\s+pf)\s*$",
        "try:\n    import pyfii as pf\nexcept Exception:\n    from pyfii import pyfii as pf",
        normalized,
    )

    # 修复常见坏模式：try 导入 pyfii 后 except: pass，导致后续 pf 未定义
    normalized = re.sub(
        r"try:\s*\n\s*(?:import\s+pyfii\s+as\s+pf|from\s+pyfii\s+import\s+pyfii\s+as\s+pf)\s*\n\s*except(?:\s+Exception)?\s*:\s*\n\s*pass",
        "try:\n    import pyfii as pf\nexcept Exception:\n    from pyfii import pyfii as pf",
        normalized,
        flags=re.IGNORECASE,
    )
    return normalized


def _validate_generated_program_text(
    program_text: str,
    expected_fps: int,
    *,
    target_script_duration_sec: float | None = None,
) -> list[str]:
    # 代码级快速安全门：时间单调、首动作时刻、关键动作完整性 + 编舞质量约束
    errors: list[str] = []
    lower = program_text.lower()

    required_tokens = ["takeoff(", ".inittime(", ".velxy(", ".velz(", ".move2(", ".land()", ".end()"]
    for token in required_tokens:
        if token not in lower:
            errors.append(f"missing required action token: {token}")

    if re.search(r"\.takeoff\(\s*\)", lower):
        errors.append("invalid takeoff signature: takeoff() is forbidden, must be takeoff(time,height)")

    for m in re.finditer(r"\.takeoff\(([^\)]*)\)", program_text):
        args_text = m.group(1).strip()
        if not args_text:
            continue
        if len([p for p in args_text.split(",") if p.strip()]) < 2:
            errors.append("invalid takeoff signature: takeoff requires two args (time,height)")
            break

    takeoff_times = [int(x) for x in re.findall(r"\.takeoff\(\s*(\d+)\s*,", program_text)]
    first_inittime_floor = (max(takeoff_times) + 3) if takeoff_times else 4

    times = [int(x) for x in re.findall(r"\.inittime\((\d+)\)", program_text)]
    if times:
        if min(times) < first_inittime_floor:
            errors.append(
                f"first inittime must be >= max_takeoff_time+3 (={first_inittime_floor}), got min={min(times)}"
            )
        for i in range(1, len(times)):
            if times[i] < times[i - 1]:
                errors.append(
                    f"inittime must be monotonic non-decreasing: {times[i - 1]} -> {times[i]} at index {i}"
                )
                break

    # FPS 由归一化阶段补齐，不作为拒收条件

    move2_calls = len(re.findall(r"\.move2\(", lower))
    if move2_calls < QUALITY_MIN_MOVE2_FINAL:
        errors.append(
            f"insufficient choreography complexity: move2 calls={move2_calls}, require >={QUALITY_MIN_MOVE2_FINAL}"
        )

    if re.search(r"for\s+\w+\s+in\s+ds\s*:[\s\S]{0,220}?\.move2\(\s*\w+\.x\s*,\s*\w+\.y\s*,", lower):
        errors.append("unsafe same-path pattern: blind loop move2(d.X,d.Y,...) detected")

    literal_targets = re.findall(r"\.move2\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)", lower)
    if literal_targets and len(set(literal_targets)) < QUALITY_MIN_LITERAL_TARGETS:
        errors.append(
            f"insufficient target diversity: require >={QUALITY_MIN_LITERAL_TARGETS} distinct literal move2 targets"
        )

    group_loop_count = len(re.findall(r"for\s+\w+\s+in\s+(?:ds|group_?\w+)", lower))
    if group_loop_count < QUALITY_MIN_GROUP_LOOP_COUNT:
        errors.append(
            f"style requirement failed: require grouped for-loop structure (ds/group_*) count>={QUALITY_MIN_GROUP_LOOP_COUNT}"
        )

    per_drone_literal_blocks = len(re.findall(r"\bd\d+\.inittime\(", lower))
    if per_drone_literal_blocks >= 7 and group_loop_count == 0:
        errors.append("style requirement failed: avoid repeated d1/d2/... literal per-drone blocks, use ds/group loops")

    if times and len(set(times)) < QUALITY_MIN_TIMELAYERS:
        errors.append(f"insufficient timeline diversity: require >={QUALITY_MIN_TIMELAYERS} distinct inittime layers")
    if times:
        sorted_times = sorted(set(times))
        if len(sorted_times) >= 2:
            max_gap = max(sorted_times[i] - sorted_times[i - 1] for i in range(1, len(sorted_times)))
            if max_gap > QUALITY_MAX_INTTIME_GAP_SEC:
                errors.append(
                    f"movement too sparse: max inittime gap={max_gap}s, require <={QUALITY_MAX_INTTIME_GAP_SEC}s"
                )

    if literal_targets:
        xs = [int(x) for x, _, _ in literal_targets]
        ys = [int(y) for _, y, _ in literal_targets]
        span_x = max(xs) - min(xs)
        span_y = max(ys) - min(ys)
        if max(span_x, span_y) < QUALITY_MIN_MAIN_SPAN_CM:
            errors.append(
                f"insufficient large-range movement: max span={max(span_x, span_y)}cm, require >={QUALITY_MIN_MAIN_SPAN_CM}cm"
            )
        if min(span_x, span_y) < QUALITY_MIN_SECONDARY_SPAN_CM:
            errors.append(
                f"insufficient 2-axis range: min span={min(span_x, span_y)}cm, require >={QUALITY_MIN_SECONDARY_SPAN_CM}cm"
            )

    if target_script_duration_sec is not None and times:
        max_t = max(times)
        min_required_t = max(8, int(target_script_duration_sec - QUALITY_TIMELINE_END_MARGIN_SEC))
        if max_t < min_required_t:
            errors.append(
                f"insufficient timeline horizon: max inittime={max_t}, require >= {min_required_t} for target duration"
            )
        min_layer_count = max(QUALITY_LONGFORM_LAYER_BASE, int(target_script_duration_sec // QUALITY_LONGFORM_LAYER_DIVISOR))
        if len(set(times)) < min_layer_count:
            errors.append(
                f"insufficient long-form layering: distinct inittime={len(set(times))}, require >= {min_layer_count}"
            )

    return errors


def _validate_stepwise_candidate_text(
    candidate: str,
    expected_fps: int,
    step_idx: int,
    total_steps: int,
    *,
    target_script_duration_sec: float | None = None,
) -> list[str]:
    # stepwise 阶段允许渐进增强，避免首步因“完整终稿约束”被过度拦截
    errors: list[str] = []
    lower = candidate.lower()

    required_tokens = [".inittime(", ".velxy(", ".velz(", ".move2("]
    for token in required_tokens:
        if token not in lower:
            errors.append(f"missing required action token: {token}")

    if "takeoff(" not in lower:
        errors.append("missing required action token: takeoff(")
    if step_idx >= total_steps:
        if ".land()" not in lower:
            errors.append("missing required action token: .land()")
        if ".end()" not in lower:
            errors.append("missing required action token: .end()")

    takeoff_times = [int(x) for x in re.findall(r"\.takeoff\(\s*(\d+)\s*,", candidate)]
    first_inittime_floor = (max(takeoff_times) + 3) if takeoff_times else 4
    times = [int(x) for x in re.findall(r"\.inittime\((\d+)\)", candidate)]
    if times:
        if min(times) < first_inittime_floor:
            errors.append(
                f"first inittime must be >= max_takeoff_time+3 (={first_inittime_floor}), got min={min(times)}"
            )
        for i in range(1, len(times)):
            if times[i] < times[i - 1]:
                errors.append(
                    f"inittime must be monotonic non-decreasing: {times[i - 1]} -> {times[i]} at index {i}"
                )
                break

    # FPS 由归一化阶段补齐，不作为拒收条件

    move2_calls = len(re.findall(r"\.move2\(", lower))
    min_move2 = QUALITY_MIN_MOVE2_FINAL if step_idx >= total_steps else QUALITY_MIN_MOVE2_STEP
    if move2_calls < min_move2:
        errors.append(f"insufficient choreography complexity: move2 calls={move2_calls}, require >={min_move2}")

    if re.search(r"for\s+\w+\s+in\s+ds\s*:[\s\S]{0,220}?\.move2\(\s*\w+\.x\s*,\s*\w+\.y\s*,", lower):
        errors.append("unsafe same-path pattern: blind loop move2(d.X,d.Y,...) detected")

    if step_idx >= total_steps:
        group_loop_count = len(re.findall(r"for\s+\w+\s+in\s+(?:ds|group_?\w+)", lower))
        if group_loop_count < QUALITY_MIN_GROUP_LOOP_COUNT:
            errors.append(
                f"style requirement failed: final step requires grouped for-loop structure (ds/group_*) count>={QUALITY_MIN_GROUP_LOOP_COUNT}"
            )
        if times and len(set(times)) < QUALITY_MIN_TIMELAYERS:
            errors.append(f"insufficient timeline diversity: require >={QUALITY_MIN_TIMELAYERS} distinct inittime layers")
        if times:
            sorted_times = sorted(set(times))
            if len(sorted_times) >= 2:
                max_gap = max(sorted_times[i] - sorted_times[i - 1] for i in range(1, len(sorted_times)))
                if max_gap > QUALITY_MAX_INTTIME_GAP_SEC:
                    errors.append(
                        f"movement too sparse: max inittime gap={max_gap}s, require <={QUALITY_MAX_INTTIME_GAP_SEC}s"
                    )
        literal_targets = re.findall(r"\.move2\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)", lower)
        if literal_targets and len(set(literal_targets)) < QUALITY_MIN_LITERAL_TARGETS:
            errors.append(
                f"insufficient target diversity: require >={QUALITY_MIN_LITERAL_TARGETS} distinct literal move2 targets"
            )
        if literal_targets:
            xs = [int(x) for x, _, _ in literal_targets]
            ys = [int(y) for _, y, _ in literal_targets]
            span_x = max(xs) - min(xs)
            span_y = max(ys) - min(ys)
            if max(span_x, span_y) < QUALITY_MIN_MAIN_SPAN_CM:
                errors.append(
                    f"insufficient large-range movement: max span={max(span_x, span_y)}cm, require >={QUALITY_MIN_MAIN_SPAN_CM}cm"
                )
            if min(span_x, span_y) < QUALITY_MIN_SECONDARY_SPAN_CM:
                errors.append(
                    f"insufficient 2-axis range: min span={min(span_x, span_y)}cm, require >={QUALITY_MIN_SECONDARY_SPAN_CM}cm"
                )
        if target_script_duration_sec is not None and times:
            max_t = max(times)
            min_required_t = max(8, int(target_script_duration_sec - QUALITY_TIMELINE_END_MARGIN_SEC))
            if max_t < min_required_t:
                errors.append(
                    f"insufficient timeline horizon: max inittime={max_t}, require >= {min_required_t} for target duration"
                )
            min_layer_count = max(
                QUALITY_LONGFORM_LAYER_BASE,
                int(target_script_duration_sec // QUALITY_LONGFORM_LAYER_DIVISOR),
            )
            if len(set(times)) < min_layer_count:
                errors.append(
                    f"insufficient long-form layering: distinct inittime={len(set(times))}, require >= {min_layer_count}"
                )

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
        + _build_pyfii_usage_guide_context()
        + "设计规范（来自项目文档摘要）：\n"
        "- 先确定起飞位与起飞，再按时间轴推进动作层。\n"
        "- inittime 用整数秒，首个动作层 >=4 秒，后续不回退。\n"
        "- 每个动作层先设 VelXY/VelZ，再 move2；尽量按场景分层推进。\n"
        "- 优先写 move2_by_time(d,target,duration_ms) 这类辅助函数：按目标距离和期望时长动态计算 VelXY/VelZ/Acc，避免全片固定速度。\n"
        "- 先设计关键动作，再补衔接动作：关键动作表达音乐段落与观感目标，衔接动作负责自然、安全地连接相邻关键动作。\n"
        "- 编码结构优先采用‘每个 inittime 一层 + for 循环分组’（参考 tests/dntg20220730_v3.py 的层次表达）。\n"
        "- 每层至少 2 组以上无人机（如内外圈/左右翼），体现队形关系与呼应。\n"
        "- 必须设计角色轮换：领舞、中心、外圈、左右翼等职责要随段落变化，不要让一架无人机长期固定在场地中心。\n"
        "- 所有无人机都要有可见 XY 运动跨度；中心构图只能短暂出现，随后应通过中心机离场、外圈补位、双中心或分组交错打破单一结构。\n"
        "- 生成后需要能通过关键帧审查：关键帧应能看出队形差异、视觉重心变化和音乐段落变化。\n"
        "- 复杂设计可参考 tests/dntg20220730_v3.py 的编舞思想：按音乐段落组织场景，用三角函数/参数曲线生成轨迹，用 group 映射表达角色轮换，用 100ms 级灯光渐变贴合节奏。\n"
        "- 不要把安全策略退化成中心机+外圈机；安全应来自清晰转场路径、分组通道和中间关键帧，而不是单一环形构图。\n"
        "- 注意：不要模仿该参考脚本的随意编码风格；请使用清晰函数、明确变量名、局部数据结构和可审查的段落组织。\n"
        "- 尤其学习它的 move2(d,p,t) 思想：动作先确定，衔接段给定时长，再求速度/加速度去完成，而不是固定 VelXY 后被动接受动作未完成。\n"
        "- 不要只输出静态队形列表；应包含至少一种参数化轨迹或循环生成的连续图案，例如环绕、利萨如、对角线展开、双组平移旋转或符号笔画。\n"
        "- 艺术参考：dntg20220730_3D.mp4，目标是有层次的编队艺术，不是随机两三次位移。\n"
        "- 6m 场地坐标范围：0<=x<=560, 0<=y<=560。\n"
        "- move2(x,y,z) 是绝对坐标移动到目标点，不是相对位移。\n"
        "- 相对位移请用 d.move(d.x+dx,d.y+dy,d.z+dz) 思路（d.x,d.y,d.z 为当前目标点）。\n"
        "- 可加入灯光编排：只使用 TurnOnAll/TurnOffAll（不要 TurnOnSingle/TurnOffSingle）；先完成全部动作设计，再补灯光；灯光可自由添加，允许突变换色。\n"
        "- 6m 场地优先安全余量与可执行性，避免碰撞与越界。\n"
        "- 需要大尺度位移：主段应出现约 320~500cm 级别的跨区移动，且兼顾双轴变化。\n"
        "- 禁止全机长时间静止：任意无人机连续保持同一目标点不应超过 4 秒。\n"
        "编码原则：\n"
        "- 直接返回完整可运行 pyfii 脚本，不要解释文本。\n"
        "- 保留标准收尾 land + end，并确保 FPS 正确。\n"
        "硬约束：\n"
        "1) 首个 inittime 必须 >= max_takeoff_time+3（例：takeoff(1)->>=4, takeoff(2)->>=5）。\n"
        "2) 全部 inittime 必须单调不回退。\n"
        "3) 每次 move2 前必须先 VelXY 和 VelZ。\n"
        "3.1) 可使用 delay(ms) 设计节奏停顿（非负整数）。\n"
        "4) 结尾必须 land + end。\n"
        "5) 输出 fps 必须使用 FPS="
        f"{render_fps}。\n"
        "6) 保持 6m 场地安全余量，避免明显碰撞风险。\n"
        "7) 优先原创编队与高频动作变化，不要套固定图案库。\n"
        "8) 严禁全机同路径、同目标点同步飞行（现实高风险）。\n"
        f"9) 至少 {QUALITY_MIN_TIMELAYERS} 个不同 inittime 的动作层，且每层要有可见队形变化。\n"
        "10) 必须按‘每个 inittime 一层 + for 循环分组’组织代码，禁止仅按单机顺序零散写动作。\n"
        f"11) 每层至少 2 组以上不同目标点，且全片不少于 {QUALITY_MIN_LITERAL_TARGETS} 个不同 move2 目标坐标。\n"
        f"12) 必须包含大尺度位移：全片主轴跨度 >={QUALITY_MIN_MAIN_SPAN_CM}cm，且次轴跨度 >={QUALITY_MIN_SECONDARY_SPAN_CM}cm（鼓励 320~500cm）。\n"
        f"13) 动作不能稀疏：任意相邻动作层间隔不应超过 {QUALITY_MAX_INTTIME_GAP_SEC} 秒。\n"
        "14) 禁止固定中心机模式：任何无人机都不能在全片长期保持同一 XY 点；若 d1/中心机存在，必须至少在 3 个段落移动到不同 XY 区域。\n"
        "15) 禁止单一环形套路：不能长期呈现一架/一组在中心、其他无人机围绕旋转；必须包含非中心化结构。\n"
        "16) 必须体现复杂编排结构：至少包含 3 个命名段落、2 种分组映射/角色重排、1 种数学参数轨迹、1 段与动作同步的灯光渐变。\n"
        "17) 转场复杂时必须加入中间关键帧或错峰路径，避免无规划换位造成中途对穿。\n"
        "18) 必须动态调节速度：至少实现一个按目标距离和期望时长计算 VelXY/VelZ 的辅助函数，并在主要 move2 中使用。\n"
        "19) 安全检查失败时应优先调整衔接路径、时长、速度和错峰，而不是把动作退化成固定安全通道。\n"
        "20) 代码风格必须可维护：禁止大段无命名魔法数字堆叠；优先使用小函数、命名列表/字典、清晰段落注释。\n"
        "21) 3D 观演视角需面向前场：pf.show(...,ThreeD=True,imshow=[90,3],d=(600,500),FPS>=60,max_fps=60)。\n"
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


def _build_structured_plan_prompt(config: PipelineConfig, fleet: FleetSpec, analysis: MusicAnalysis, steps: int) -> str:
    analysis_payload = json.dumps(to_dict(analysis), ensure_ascii=False)
    return (
        "你是 pyfii 编舞 DSL 规划器。请输出严格 JSON，不要输出解释。\n"
        + _build_pyfii_usage_guide_context()
        + "输出格式：\n"
        "{\n"
        "  \"global\": {\"takeoff_time\": 1, \"takeoff_z\": 100, \"fps\": 40},\n"
        "  \"layers\": [\n"
        "    {\"inittime\": 4, \"targets\": [{\"drone_id\":1,\"x\":280,\"y\":200,\"z\":120}], \"velxy\": [120,240], \"velz\": [120,240]}\n"
        "  ]\n"
        "}\n"
        "约束：\n"
        f"- drone_id 范围 1..{fleet.drone_count}\n"
        "- x/y/z 必须在合法范围\n"
        f"- layers 至少 {max(3, int(steps))} 层，inittime 单调\n"
        "- 每层 targets 必须覆盖全部无人机\n"
        f"用户意图: {config.user_intent}\n"
        f"机队: {to_dict(fleet)}\n"
        f"音乐分析: {analysis_payload}\n"
    )


def _compile_structured_plan_to_pyfii(
    plan_text: str,
    fleet: FleetSpec,
    output_path: str,
    music_path: str,
    expected_fps: int,
) -> str | None:
    try:
        payload = json.loads(plan_text)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", plan_text)
        if not m:
            return None
        try:
            payload = json.loads(m.group(0))
        except Exception:
            return None

    layers = payload.get("layers") if isinstance(payload, dict) else None
    if not isinstance(layers, list) or not layers:
        return None

    ctor = "pf.Drone" if fleet.fleet_type == "F400" else "pf.Drone6"
    config_name = "pf.drone_config_6m"
    start_positions = _freeform_start_positions(fleet.drone_count)

    lines: list[str] = _pyfii_bootstrap_lines() + ["# structured pyfii coding-agent fallback"]
    for idx in range(fleet.drone_count):
        lines.append(f"d{idx + 1}={ctor}(0,0,{config_name},\"192.168.51.{51 + idx}\")")
    lines.append("")
    lines.append("ds=[" + ",".join([f"d{i+1}" for i in range(fleet.drone_count)]) + "]")
    lines.append(f"start_positions={repr(start_positions)}")
    lines.append("for d,p in zip(ds,start_positions):")
    lines.append("    d.X=d.x=p[0]")
    lines.append("    d.Y=d.y=p[1]")
    lines.append("    d.takeoff(1,100)")
    lines.append("")

    prev_time = 4
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        t = int(layer.get("inittime", prev_time))
        t = max(4, t, prev_time)
        prev_time = t
        velxy = layer.get("velxy", [120, 240])
        velz = layer.get("velz", [120, 240])
        vx = int(velxy[0]) if isinstance(velxy, list) and len(velxy) >= 2 else 120
        ax = int(velxy[1]) if isinstance(velxy, list) and len(velxy) >= 2 else 240
        vz = int(velz[0]) if isinstance(velz, list) and len(velz) >= 2 else 120
        az = int(velz[1]) if isinstance(velz, list) and len(velz) >= 2 else 240

        targets = layer.get("targets", [])
        targets_by_id: dict[int, dict[str, Any]] = {}
        if isinstance(targets, list):
            for item in targets:
                if isinstance(item, dict) and "drone_id" in item:
                    targets_by_id[int(item["drone_id"])] = item

        for d_idx in range(1, fleet.drone_count + 1):
            item = targets_by_id.get(d_idx, {})
            x = int(item.get("x", start_positions[d_idx - 1][0]))
            y = int(item.get("y", start_positions[d_idx - 1][1]))
            z = int(item.get("z", 120 if fleet.fleet_type == "F400" else 140))
            x = max(0, min(560, x))
            y = max(0, min(560, y))
            z = max(80 if fleet.fleet_type == "F400" else 100, min(250, z))
            lines.append(f"d{d_idx}.inittime({t})")
            lines.append(f"d{d_idx}.VelXY({vx},{ax})")
            lines.append(f"d{d_idx}.VelZ({vz},{az})")
            lines.append(f"d{d_idx}.move2({x},{y},{z})")
        lines.append("")

    for d_idx in range(1, fleet.drone_count + 1):
        lines.append(f"d{d_idx}.land()")
        lines.append(f"d{d_idx}.end()")
    lines.append("")
    lines.append(f"name='{output_path}'")
    lines.append("F=pf.Fii(name,ds,music='" + music_path + "')")
    lines.append("F.save()")
    lines.append("data,t0,music,field,device=pf.read_fii(name)")
    lines.append(f"pf.show(data,t0,music,field=field,device=device,save=name,FPS={max(10, int(expected_fps))})")
    return "\n".join(lines) + "\n"


def _generate_program_with_structured_coding_agent(
    out_dir: Path,
    qwen_client: QwenVideoClient,
    config: PipelineConfig,
    fleet: FleetSpec,
    analysis: MusicAnalysis,
    expected_fps: int,
    program_file: Path,
    *,
    target_script_duration_sec: float | None = None,
    output_duration_range_sec: tuple[float, float] | None = None,
    effective_action_steps: int | None = None,
) -> str:
    struct_steps = max(3, int(effective_action_steps if effective_action_steps is not None else config.qwen_action_steps))
    if target_script_duration_sec is not None:
        required_end = max(8, int(float(target_script_duration_sec) - 8.0))
        min_steps_by_horizon = max(3, int(ceil(max(0, required_end - 4) / 4.0)) + 1)
        struct_steps = max(struct_steps, min_steps_by_horizon)
    plan_prompt = _build_structured_plan_prompt(config=config, fleet=fleet, analysis=analysis, steps=struct_steps)
    plan_text = qwen_client.generate_design_text(plan_prompt)
    compiled = _compile_structured_plan_to_pyfii(
        plan_text=plan_text,
        fleet=fleet,
        output_path=str(out_dir / "nl_choreo_output"),
        music_path=config.audio_path,
        expected_fps=expected_fps,
    )
    if not compiled:
        local_plan = {
            "global": {"takeoff_time": 1, "takeoff_z": 100, "fps": int(expected_fps)},
            "layers": [],
        }
        positions = _freeform_start_positions(fleet.drone_count)
        for li in range(struct_steps):
            t = 4 + li * 4
            targets: list[dict[str, int]] = []
            for i in range(fleet.drone_count):
                x0, y0 = positions[i]
                x = max(0, min(560, x0 + ((li % 3) - 1) * 35 + (i % 3 - 1) * 18))
                y = max(0, min(560, y0 + (((li + i) % 3) - 1) * 28))
                z = max(80 if fleet.fleet_type == "F400" else 100, min(250, 110 + (li % 3) * 12 + (i % 2) * 8))
                targets.append({"drone_id": i + 1, "x": int(x), "y": int(y), "z": int(z)})
            local_plan["layers"].append({"inittime": t, "targets": targets, "velxy": [120, 240], "velz": [120, 240]})
        compiled = _compile_structured_plan_to_pyfii(
            plan_text=json.dumps(local_plan, ensure_ascii=False),
            fleet=fleet,
            output_path=str(out_dir / "nl_choreo_output"),
            music_path=config.audio_path,
            expected_fps=expected_fps,
        )
        if not compiled:
            raise RuntimeError("structured coding-agent plan parse/compile failed")
    compiled = _normalize_generated_program_text(compiled, expected_fps=expected_fps)
    static_errors = _validate_generated_program_text(
        compiled,
        expected_fps=expected_fps,
        target_script_duration_sec=target_script_duration_sec,
    )
    if static_errors:
        raise RuntimeError("structured coding-agent generated invalid script: " + "; ".join(static_errors))
    program_file.write_text(compiled, encoding="utf-8")
    _ensure_render_project(out_dir, program_file, force=True)
    safety_err = _probe_render_safety_for_project(out_dir=out_dir, config=config, tag="safety_structured_accept")
    if safety_err:
        raise RuntimeError(safety_err)
    if output_duration_range_sec is not None:
        out_min_sec, out_max_sec = output_duration_range_sec
        duration_err = _validate_output_duration(
            video_path=str(out_dir / "nl_choreo_output.mp4"),
            out_min_sec=float(out_min_sec),
            out_max_sec=float(out_max_sec),
        )
        if duration_err:
            raise RuntimeError(duration_err)
    _append_jsonl(
        _qwen_calls_path(out_dir),
        {
            "action": "structured_coding_agent_acceptance",
            "accepted": True,
            "reason": "passed",
        },
    )
    return compiled


def _build_reviewer_repair_prompt(candidate_code: str, errors: list[str], expected_fps: int) -> str:
    errs = "\n".join([f"- {e}" for e in errors])
    return (
        "你是 pyfii 代码审稿修复器。请修复候选脚本并输出完整 Python 代码（只输出代码）。\n"
        + _build_pyfii_usage_guide_context()
        + "必须先修复以下失败项：\n"
        + errs
        + "\n\n硬约束：\n"
        "1) 必须保留 takeoff。\n"
        "2) 至少包含 inittime/VelXY/VelZ/move2。\n"
        "3) 末尾必须 land + end。\n"
        f"4) move2 必须有至少 {QUALITY_MIN_MOVE2_FINAL} 次调用（stepwise 至少 {QUALITY_MIN_MOVE2_STEP} 次）。\n"
        "5) 按 inittime 分层，并使用 for 循环分组表达编队关系。\n"
        "6) 每层至少 2 组目标，避免全机同目标同路径。\n"
        f"7) 鼓励 320~500cm 跨区位移，任意相邻动作层间隔不超过 {QUALITY_MAX_INTTIME_GAP_SEC} 秒。\n"
        f"8) 输出 FPS={expected_fps}。\n"
        "候选脚本：\n"
        "```python\n"
        + candidate_code
        + "\n```"
    )


def _build_codegen_fix_prompt(previous_code: str, errors: list[str]) -> str:
    # 根据失败原因回传修复指令，要求返回完整代码
    errs = "\n".join([f"- {e}" for e in errors])
    return (
        "请修复下面 pyfii Python 脚本，并返回完整修复后代码（只输出代码）。\n"
        + _build_pyfii_usage_guide_context()
        + "必须修复以下问题：\n"
        f"{errs}\n\n"
        "强约束（必须同时满足）：\n"
        "1) 严禁所有无人机共享同一路径或同一目标点。\n"
        f"2) 至少包含 {QUALITY_MIN_TIMELAYERS} 个时间层（不同 inittime）和明显编队变化。\n"
        "3) 每个动作层至少 2 组不同目标坐标。\n"
        "3.1) 编码结构采用按 inittime 分层的 for 循环分组写法，清晰表达队形关系。\n"
        "3.2) 使用分层编舞风格与有节奏的艺术转场；灯光在动作完成后再补充，颜色与变换方式可自由（允许突变）。\n"
        f"3.3) 鼓励 320~500cm 级别跨区位移，且禁止任意无人机在同一目标点停留超过 {QUALITY_MAX_INTTIME_GAP_SEC} 秒。\n"
        "4) 6m 场地坐标范围：0<=x<=560, 0<=y<=560。\n"
        "5) move2(x,y,z) 是绝对坐标移动，不是相对位移。\n"
        "6) 相对位移请用 d.move(d.x+dx,d.y+dy,d.z+dz) 思路（d.x,d.y,d.z 为当前目标点）。\n"
        "7) move2 前必须 VelXY + VelZ；保留 land+end；FPS 缺失会自动补齐。\n\n"
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
        "要求动作频繁、队形变化明显、转场有层次；参考 dntg20220730_3D.mp4 的艺术编排。\n"
        "鼓励主段出现 320~500cm 级别跨区位移，同时保持安全间距。\n"
        f"任意无人机连续保持同一目标点不应超过 {QUALITY_MAX_INTTIME_GAP_SEC} 秒。\n"
        "每一步都要指明该层 inittime 下至少两组（groupA/groupB）队形关系，而不是随机单点移动。\n"
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
    # 要求 Qwen 按“分场景递进”改写完整脚本，且优先沿用当前脚本结构
    analysis_payload = json.dumps(to_dict(analysis), ensure_ascii=False)
    return (
        "你是 pyfii 编舞工程师。请在当前脚本基础上，按当前步对应的场景递进修改，返回完整 Python 代码。\n"
        + _build_pyfii_usage_guide_context()
        + "分步规则：\n"
        "1) 当前步先保证该场景可执行与安全，可暂不追求终稿复杂度。\n"
        "2) 逐步增强动作密度与队形变化，最后一步再收敛到完整终稿。\n"
        "3) 必须按 inittime 分层组织，并使用 for 循环分组（groupA/groupB...）表达编队关系。\n"
        "4) 每一步都应增加可见编队艺术性，参考 dntg20220730_3D.mp4 的层次与转场。\n"
        "硬约束：\n"
        "1) takeoff 后首个 inittime>=max_takeoff_time+3（例：takeoff(1)->>=4, takeoff(2)->>=5）；inittime 不回退。\n"
        "2) 每次 move2 前必须 VelXY 和 VelZ。\n"
        "3) 可使用 delay(ms) 设计停顿节奏（非负整数）。\n"
        "3) 6m 场地坐标范围：0<=x<=560, 0<=y<=560。\n"
        "4) move2(x,y,z) 是绝对坐标移动，不是相对位移。\n"
        "5) 相对位移请用 d.move(d.x+dx,d.y+dy,d.z+dz) 思路（d.x,d.y,d.z 为当前目标点）。\n"
        "6) 必须保留 takeoff。\n"
        "7) 最后一步必须包含 land+end；非最后一步也尽量保留。\n"
        "8) 严禁全机同路径/同目标点；至少分成 2 组以上目标。\n"
        "9) 每个 inittime 层必须有分组 for 块，不得只写零散单机动作。\n"
        "10) 本步新增动作应尽量形成呼应/对称/扩散/收拢等艺术转场，而非随机位移。\n"
        "11) 鼓励 320~500cm 级别的大尺度跨区转场（保持安全间距，不越界）。\n"
        "11.1) 可加入灯光编排，但只用 TurnOnAll/TurnOffAll；灯光放在动作设计完成后统一添加，允许突变换色。\n"
        f"12) 禁止任意无人机在同一目标点停留超过 {QUALITY_MAX_INTTIME_GAP_SEC} 秒。\n"
        f"13) 必须使用 FPS={expected_fps}（若遗漏会由系统自动补齐）。\n"
        "14) 只输出完整代码，不要解释。\n"
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


def _run_reviewer_repair_once(
    qwen_client: QwenVideoClient,
    candidate: str,
    errors: list[str],
    expected_fps: int,
) -> str | None:
    try:
        repaired_raw = qwen_client.generate_python_code(
            _build_reviewer_repair_prompt(candidate_code=candidate, errors=errors, expected_fps=expected_fps)
        )
        repaired = _strip_markdown_code_fence(repaired_raw)
        repaired = _normalize_generated_program_text(repaired, expected_fps=expected_fps)
        return repaired
    except Exception:
        return None


def _validate_then_maybe_repair(
    qwen_client: QwenVideoClient,
    validator: Callable[[str], list[str]],
    candidate: str,
    expected_fps: int,
) -> tuple[str, list[str], bool]:
    errors = validator(candidate)
    if not errors:
        return candidate, errors, False
    repaired = _run_reviewer_repair_once(
        qwen_client=qwen_client,
        candidate=candidate,
        errors=errors,
        expected_fps=expected_fps,
    )
    if repaired is None:
        return candidate, errors, False
    repaired_errors = validator(repaired)
    if repaired_errors:
        return candidate, errors, False
    return repaired, [], True


def _generate_safe_program_with_qwen(
    out_dir: Path,
    qwen_client: QwenVideoClient,
    config: PipelineConfig,
    prompt_zh: str,
    max_attempts: int,
    expected_fps: int,
    program_file: Path,
    *,
    target_script_duration_sec: float | None = None,
    output_duration_range_sec: tuple[float, float] | None = None,
) -> str:
    # 代码生成-执行闭环：若不安全/不可执行则把问题回传给 Qwen 修复
    prompt = prompt_zh
    last_errors: list[str] = ["unknown generation failure"]

    for attempt in range(1, max(1, int(max_attempts)) + 1):
        candidate_raw = qwen_client.generate_python_code(prompt)
        candidate = _strip_markdown_code_fence(candidate_raw)
        candidate = _normalize_generated_program_text(candidate, expected_fps=expected_fps)

        candidate, static_errors, repaired_by_reviewer = _validate_then_maybe_repair(
            qwen_client=qwen_client,
            validator=lambda c: _validate_generated_program_text(
                c,
                expected_fps=expected_fps,
                target_script_duration_sec=target_script_duration_sec,
            ),
            candidate=candidate,
            expected_fps=expected_fps,
        )
        if static_errors:
            last_errors = static_errors
            _append_jsonl(
                _inspection_rounds_path(out_dir),
                {
                    "type": "direct_codegen_attempt",
                    "mode": "one_shot",
                    "attempt": attempt,
                    "accepted": False,
                    "reason": "static_validation_failed",
                    "errors": static_errors,
                    "reviewer_repair_attempted": True,
                },
            )
            _append_jsonl(
                _qwen_calls_path(out_dir),
                {
                    "action": "generate_python_code_acceptance",
                    "mode": "one_shot",
                    "attempt": attempt,
                    "accepted": False,
                    "reason": "static_validation_failed",
                    "errors": static_errors,
                    "reviewer_repair_attempted": True,
                },
            )
            prompt = _build_codegen_fix_prompt(candidate, static_errors)
            continue

        program_file.write_text(candidate, encoding="utf-8")
        try:
            _ensure_render_project(out_dir, program_file, force=True)
            safety_err = _probe_render_safety_for_project(
                out_dir=out_dir,
                config=config,
                tag=f"safety_one_shot_attempt_{attempt:02d}",
            )
            if safety_err:
                raise RuntimeError(safety_err)
            if output_duration_range_sec is not None:
                out_min_sec, out_max_sec = output_duration_range_sec
                duration_err = _validate_output_duration(
                    video_path=str(out_dir / "nl_choreo_output.mp4"),
                    out_min_sec=float(out_min_sec),
                    out_max_sec=float(out_max_sec),
                )
                if duration_err:
                    raise RuntimeError(duration_err)
            _append_jsonl(
                _inspection_rounds_path(out_dir),
                {
                    "type": "direct_codegen_attempt",
                    "mode": "one_shot",
                    "attempt": attempt,
                    "accepted": True,
                    "reason": "passed",
                    "program_file": str(program_file),
                    "reviewer_repaired": repaired_by_reviewer,
                },
            )
            _append_jsonl(
                _qwen_calls_path(out_dir),
                {
                    "action": "generate_python_code_acceptance",
                    "mode": "one_shot",
                    "attempt": attempt,
                    "accepted": True,
                    "reason": "passed",
                    "reviewer_repaired": repaired_by_reviewer,
                },
            )
            return candidate
        except Exception as exc:
            last_errors = [f"program execution/render failed: {exc}"]
            _append_jsonl(
                _inspection_rounds_path(out_dir),
                {
                    "type": "direct_codegen_attempt",
                    "mode": "one_shot",
                    "attempt": attempt,
                    "accepted": False,
                    "reason": "execution_or_render_failed",
                    "errors": last_errors,
                },
            )
            _append_jsonl(
                _qwen_calls_path(out_dir),
                {
                    "action": "generate_python_code_acceptance",
                    "mode": "one_shot",
                    "attempt": attempt,
                    "accepted": False,
                    "reason": "execution_or_render_failed",
                    "errors": last_errors,
                },
            )
            prompt = _build_codegen_fix_prompt(candidate, last_errors)

    raise RuntimeError("qwen direct codegen failed after retries: " + "; ".join(last_errors))


def _apply_direct_edit_rounds(
    current_code: str,
    rounds: list[str],
    qwen_client: QwenVideoClient,
    config: PipelineConfig,
    expected_fps: int,
    dialogue_manager: DialogueManager,
    out_dir: Path,
    program_file: Path,
    *,
    target_script_duration_sec: float | None = None,
    output_duration_range_sec: tuple[float, float] | None = None,
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
                config=config,
                prompt_zh=prompt,
                max_attempts=2,
                expected_fps=expected_fps,
                program_file=program_file,
                target_script_duration_sec=target_script_duration_sec,
                output_duration_range_sec=output_duration_range_sec,
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


def _build_adaptive_step_prompt(base_prompt: str, failure_errors: list[str], attempt: int, max_attempts: int) -> str:
    # 同一步连续失败时，逐轮强化约束并注入失败统计
    if not failure_errors:
        return base_prompt
    freq: dict[str, int] = {}
    for err in failure_errors:
        freq[err] = freq.get(err, 0) + 1
    top_items = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    top_lines = "\n".join([f"- {k} (x{v})" for k, v in top_items])
    return (
        base_prompt
        + "\n\n"
        + f"[系统追加约束 attempt {attempt}/{max_attempts}]\n"
        + "你上一次输出未通过静态检查。请逐条修复以下高频失败项：\n"
        + top_lines
        + "\n必须直接输出完整 Python 代码，不得输出解释。"
    )


def _generate_program_stepwise_with_qwen(
    out_dir: Path,
    qwen_client: QwenVideoClient,
    config: PipelineConfig,
    fleet: FleetSpec,
    analysis: MusicAnalysis,
    seed_program_text: str,
    expected_fps: int,
    program_file: Path,
    *,
    target_script_duration_sec: float | None = None,
    output_duration_range_sec: tuple[float, float] | None = None,
    effective_action_steps: int | None = None,
) -> str:
    # 动作级迭代生成：先规划步骤，再逐步改写完整脚本并执行反馈
    current_code = seed_program_text
    program_file.write_text(current_code, encoding="utf-8")
    _ensure_render_project(out_dir, program_file, force=True)

    total_steps = max(1, int(effective_action_steps if effective_action_steps is not None else config.qwen_action_steps))

    try:
        step_plan_text = qwen_client.generate_design_text(
            _build_action_plan_prompt(config=config, analysis=analysis, total_steps=total_steps)
        )
    except Exception:
        step_plan_text = "Step1: 强化队形变化并增加动作频率"

    successful_steps = 0
    for step_idx in range(1, total_steps + 1):
        _log_progress(f"direct step {step_idx}/{total_steps}")
        step_prompt = _build_action_step_prompt(
            config=config,
            fleet=fleet,
            analysis=analysis,
            step_plan_text=step_plan_text,
            step_idx=step_idx,
            total_steps=total_steps,
            current_code=current_code,
            expected_fps=expected_fps,
        )
        prompt = step_prompt
        step_ok = False
        last_errors: list[str] = []
        failure_history: list[str] = []

        for attempt in range(1, max(1, int(config.qwen_step_patch_attempts)) + 1):
            try:
                effective_prompt = _build_adaptive_step_prompt(
                    base_prompt=prompt,
                    failure_errors=failure_history,
                    attempt=attempt,
                    max_attempts=max(1, int(config.qwen_step_patch_attempts)),
                )
                candidate_raw = qwen_client.generate_python_code(effective_prompt)
                candidate = _strip_markdown_code_fence(candidate_raw)
                candidate = _normalize_generated_program_text(candidate, expected_fps=expected_fps)
                candidate, static_errors, repaired_by_reviewer = _validate_then_maybe_repair(
                    qwen_client=qwen_client,
                    validator=lambda c: _validate_stepwise_candidate_text(
                        c,
                        expected_fps=expected_fps,
                        step_idx=step_idx,
                        total_steps=total_steps,
                        target_script_duration_sec=target_script_duration_sec,
                    ),
                    candidate=candidate,
                    expected_fps=expected_fps,
                )
                if static_errors:
                    last_errors = static_errors
                    failure_history.extend(static_errors)
                    _append_jsonl(
                        _inspection_rounds_path(out_dir),
                        {
                            "type": "direct_codegen_step_attempt",
                            "step": step_idx,
                            "attempt": attempt,
                            "accepted": False,
                            "reason": "static_validation_failed",
                            "errors": static_errors,
                            "reviewer_repair_attempted": True,
                        },
                    )
                    _append_jsonl(
                        _qwen_calls_path(out_dir),
                        {
                            "action": "generate_python_code_acceptance",
                            "mode": "stepwise",
                            "step": step_idx,
                            "attempt": attempt,
                            "accepted": False,
                            "reason": "static_validation_failed",
                            "errors": static_errors,
                            "reviewer_repair_attempted": True,
                        },
                    )
                    prompt = _build_codegen_fix_prompt(candidate, static_errors)
                    continue

                program_file.write_text(candidate, encoding="utf-8")
                _ensure_render_project(out_dir, program_file, force=True)
                safety_err = _probe_render_safety_for_project(
                    out_dir=out_dir,
                    config=config,
                    tag=f"safety_step_{step_idx:02d}_attempt_{attempt:02d}",
                )
                if safety_err:
                    raise RuntimeError(safety_err)
                if output_duration_range_sec is not None and step_idx >= total_steps:
                    out_min_sec, out_max_sec = output_duration_range_sec
                    duration_err = _validate_output_duration(
                        video_path=str(out_dir / "nl_choreo_output.mp4"),
                        out_min_sec=float(out_min_sec),
                        out_max_sec=float(out_max_sec),
                    )
                    if duration_err:
                        raise RuntimeError(duration_err)
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
                _append_jsonl(
                    _qwen_calls_path(out_dir),
                    {
                        "action": "generate_python_code_acceptance",
                        "mode": "stepwise",
                        "step": step_idx,
                        "attempt": attempt,
                        "accepted": True,
                        "reason": "passed",
                        "step_file": str(step_file),
                    },
                )
                current_code = candidate
                successful_steps += 1
                step_ok = True
                break
            except Exception as exc:
                last_errors = [f"step execution failed: {exc}"]
                failure_history.extend(last_errors)
                _append_jsonl(
                    _inspection_rounds_path(out_dir),
                    {
                        "type": "direct_codegen_step_attempt",
                        "step": step_idx,
                        "attempt": attempt,
                        "accepted": False,
                        "reason": "execution_or_render_failed",
                        "errors": last_errors,
                    },
                )
                _append_jsonl(
                    _qwen_calls_path(out_dir),
                    {
                        "action": "generate_python_code_acceptance",
                        "mode": "stepwise",
                        "step": step_idx,
                        "attempt": attempt,
                        "accepted": False,
                        "reason": "execution_or_render_failed",
                        "errors": last_errors,
                    },
                )
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
            if config.direct_wait_until_step_accepted:
                raise RuntimeError(
                    f"direct step {step_idx} failed after {max(1, int(config.qwen_step_patch_attempts))} attempts: "
                    + "; ".join(last_errors)
                )
            continue

    if successful_steps == 0:
        raise RuntimeError("direct stepwise generation produced no valid step")

    program_file.write_text(current_code, encoding="utf-8")
    _ensure_render_project(out_dir, program_file, force=True)
    if output_duration_range_sec is not None:
        out_min_sec, out_max_sec = output_duration_range_sec
        duration_err = _validate_output_duration(
            video_path=str(out_dir / "nl_choreo_output.mp4"),
            out_min_sec=float(out_min_sec),
            out_max_sec=float(out_max_sec),
        )
        if duration_err:
            raise RuntimeError(duration_err)
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
        full_result_2d, full_result_3d = render_project_pair(
            project_path=project_path,
            save_path_2d=full_save,
            save_path_3d=f"{full_save}_3d",
            fps=max(10, int(config.render_fps)),
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


def _align_segments_to_video_duration(segments: list[SegmentSpec], video_duration_sec: float) -> list[SegmentSpec]:
    # 分段窗口必须与实际渲染视频长度对齐，避免尾段切片越界
    if video_duration_sec <= 0:
        return segments
    aligned: list[SegmentSpec] = []
    prev_start = 0.0
    max_end = max(0.05, video_duration_sec - 0.01)
    for idx, seg in enumerate(segments):
        start = max(0.0, min(float(seg.start), max_end))
        start = max(start, prev_start)
        if idx == len(segments) - 1:
            end = max(start + 0.05, max_end)
        else:
            end = max(start + 0.05, min(float(seg.end), max_end))
        prev_start = start
        aligned.append(
            SegmentSpec(
                segment_id=seg.segment_id,
                scene_id=seg.scene_id,
                start=start,
                end=end,
                tracks=seg.tracks,
            )
        )
    return aligned


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

    effective_duration = _probe_video_duration_sec(full_video_2d)
    segments = _align_segments_to_video_duration(segments, effective_duration)

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

        target_output_duration_sec, target_script_duration_sec, output_dur_min_sec, output_dur_max_sec = _duration_targets_sec(
            analysis=analysis,
            force_duration_sec=config.force_duration_sec,
        )
        target_script_duration_sec = target_script_duration_sec if config.force_duration_sec is not None else None
        strict_output_duration_range_sec = (
            (output_dur_min_sec, output_dur_max_sec) if config.force_duration_sec is not None else None
        )

        effective_action_steps = max(1, int(config.qwen_action_steps))
        if config.direct_python_codegen and target_script_duration_sec is not None and target_script_duration_sec > 0:
            effective_action_steps = max(effective_action_steps, int(ceil(target_script_duration_sec / 8.0)))

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
                target_output_duration_sec=target_output_duration_sec,
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
                    target_script_duration_sec=target_script_duration_sec,
                    output_duration_range_sec=strict_output_duration_range_sec,
                    effective_action_steps=effective_action_steps,
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
                        config=config,
                        prompt_zh=prompt_zh,
                        max_attempts=config.max_python_regen_attempts,
                        expected_fps=max(40, int(config.render_fps)),
                        program_file=program_file,
                        target_script_duration_sec=target_script_duration_sec,
                        output_duration_range_sec=strict_output_duration_range_sec,
                    )
                except Exception:
                    if config.direct_use_structured_agent_fallback:
                        _log_progress("direct mode fallback: structured pyfii coding agent")
                        try:
                            program_text = _generate_program_with_structured_coding_agent(
                                out_dir=out_dir,
                                qwen_client=qwen_client,
                                config=config,
                                fleet=fleet,
                                analysis=analysis,
                                expected_fps=max(40, int(config.render_fps)),
                                program_file=program_file,
                                target_script_duration_sec=target_script_duration_sec,
                                output_duration_range_sec=strict_output_duration_range_sec,
                                effective_action_steps=effective_action_steps,
                            )
                        except Exception:
                            fallback_seed = _choose_direct_seed_program(
                                config=config,
                                deterministic_seed_program_text=deterministic_seed_program_text,
                                fleet=fleet,
                                target_output_duration_sec=target_output_duration_sec,
                            )
                            if fallback_seed is None and deterministic_seed_program_text is not None:
                                _log_progress("direct mode fallback: use deterministic scene seed")
                                fallback_seed = deterministic_seed_program_text
                            if fallback_seed is None:
                                _log_progress("direct mode fallback: use duration-safe freeform seed")
                                fallback_seed = _build_freeform_seed_program(
                                    output_path=str(out_dir / "nl_choreo_output"),
                                    fleet=fleet,
                                    music_path=config.audio_path,
                                    render_fps=max(40, int(config.render_fps)),
                                    target_output_duration_sec=target_output_duration_sec,
                                )
                            _log_progress("direct mode fallback: use configured direct seed")
                            program_text = fallback_seed
                            program_file.write_text(program_text, encoding="utf-8")
                            _ensure_render_project(out_dir, program_file, force=True)
                            safety_err = _probe_render_safety_for_project(
                                out_dir=out_dir,
                                config=config,
                                tag="safety_fallback_seed_initial",
                            )
                            if safety_err:
                                raise RuntimeError(safety_err)
                            duration_err = _validate_output_duration(
                                video_path=str(out_dir / "nl_choreo_output.mp4"),
                                out_min_sec=output_dur_min_sec,
                                out_max_sec=output_dur_max_sec,
                            ) if strict_output_duration_range_sec is not None else None
                            if duration_err:
                                raise RuntimeError(duration_err)
                    else:
                        fallback_seed = _choose_direct_seed_program(
                            config=config,
                            deterministic_seed_program_text=deterministic_seed_program_text,
                            fleet=fleet,
                            target_output_duration_sec=target_output_duration_sec,
                        )
                        if fallback_seed is None and deterministic_seed_program_text is not None:
                            fallback_seed = deterministic_seed_program_text
                        if fallback_seed is None:
                            raise
                        _log_progress("direct mode fallback: use configured direct seed")
                        program_text = fallback_seed
                        program_file.write_text(program_text, encoding="utf-8")
                        _ensure_render_project(out_dir, program_file, force=True)
                        safety_err = _probe_render_safety_for_project(
                            out_dir=out_dir,
                            config=config,
                            tag="safety_fallback_seed_initial_nostruct",
                        )
                        if safety_err:
                            raise RuntimeError(safety_err)
                        duration_err = _validate_output_duration(
                            video_path=str(out_dir / "nl_choreo_output.mp4"),
                            out_min_sec=output_dur_min_sec,
                            out_max_sec=output_dur_max_sec,
                        )
                        if duration_err:
                            raise RuntimeError(duration_err)

            rounds = edit_rounds or []
            if rounds:
                program_text = _apply_direct_edit_rounds(
                    current_code=program_text,
                    rounds=rounds,
                    qwen_client=qwen_client,
                    config=config,
                    expected_fps=max(40, int(config.render_fps)),
                    dialogue_manager=dialogue_manager,
                    out_dir=out_dir,
                    program_file=program_file,
                    target_script_duration_sec=target_script_duration_sec,
                    output_duration_range_sec=strict_output_duration_range_sec,
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
                                target_script_duration_sec=target_script_duration_sec,
                                output_duration_range_sec=strict_output_duration_range_sec,
                                effective_action_steps=effective_action_steps,
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
                                    config=config,
                                    prompt_zh=prompt_zh,
                                    max_attempts=config.max_python_regen_attempts,
                                    expected_fps=max(40, int(config.render_fps)),
                                    program_file=program_file,
                                    target_script_duration_sec=target_script_duration_sec,
                                    output_duration_range_sec=strict_output_duration_range_sec,
                                )
                            except Exception:
                                if config.direct_use_structured_agent_fallback:
                                    try:
                                        program_text = _generate_program_with_structured_coding_agent(
                                            out_dir=out_dir,
                                            qwen_client=qwen_client,
                                            config=config,
                                            fleet=fleet,
                                            analysis=analysis,
                                            expected_fps=max(40, int(config.render_fps)),
                                            program_file=program_file,
                                            target_script_duration_sec=target_script_duration_sec,
                                            output_duration_range_sec=strict_output_duration_range_sec,
                                            effective_action_steps=effective_action_steps,
                                        )
                                    except Exception:
                                        fallback_seed = _choose_direct_seed_program(
                                            config=config,
                                            deterministic_seed_program_text=deterministic_seed_program_text,
                                            fleet=fleet,
                                            target_output_duration_sec=target_output_duration_sec,
                                        )
                                        if fallback_seed is None and deterministic_seed_program_text is not None:
                                            fallback_seed = deterministic_seed_program_text
                                        if fallback_seed is None:
                                            fallback_seed = _build_freeform_seed_program(
                                                output_path=str(out_dir / "nl_choreo_output"),
                                                fleet=fleet,
                                                music_path=config.audio_path,
                                                render_fps=max(40, int(config.render_fps)),
                                                target_output_duration_sec=target_output_duration_sec,
                                            )
                                        program_text = fallback_seed
                                        program_file.write_text(program_text, encoding="utf-8")
                                        _ensure_render_project(out_dir, program_file, force=True)
                                        safety_err = _probe_render_safety_for_project(
                                            out_dir=out_dir,
                                            config=config,
                                            tag=f"safety_fallback_seed_round_{state.round_idx:02d}",
                                        )
                                        if safety_err:
                                            raise RuntimeError(safety_err)
                                        duration_err = _validate_output_duration(
                                            video_path=str(out_dir / "nl_choreo_output.mp4"),
                                            out_min_sec=output_dur_min_sec,
                                            out_max_sec=output_dur_max_sec,
                                        )
                                        if duration_err:
                                            raise RuntimeError(duration_err)
                                else:
                                    fallback_seed = _choose_direct_seed_program(
                                        config=config,
                                        deterministic_seed_program_text=deterministic_seed_program_text,
                                        fleet=fleet,
                                        target_output_duration_sec=target_output_duration_sec,
                                    )
                                    if fallback_seed is None and deterministic_seed_program_text is not None:
                                        fallback_seed = deterministic_seed_program_text
                                    if fallback_seed is None:
                                        fallback_seed = _build_freeform_seed_program(
                                            output_path=str(out_dir / "nl_choreo_output"),
                                            fleet=fleet,
                                            music_path=config.audio_path,
                                            render_fps=max(40, int(config.render_fps)),
                                            target_output_duration_sec=target_output_duration_sec,
                                        )
                                    program_text = fallback_seed
                                    program_file.write_text(program_text, encoding="utf-8")
                                    _ensure_render_project(out_dir, program_file, force=True)
                                    safety_err = _probe_render_safety_for_project(
                                        out_dir=out_dir,
                                        config=config,
                                        tag=f"safety_fallback_seed_round_{state.round_idx:02d}_nostruct",
                                    )
                                    if safety_err:
                                        raise RuntimeError(safety_err)
                                    duration_err = _validate_output_duration(
                                        video_path=str(out_dir / "nl_choreo_output.mp4"),
                                        out_min_sec=output_dur_min_sec,
                                        out_max_sec=output_dur_max_sec,
                                    )
                                    if duration_err:
                                        raise RuntimeError(duration_err)
                    else:
                        program_text = seed_program_text
                        program_file.write_text(program_text, encoding="utf-8")
                        _ensure_render_project(out_dir, program_file, force=True)
                        safety_err = _probe_render_safety_for_project(
                            out_dir=out_dir,
                            config=config,
                            tag=f"safety_seed_round_{state.round_idx:02d}",
                        )
                        if safety_err:
                            raise RuntimeError(safety_err)

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
        final_safety_err = _validate_render_warnings_safe(final_render_warnings)
        if final_safety_err:
            state.status = "failed_retryable"
            state.stage = "done"
            state.last_error = final_safety_err
            _write_state(out_dir, state)

        final_narration_text = ""
        final_narration_error = ""
        if config.use_qwen:
            try:
                final_narration_text = generate_final_design_narration(
                    client=qwen_client,
                    vibe_target=config.user_intent,
                    script_text=program_file.read_text(encoding="utf-8") if program_file.exists() else "",
                    video_paths=[final_full_video_3d, final_full_video_2d],
                )
                _final_narration_path(out_dir).write_text(final_narration_text, encoding="utf-8")
                _append_jsonl(
                    _qwen_calls_path(out_dir),
                    {
                        "action": "generate_final_design_narration",
                        "ok": True,
                        "artifact": str(_final_narration_path(out_dir)),
                    },
                )
            except Exception as exc:
                final_narration_error = str(exc)
                _append_jsonl(
                    _qwen_calls_path(out_dir),
                    {
                        "action": "generate_final_design_narration",
                        "ok": False,
                        "error": final_narration_error,
                    },
                )

        _append_jsonl(
            _inspection_rounds_path(out_dir),
            {
                "type": "final_summary",
                "final_full_video_2d": final_full_video_2d,
                "final_full_video_3d": final_full_video_3d,
                "fallback_used": final_fallback_used,
                "render_distance_warning_summary": summarize_render_distance_warnings(final_render_warnings),
                "final_safety_error": final_safety_err or "",
                "final_design_narration_path": str(_final_narration_path(out_dir)) if final_narration_text else "",
                "final_design_narration_error": final_narration_error,
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
            "final_design_narration_path": str(_final_narration_path(out_dir)) if _final_narration_path(out_dir).exists() else "",
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
