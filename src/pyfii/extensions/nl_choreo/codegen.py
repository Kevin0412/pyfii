# -*- coding: utf-8 -*-
# 该文件把场景计划转换为 pyfii 可执行动作序列

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .contracts import DroneOp, DroneTrackSpec, FleetSpec, ScenePlan, SegmentSpec

ColorPalette = list[str]


@dataclass
class CodegenConfig:
    # 代码生成基础配置
    palette: ColorPalette


def _default_palette() -> ColorPalette:
    # 默认配色用于节奏分段可视化
    return ["#ff5555", "#ffaa00", "#ffee55", "#55ff99", "#55bbff", "#aa88ff"]


def _lane_positions() -> list[int]:
    # 7 机 6m 地毯默认 y 轴车道
    return [40, 120, 200, 280, 360, 440, 520]


def _formation_targets(name: str, idx: int) -> tuple[float, float]:
    # 根据编队类型给出相对目标 (x,z)
    if name == "line":
        return (80 + idx * 70, 120)
    if name == "arc":
        return (120 + idx * 55, 110 + abs(3 - idx) * 20)
    if name == "double_triangle":
        tri = [(180, 120), (250, 170), (320, 220), (390, 170), (460, 120), (320, 140), (320, 200)]
        return tri[idx]
    if name == "spiral":
        pts = [(280, 120), (350, 130), (400, 160), (420, 200), (390, 220), (330, 230), (260, 210)]
        return pts[idx]
    if name == "ring":
        ring = [(210, 160), (250, 200), (310, 220), (370, 200), (410, 160), (350, 120), (270, 120)]
        return ring[idx]
    # fan
    fan = [(160, 120), (220, 140), (280, 160), (340, 180), (400, 160), (460, 140), (520, 120)]
    return fan[idx]


def build_segment_specs(plan: ScenePlan, config: CodegenConfig | None = None) -> list[SegmentSpec]:
    # 以场景为粒度生成段级动作规格
    cfg = config or CodegenConfig(palette=_default_palette())
    lanes = _lane_positions()

    segments: list[SegmentSpec] = []
    for s_idx, scene in enumerate(plan.scenes):
        tracks: list[DroneTrackSpec] = []
        for d_idx in range(plan.fleet.drone_count):
            x, z = _formation_targets(scene.formation, d_idx)
            color = cfg.palette[s_idx % len(cfg.palette)]
            ops = [
                DroneOp(op="inittime", args=[int(scene.start)]),
                DroneOp(op="VelXY", args=[160, 320]),
                DroneOp(op="VelZ", args=[160, 320]),
                DroneOp(op="move2", args=[round(x), lanes[d_idx], round(z)]),
                DroneOp(op="TurnOnAll", args=[color]),
            ]
            # 每段末尾留一个小等待，降低相邻段边界抖动
            gap_ms = max(100, int((scene.end - scene.start) * 1000) - 1000)
            ops.append(DroneOp(op="delay", args=[gap_ms]))
            tracks.append(DroneTrackSpec(drone_id=d_idx + 1, ops=ops))

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


def apply_nl_patch(
    segments: list[SegmentSpec],
    patch_text: str,
    mode: Literal["safer", "stronger"] = "safer",
) -> tuple[list[SegmentSpec], str, list[str]]:
    # 解析自然语言编辑并做局部补丁（先实现可解释的规则补丁）
    text = patch_text.lower().strip()
    affected: list[str] = []
    summary = "no-op"

    if "提前" in patch_text or "earlier" in text:
        for seg in segments:
            for track in seg.tracks:
                for op in track.ops:
                    if op.op == "inittime" and op.args:
                        op.args[0] = max(0, int(op.args[0]) - 1)
            affected.append(seg.segment_id)
        summary = "shifted scene starts earlier by 1s"
    elif "更慢" in patch_text or "slower" in text:
        for seg in segments:
            for track in seg.tracks:
                for op in track.ops:
                    if op.op in {"VelXY", "VelZ"} and len(op.args) >= 2:
                        op.args[0] = max(20, int(op.args[0] * 0.8))
                        op.args[1] = max(50, int(op.args[1] * 0.8))
            affected.append(seg.segment_id)
        summary = "reduced velocity/acceleration to 80%"
    elif "更亮" in patch_text or "brighter" in text:
        for seg in segments:
            for track in seg.tracks:
                for op in track.ops:
                    if op.op == "TurnOnAll":
                        op.args = ["#ffffff"]
            affected.append(seg.segment_id)
        summary = "set lights to white for highlighted brightness"

    if mode == "safer" and summary != "no-op":
        summary += " (safe-rule patch)"

    return segments, summary, sorted(set(affected))


