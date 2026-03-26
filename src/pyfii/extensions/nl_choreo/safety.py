# -*- coding: utf-8 -*-
# 该文件实现硬约束与安全检查

from __future__ import annotations

from dataclasses import dataclass
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
    # 段级静态检查：时间区间 + move2 坐标合法性
    errors: list[str] = []
    warnings: list[str] = []
    for seg in segments:
        if seg.end <= seg.start:
            errors.append(f"invalid segment duration: {seg.segment_id}")
        for track in seg.tracks:
            if track.drone_id < 1 or track.drone_id > fleet.drone_count:
                errors.append(f"invalid drone_id in {seg.segment_id}: {track.drone_id}")
            for op in track.ops:
                if op.op == "move2" and len(op.args) >= 3:
                    try:
                        _check_coordinate(float(op.args[0]), float(op.args[1]), float(op.args[2]), fleet)
                    except Exception as exc:
                        errors.append(f"{seg.segment_id}/d{track.drone_id}: {exc}")
                elif op.op not in {"inittime", "VelXY", "VelZ", "move2", "delay", "TurnOnAll", "land"}:
                    warnings.append(f"unknown op {op.op} in {seg.segment_id}")
    return SafetyCheckResult(errors=errors, warnings=warnings)


def summarize_render_distance_warnings(render_warnings: list[str]) -> dict[str, Any]:
    # 渲染阶段警告汇总：便于对话轮次显示
    return {"count": len(render_warnings), "warnings": render_warnings[:50]}
