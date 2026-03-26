# -*- coding: utf-8 -*-
# 自然语言编排扩展的公共导出

from .contracts import (
    FleetSpec,
    MusicAnalysis,
    Scene,
    ScenePlan,
    SegmentIssue,
    SegmentSpec,
    validate_scene_plan,
)
from .dialogue_manager import DialogueManager
from .pipeline import PipelineConfig, run_nl_choreo_pipeline

__all__ = [
    "DialogueManager",
    "FleetSpec",
    "MusicAnalysis",
    "PipelineConfig",
    "Scene",
    "ScenePlan",
    "SegmentIssue",
    "SegmentSpec",
    "run_nl_choreo_pipeline",
    "validate_scene_plan",
]
