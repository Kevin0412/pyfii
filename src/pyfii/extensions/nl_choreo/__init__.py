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
from .keyframe_workflow import (
    emit_gpt55_burst_recompose_program,
    get_gpt55_burst_recompose_seed_info,
)

try:
    from .pipeline import PipelineConfig, run_nl_choreo_pipeline
except ModuleNotFoundError as _pipeline_import_error:  # pragma: no cover - optional runtime dependency guard
    PipelineConfig = None  # type: ignore[assignment]

    def run_nl_choreo_pipeline(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise _pipeline_import_error

__all__ = [
    "DialogueManager",
    "emit_gpt55_burst_recompose_program",
    "FleetSpec",
    "get_gpt55_burst_recompose_seed_info",
    "MusicAnalysis",
    "PipelineConfig",
    "Scene",
    "ScenePlan",
    "SegmentIssue",
    "SegmentSpec",
    "run_nl_choreo_pipeline",
    "validate_scene_plan",
]
