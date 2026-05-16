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
from .motion_phrase import (
    DroneGroup,
    MotionDesignSpec,
    MotionPhrase,
    MotionPhraseMetrics,
    MotionPrimitive,
    evaluate_motion_phrase_flexibility,
    validate_motion_design_spec,
    validate_phrase_design_direction,
)
from .qwen_client import AIProviderConfig, QwenConfig, ai_provider_config_from_dict, qwen_config_from_dict

try:
    from .pipeline import PipelineConfig, run_nl_choreo_pipeline
except ModuleNotFoundError as _pipeline_import_error:  # pragma: no cover - optional runtime dependency guard
    PipelineConfig = None  # type: ignore[assignment]

    def run_nl_choreo_pipeline(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise _pipeline_import_error

__all__ = [
    "AIProviderConfig",
    "DialogueManager",
    "emit_gpt55_burst_recompose_program",
    "FleetSpec",
    "get_gpt55_burst_recompose_seed_info",
    "DroneGroup",
    "MusicAnalysis",
    "MotionDesignSpec",
    "MotionPhrase",
    "MotionPhraseMetrics",
    "MotionPrimitive",
    "PipelineConfig",
    "QwenConfig",
    "Scene",
    "ScenePlan",
    "SegmentIssue",
    "SegmentSpec",
    "ai_provider_config_from_dict",
    "evaluate_motion_phrase_flexibility",
    "qwen_config_from_dict",
    "run_nl_choreo_pipeline",
    "validate_motion_design_spec",
    "validate_phrase_design_direction",
    "validate_scene_plan",
]