def emit_pyfii_program(
    output_path: str,
    fleet: FleetSpec,
    segments: list[SegmentSpec],
    program_name: str,
    music_path: str,
) -> str:
    # 生成可执行 pyfii 脚本文本，全部新注释使用中文
    if fleet.fleet_type == "F400":
        ctor = "pf.Drone"
        config_name = "pf.drone_config_6m"
        device_name = "F400"
    else:
        ctor = "pf.Drone6"
        config_name = "pf.drone_config_6m"
        device_name = "F600"

    lines: list[str] = [
        "import os",
        "import sys",
        "",
        "path = os.getcwd() + r'/src'",
        "sys.path.append(path)",
        "",
        "import pyfii as pf",
        "",
        "# 自动生成：自然语言编排结果（请按需人工复核）",
        f"# 机型：{device_name}，机数：{fleet.drone_count}",
    ]

    for idx in range(fleet.drone_count):
        lines.append(
            f"d{idx + 1}={ctor}(0,0,{config_name},\"192.168.51.{51 + idx}\")"
        )
    lines.append("")
    lines.append("ds=[" + ",".join([f"d{i+1}" for i in range(fleet.drone_count)]) + "]")
    lines.append("")
    lines.append("for d,y in zip(ds,[40,120,200,280,360,440,520]):")
    lines.append("    # 初始化起飞位")
    lines.append("    d.X=40")
    lines.append("    d.Y=y")
    lines.append("    d.takeoff(1,80)")

    velxy_ready: dict[int, bool] = {i + 1: False for i in range(fleet.drone_count)}
    velz_ready: dict[int, bool] = {i + 1: False for i in range(fleet.drone_count)}

    for seg in segments:
        lines.append(f"# 段 {seg.segment_id} / 场景 {seg.scene_id}")
        for track in sorted(seg.tracks, key=lambda t: t.drone_id):
            dname = f"d{track.drone_id}"
            lines.append(f"# 无人机 {track.drone_id}")
            for op in track.ops:
                if op.op == "inittime":
                    continue
                if op.op == "VelXY":
                    velxy_ready[track.drone_id] = True
                if op.op == "VelZ":
                    velz_ready[track.drone_id] = True
                if op.op == "move2":
                    if not velxy_ready[track.drone_id]:
                        lines.append(f"{dname}.VelXY(160,320)")
                        velxy_ready[track.drone_id] = True
                    if not velz_ready[track.drone_id]:
                        lines.append(f"{dname}.VelZ(160,320)")
                        velz_ready[track.drone_id] = True
                args = ",".join([repr(a) for a in op.args])
                lines.append(f"{dname}.{op.op}({args})")

    for i in range(fleet.drone_count):
        lines.append(f"d{i+1}.land()")
        lines.append(f"d{i+1}.end()")
    lines.append("")
    lines.append(f"name='{output_path}'")
    lines.append("F=pf.Fii(name,ds,music='" + music_path + "')")
    lines.append("F.save()")
    lines.append("data,t0,music,field,device=pf.read_fii(name)")
    lines.append("pf.show(data,t0,music,field=field,device=device,save=name,FPS=25)")

    return "\n".join(lines) + "\n"
