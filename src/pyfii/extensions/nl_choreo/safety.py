# -*- coding: utf-8 -*-
# 该文件实现硬约束与安全检查

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any

from .contracts import FleetSpec, SegmentSpec

# 复用 pyfii 默认 6m 参数，避免在无图形环境下导入 pyfii 顶层模块
_DRONE_CONFIG_6M = {
    "xyRange": (0, 560),
    "zRangeF400": (80, 250),
    "zRangeF600": (100, 250),
    "velRange": (20, 200),
    "accRange": (50, 400),
    "ArateRange": (5, 60),
}


@dataclass
class SafetyCheckResult:
    # 安全检查输出：errors 为硬错误，warnings 为提示
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        # 只要没有硬错误就可继续
        return len(self.errors) == 0


def validate_fleet_rule(fleet: FleetSpec) -> None:
    # 机型同构强校验
    if fleet.fleet_type == "F400" and fleet.drone_class != "Drone":
        raise ValueError("F400 fleet must map to Drone")
    if fleet.fleet_type == "F600" and fleet.drone_class != "Drone6":
        raise ValueError("F600 fleet must map to Drone6")


def validate_duration(duration: float) -> None:
    # 需求规定总时长必须在 60~70 秒
    if not (60.0 <= duration <= 70.0):
        raise ValueError("duration must be in [60, 70] seconds")


def _check_coordinate(x: float, y: float, z: float, fleet: FleetSpec) -> None:
    # 坐标边界检查：沿用 pyfii 已有地毯范围
    xy_min, xy_max = _DRONE_CONFIG_6M["xyRange"]
    if fleet.fleet_type == "F400":
        z_min, z_max = _DRONE_CONFIG_6M["zRangeF400"]
    else:
        z_min, z_max = _DRONE_CONFIG_6M["zRangeF600"]
    if not (xy_min <= x <= xy_max and xy_min <= y <= xy_max and z_min <= z <= z_max):
        raise ValueError(f"coordinate out of range: ({x}, {y}, {z})")


def validate_segment_specs(segments: list[SegmentSpec], fleet: FleetSpec) -> SafetyCheckResult:
    # 段级静态检查：时间区间 + move2 坐标合法性 + 最小间距 + 路径冲突
    errors: list[str] = []
    warnings: list[str] = []

    all_targets: dict[int, tuple[float, float, float]] = {}

    min_dist = 50.0 if fleet.fleet_type == "F400" else 33.0

    for seg in segments:
        if seg.end <= seg.start:
            errors.append(f"invalid segment duration: {seg.segment_id}")

        seg_targets: dict[int, tuple[float, float, float]] = {}
        for track in seg.tracks:
            if track.drone_id < 1 or track.drone_id > fleet.drone_count:
                errors.append(f"invalid drone_id in {seg.segment_id}: {track.drone_id}")

            seen_move = False
            seen_land = False
            seen_velxy = False
            seen_velz = False

            for op in track.ops:
                if op.op == "land":
                    seen_land = True
                elif op.op == "VelXY":
                    seen_velxy = True
                elif op.op == "VelZ":
                    seen_velz = True
                elif op.op == "move2" and len(op.args) >= 3:
                    seen_move = True
                    if not (seen_velxy and seen_velz):
                        errors.append(f"{seg.segment_id}/d{track.drone_id}: move2 before VelXY/VelZ")
                    try:
                        x = float(op.args[0])
                        y = float(op.args[1])
                        z = float(op.args[2])
                        _check_coordinate(x, y, z, fleet)
                        seg_targets[track.drone_id] = (x, y, z)
                    except Exception as exc:
                        errors.append(f"{seg.segment_id}/d{track.drone_id}: {exc}")
                elif op.op not in {"inittime", "VelXY", "VelZ", "move2", "delay", "TurnOnAll", "land", "takeoff"}:
                    warnings.append(f"unknown op {op.op} in {seg.segment_id}")

            if seen_move and seen_land:
                warnings.append(f"{seg.segment_id}/d{track.drone_id}: land appears in active segment ops")

        # 段内最小间距（F400 50cm，F600 33cm）
        ids = sorted(seg_targets.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a = seg_targets[ids[i]]
                b = seg_targets[ids[j]]
                dist_xy = sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)
                if dist_xy < min_dist:
                    errors.append(
                        f"{seg.segment_id}: d{ids[i]} and d{ids[j]} too close ({dist_xy:.1f}cm < {min_dist:.1f}cm)"
                    )

        # 路径冲突：比较上一目标点 -> 当前目标点 的同步移动轨迹，若过程距离低于阈值直接失败
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                di = ids[i]
                dj = ids[j]
                if di not in all_targets or dj not in all_targets:
                    continue
                a0 = all_targets[di]
                a1 = seg_targets[di]
                b0 = all_targets[dj]
                b1 = seg_targets[dj]
                min_path_dist = 10**9
                for step in range(11):
                    t = step / 10.0
                    ax = a0[0] + (a1[0] - a0[0]) * t
                    ay = a0[1] + (a1[1] - a0[1]) * t
                    bx = b0[0] + (b1[0] - b0[0]) * t
                    by = b0[1] + (b1[1] - b0[1]) * t
                    dxy = sqrt((ax - bx) ** 2 + (ay - by) ** 2)
                    if dxy < min_path_dist:
                        min_path_dist = dxy
                if min_path_dist < min_dist:
                    errors.append(
                        f"{seg.segment_id}: path conflict d{di}/d{dj} ({min_path_dist:.1f}cm < {min_dist:.1f}cm)"
                    )

        all_targets.update(seg_targets)

    # 全局必须存在动作目标且最终流程应落地（由 codegen 末尾保证）
    if not all_targets:
        warnings.append("no move2 targets found across segments")

    return SafetyCheckResult(errors=errors, warnings=warnings)


def summarize_render_distance_warnings(render_warnings: list[str]) -> dict[str, Any]:
    # 渲染阶段警告汇总：便于对话轮次显示
    return {"count": len(render_warnings), "warnings": render_warnings[:50]}
