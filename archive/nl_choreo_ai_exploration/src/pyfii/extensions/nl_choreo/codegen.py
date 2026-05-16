# -*- coding: utf-8 -*-
# 该文件把场景计划转换为 pyfii 可执行动作序列

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, cos, pi, sin
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


def _fallback_start_positions(count: int) -> list[tuple[int, int]]:
    # 无 move2 时的兜底起飞平面布局（不再硬编码 y 车道）
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


def _formation_targets(name: str, idx: int) -> tuple[float, float, float]:
    # 根据编队类型给出相对目标 (x,y,z)
    y = 60 + 70 * idx
    if name == "line":
        return (80 + idx * 70, y, 120)
    if name == "arc":
        return (120 + idx * 55, y, 110 + abs(3 - idx) * 20)
    if name == "double_triangle":
        xs = [180, 250, 320, 390, 460, 320, 320]
        zs = [120, 170, 220, 170, 120, 140, 200]
        return (xs[idx], y, zs[idx])
    if name == "spiral":
        xs = [280, 350, 400, 420, 390, 330, 260]
        zs = [120, 130, 160, 200, 220, 230, 210]
        return (xs[idx], y, zs[idx])
    if name == "ring":
        xs = [210, 250, 310, 370, 410, 350, 270]
        zs = [160, 200, 220, 200, 160, 120, 120]
        return (xs[idx], y, zs[idx])
    # fan
    return (160 + idx * 60, y, [120, 140, 160, 180, 160, 140, 120][idx])


