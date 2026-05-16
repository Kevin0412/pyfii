# -*- coding: utf-8 -*-
# 该文件定义工作流各阶段的结构化数据契约

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

DroneClass = Literal["Drone", "Drone6"]
FleetType = Literal["F400", "F600"]


@dataclass
class FleetSpec:
    # 机队配置：必须同构（全部 F400 或全部 F600）
    drone_count: int
    fleet_type: FleetType = "F400"
    drone_class: DroneClass = "Drone"


@dataclass
class MusicSection:
    # 音乐分段信息
    section_id: str
    start: float
    end: float
    energy: Literal["low", "mid", "high"]


@dataclass
class MusicAnalysis:
    # 音乐分析产物：后续规划直接消费该结构
    duration: float
    tempo_estimate: float
    beats: list[float]
    onsets: list[float]
    sections: list[MusicSection]
    energy_curve: list[float] = field(default_factory=list)
    climax_ranges: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class Scene:
    # 场景级编排描述
    scene_id: str
    start: float
    end: float
    formation: str
    motion_style: str
    transition_style: str


@dataclass
class ScenePlan:
    # 场景规划：包含机型约束与用户意图
    user_intent: str
    fleet: FleetSpec
    scenes: list[Scene]


@dataclass
class DroneOp:
    # 单条无人机动作指令
    op: str
    args: list[Any]


@dataclass
class DroneTrackSpec:
    # 单机轨迹片段定义
    drone_id: int
    ops: list[DroneOp]


@dataclass
class SegmentSpec:
    # 段级生成规格：支持局部重生
    segment_id: str
    scene_id: str
    start: float
    end: float
    tracks: list[DroneTrackSpec]


@dataclass
class SegmentIssue:
    # 视觉/安全问题项
    segment_id: str
    severity: Literal["low", "medium", "high"]
    detail: str
    recommendation_zh: str


@dataclass
class InspectionReport:
    # 视觉检查结果
    issues: list[SegmentIssue]
    suggest_regenerate: bool


def to_dict(obj: Any) -> dict[str, Any]:
    # dataclass 转字典便于 JSON 落盘
    return asdict(obj)


def validate_fleet_spec(fleet: FleetSpec) -> None:
    # 强约束：7 架 + 同构机队映射一致
    if fleet.drone_count != 7:
        raise ValueError("drone_count must be 7 for this workflow")
    if fleet.fleet_type == "F400" and fleet.drone_class != "Drone":
        raise ValueError("F400 must use Drone class")
    if fleet.fleet_type == "F600" and fleet.drone_class != "Drone6":
        raise ValueError("F600 must use Drone6 class")


def validate_scene_plan(plan: ScenePlan) -> None:
    # 规划校验：时间单调、区间合法、机队规则合法
    validate_fleet_spec(plan.fleet)
    if not plan.scenes:
        raise ValueError("scene plan is empty")

    prev_end = 0.0
    for scene in plan.scenes:
        if scene.start < prev_end:
            raise ValueError(f"scene overlap detected: {scene.scene_id}")
        if scene.end <= scene.start:
            raise ValueError(f"scene duration invalid: {scene.scene_id}")
        prev_end = scene.end