def build_segment_specs(plan: ScenePlan, config: CodegenConfig | None = None) -> list[SegmentSpec]:
    # 以场景为粒度生成段级动作规格
    cfg = config or CodegenConfig(palette=_default_palette())

    z_min = 80 if plan.fleet.fleet_type == "F400" else 100
    z_max = 250

    style_factor = {
        "smooth_glide": 0.9,
        "rhythm_pulse": 1.0,
        "strong_expansion": 1.15,
    }

    segments: list[SegmentSpec] = []
    for s_idx, scene in enumerate(plan.scenes):
        tracks: list[DroneTrackSpec] = []
        factor = style_factor.get(scene.motion_style, 1.0)
        speed = max(60, min(200, int(160 * factor)))
        acc = max(120, min(400, int(320 * factor)))

        for d_idx in range(plan.fleet.drone_count):
            x, y, z = _formation_targets(scene.formation, d_idx)
            # 增加高度分层，提升画面层次感
            z_layer = (d_idx - (plan.fleet.drone_count // 2)) * 8
            z = max(z_min, min(z_max, int(round(z + z_layer))))
            y = max(0, min(560, int(round(y))))
            color = cfg.palette[s_idx % len(cfg.palette)]
            ops = [
                DroneOp(op="inittime", args=[int(scene.start)]),
                DroneOp(op="VelXY", args=[speed, acc]),
                DroneOp(op="VelZ", args=[speed, acc]),
                DroneOp(op="move2", args=[round(x), y, z]),
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


def _render_relation_list(name: str, values: list[int | None]) -> str:
    # 关系化列表输出：可识别等差关系，提升可维护性
    if not values:
        return f"{name}=[]"
    if any(v is None for v in values):
        return f"{name}={repr(values)}"
    ints = [int(v) for v in values]
    if all(v == ints[0] for v in ints):
        return f"{name}=[{ints[0]} for _ in range({len(ints)})]"
    if len(ints) >= 2:
        step = ints[1] - ints[0]
        if all(ints[i] == ints[0] + step * i for i in range(len(ints))):
            return f"{name}=[{ints[0]}+{step}*i for i in range({len(ints)})]"
    return f"{name}={repr(ints)}"


def _extract_track_ops(track: DroneTrackSpec, fallback_start: int) -> dict[str, object]:
    # 把单机轨迹压平成可生成的参数集合
    init_sec = fallback_start
    velxy: tuple[int, int] | None = None
    velz: tuple[int, int] | None = None
    move2: tuple[int, int, int] | None = None
    color: str | None = None
    delay_ms: int | None = None

    for op in track.ops:
        if op.op == "inittime" and op.args:
            init_sec = int(op.args[0])
        elif op.op == "VelXY" and len(op.args) >= 2:
            velxy = (int(op.args[0]), int(op.args[1]))
        elif op.op == "VelZ" and len(op.args) >= 2:
            velz = (int(op.args[0]), int(op.args[1]))
        elif op.op == "move2" and len(op.args) >= 3:
            move2 = (int(op.args[0]), int(op.args[1]), int(op.args[2]))
        elif op.op == "TurnOnAll" and op.args:
            color = str(op.args[0])
        elif op.op == "delay" and op.args:
            delay_ms = int(op.args[0])

    return {
        "init_sec": init_sec,
        "velxy": velxy,
        "velz": velz,
        "move2": move2,
        "color": color,
        "delay_ms": delay_ms,
    }


def emit_pyfii_program(
    output_path: str,
    fleet: FleetSpec,
    segments: list[SegmentSpec],
    program_name: str,
    music_path: str,
    render_fps: int = 30,
) -> str:
    # 生成可执行 pyfii 脚本文本：按绝对时间分组，便于人工维护
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
    start_positions = _fallback_start_positions(fleet.drone_count)
    lines.append(f"start_positions={repr(start_positions)}")
    lines.append("for d,p in zip(ds,start_positions):")
    lines.append("    # 初始化起飞位")
    lines.append("    d.X=p[0]")
    lines.append("    d.Y=p[1]")
    lines.append("    d.takeoff(1,80)")

    next_safe_time_sec = 4

    for seg in segments:
        tracks_by_id = {t.drone_id: t for t in seg.tracks}
        extracted: list[dict[str, object]] = []
        init_secs: list[int] = []

        for drone_id in range(1, fleet.drone_count + 1):
            track = tracks_by_id.get(drone_id)
            if track is None:
                extracted.append(
                    {
                        "init_sec": int(seg.start),
                        "velxy": None,
                        "velz": None,
                        "move2": None,
                        "color": None,
                        "delay_ms": None,
                    }
                )
                init_secs.append(int(seg.start))
                continue
            item = _extract_track_ops(track, fallback_start=int(seg.start))
            extracted.append(item)
            init_secs.append(int(item["init_sec"]))

        t_abs = min(init_secs) if init_secs else int(seg.start)
        t_emit = max(next_safe_time_sec, t_abs, 4)
        lines.append("")
        lines.append(f"# 段 {seg.segment_id} / 场景 {seg.scene_id}")
        lines.append(f"# startTime = {t_abs}s")
        lines.append(f"# endTime = {int(seg.end)}s")
        lines.append("for d in ds:")
        lines.append(f"    d.inittime({t_emit})")

        move2_vals = [item["move2"] for item in extracted]
        velxy_vals = [item["velxy"] for item in extracted]
        velz_vals = [item["velz"] for item in extracted]
        color_vals = [item["color"] for item in extracted]
        delay_vals = [item["delay_ms"] for item in extracted]

        has_move2 = any(v is not None for v in move2_vals)
        has_velxy = any(v is not None for v in velxy_vals)
        has_velz = any(v is not None for v in velz_vals)
        has_color = any(v is not None for v in color_vals)
        has_delay = any(v is not None for v in delay_vals)

        xs = [v[0] if v is not None else None for v in move2_vals]
        ys = [v[1] if v is not None else None for v in move2_vals]
        zs = [v[2] if v is not None else None for v in move2_vals]
        vxy_speed = [v[0] if v is not None else None for v in velxy_vals]
        vxy_acc = [v[1] if v is not None else None for v in velxy_vals]
        vz_speed = [v[0] if v is not None else None for v in velz_vals]
        vz_acc = [v[1] if v is not None else None for v in velz_vals]

        if has_move2:
            lines.append(_render_relation_list("xs", xs))
            lines.append(_render_relation_list("ys", ys))
            lines.append(_render_relation_list("zs", zs))
        if has_velxy:
            lines.append(_render_relation_list("vxy_speed", vxy_speed))
            lines.append(_render_relation_list("vxy_acc", vxy_acc))
        if has_velz:
            lines.append(_render_relation_list("vz_speed", vz_speed))
            lines.append(_render_relation_list("vz_acc", vz_acc))
        if has_color:
            lines.append(f"colors={repr(color_vals)}")
        if has_delay:
            lines.append(f"delays={repr(delay_vals)}")

        lines.append("for i,d in enumerate(ds):")
        if has_velxy:
            lines.append("    if vxy_speed[i] is not None and vxy_acc[i] is not None:")
            lines.append("        d.VelXY(vxy_speed[i],vxy_acc[i])")
        if has_velz:
            lines.append("    if vz_speed[i] is not None and vz_acc[i] is not None:")
            lines.append("        d.VelZ(vz_speed[i],vz_acc[i])")
        if has_move2:
            lines.append("    if xs[i] is not None and ys[i] is not None and zs[i] is not None:")
            lines.append("        if not ('vxy_speed' in locals() and vxy_speed[i] is not None and vxy_acc[i] is not None):")
            lines.append("            d.VelXY(160,320)")
            lines.append("        if not ('vz_speed' in locals() and vz_speed[i] is not None and vz_acc[i] is not None):")
            lines.append("            d.VelZ(160,320)")
            lines.append("        d.move2(xs[i],ys[i],zs[i])")
        if has_color:
            lines.append("    if colors[i] is not None:")
            lines.append("        d.TurnOnAll(colors[i])")
        if has_delay:
            lines.append("    if delays[i] is not None:")
            lines.append("        d.delay(delays[i])")

        max_delay_ms = max((int(v) for v in delay_vals if v is not None), default=0)
        step_sec = max(1, ceil(max_delay_ms / 1000) + 1)
        next_safe_time_sec = max(next_safe_time_sec, t_emit + step_sec, int(seg.end))

    lines.append("")
    lines.append("# endTime = final")
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
