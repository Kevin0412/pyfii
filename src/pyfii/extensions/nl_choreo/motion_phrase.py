# -*- coding: utf-8 -*-
"""Phrase-level choreography contracts for iterative motion design.

The current keyframe and template examples are useful baselines, but the next
workflow needs an intermediate representation that can describe non-uniform
timing, drone subgroups, and user-directed phrase edits before codegen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import pstdev
from typing import Any


PROHIBITED_DESIGN_PRIMITIVES = {
    "random",
    "random_search",
    "random_walk",
    "global_rotation",
    "single_center_orbit",
    "fixed_lane",
    "uniform_template_grid",
}


@dataclass
class MotionPrimitive:
    name: str
    weight: float = 1.0
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class DroneGroup:
    group_id: str
    drones: list[int]
    role: str


@dataclass
class MotionPhrase:
    phrase_id: str
    start: float
    end: float
    intent: str
    primitives: list[MotionPrimitive] = field(default_factory=list)
    groups: list[DroneGroup] = field(default_factory=list)
    source_scene_ids: list[str] = field(default_factory=list)
    role_mapping: dict[int, str] = field(default_factory=dict)
    timing_notes: str = ""
    risk: str = ""
    repair_strategy: str = ""


@dataclass
class MotionDesignSpec:
    user_intent: str
    duration: float
    phrases: list[MotionPhrase]


@dataclass
class MotionPhraseMetrics:
    phrase_count: int
    unique_primitive_count: int
    duration_stddev: float
    grouped_phrase_ratio: float
    multi_primitive_phrase_ratio: float
    overlapping_phrase_pairs: int

    @property
    def has_non_uniform_timing(self) -> bool:
        return self.duration_stddev > 0.05


def phrase_duration(phrase: MotionPhrase) -> float:
    return phrase.end - phrase.start


def evaluate_motion_phrase_flexibility(spec: MotionDesignSpec) -> MotionPhraseMetrics:
    durations = [phrase_duration(phrase) for phrase in spec.phrases]
    primitive_names = {
        primitive.name
        for phrase in spec.phrases
        for primitive in phrase.primitives
        if primitive.name
    }
    phrase_count = len(spec.phrases)
    grouped_count = sum(1 for phrase in spec.phrases if phrase.groups)
    multi_primitive_count = sum(1 for phrase in spec.phrases if len(phrase.primitives) >= 2)
    return MotionPhraseMetrics(
        phrase_count=phrase_count,
        unique_primitive_count=len(primitive_names),
        duration_stddev=pstdev(durations) if len(durations) > 1 else 0.0,
        grouped_phrase_ratio=grouped_count / phrase_count if phrase_count else 0.0,
        multi_primitive_phrase_ratio=multi_primitive_count / phrase_count if phrase_count else 0.0,
        overlapping_phrase_pairs=_count_overlapping_phrase_pairs(spec.phrases),
    )


def validate_motion_design_spec(spec: MotionDesignSpec, fleet_size: int = 7) -> list[str]:
    errors: list[str] = []
    if spec.duration <= 0:
        errors.append("motion spec duration must be positive")
    if not spec.phrases:
        errors.append("motion spec must contain at least one phrase")
        return errors

    seen_phrase_ids: set[str] = set()
    for phrase in spec.phrases:
        if not phrase.phrase_id:
            errors.append("phrase id is required")
        elif phrase.phrase_id in seen_phrase_ids:
            errors.append(f"duplicate phrase id: {phrase.phrase_id}")
        seen_phrase_ids.add(phrase.phrase_id)

        if phrase.start < 0:
            errors.append(f"{phrase.phrase_id}: start must be non-negative")
        if phrase.end <= phrase.start:
            errors.append(f"{phrase.phrase_id}: phrase duration must be positive")
        if phrase.end > spec.duration:
            errors.append(f"{phrase.phrase_id}: phrase exceeds design duration")
        if not phrase.intent:
            errors.append(f"{phrase.phrase_id}: intent is required")
        if not phrase.primitives:
            errors.append(f"{phrase.phrase_id}: at least one motion primitive is required")

        for primitive in phrase.primitives:
            if not primitive.name:
                errors.append(f"{phrase.phrase_id}: primitive name is required")
            if primitive.weight <= 0:
                errors.append(f"{phrase.phrase_id}: primitive {primitive.name} weight must be positive")

        _validate_phrase_groups(phrase, fleet_size, errors)
        _validate_role_mapping(phrase, fleet_size, errors)

    return errors


def validate_phrase_design_direction(
    spec: MotionDesignSpec,
    *,
    min_unique_primitives: int = 4,
    min_grouped_phrase_ratio: float = 0.30,
    min_multi_primitive_phrase_ratio: float = 0.40,
    require_non_uniform_timing: bool = True,
) -> list[str]:
    errors = validate_motion_design_spec(spec)
    if errors:
        return errors

    metrics = evaluate_motion_phrase_flexibility(spec)
    primitive_names = {
        primitive.name.strip().lower()
        for phrase in spec.phrases
        for primitive in phrase.primitives
        if primitive.name
    }
    prohibited = sorted(primitive_names & PROHIBITED_DESIGN_PRIMITIVES)
    if prohibited:
        errors.append(
            "prohibited design primitive: "
            + ", ".join(prohibited)
            + "; design phrases explicitly instead of relying on random search, fixed lanes, or one global rotation"
        )
    if metrics.unique_primitive_count < min_unique_primitives:
        errors.append(
            "insufficient motion vocabulary: "
            f"unique primitives={metrics.unique_primitive_count}, require >= {min_unique_primitives}"
        )
    if metrics.grouped_phrase_ratio < min_grouped_phrase_ratio:
        errors.append(
            "insufficient subgroup choreography: "
            f"grouped phrase ratio={metrics.grouped_phrase_ratio:.2f}, require >= {min_grouped_phrase_ratio:.2f}"
        )
    if metrics.multi_primitive_phrase_ratio < min_multi_primitive_phrase_ratio:
        errors.append(
            "insufficient phrase composition: "
            f"multi-primitive phrase ratio={metrics.multi_primitive_phrase_ratio:.2f}, "
            f"require >= {min_multi_primitive_phrase_ratio:.2f}"
        )
    if require_non_uniform_timing and not metrics.has_non_uniform_timing:
        errors.append("phrase timing is too uniform; vary durations before codegen")
    return errors


def _validate_phrase_groups(phrase: MotionPhrase, fleet_size: int, errors: list[str]) -> None:
    seen_group_ids: set[str] = set()
    assigned_drones: set[int] = set()
    for group in phrase.groups:
        if not group.group_id:
            errors.append(f"{phrase.phrase_id}: group id is required")
        elif group.group_id in seen_group_ids:
            errors.append(f"{phrase.phrase_id}: duplicate group id {group.group_id}")
        seen_group_ids.add(group.group_id)

        if not group.drones:
            errors.append(f"{phrase.phrase_id}: group {group.group_id} has no drones")
        if not group.role:
            errors.append(f"{phrase.phrase_id}: group {group.group_id} role is required")

        for drone_id in group.drones:
            if drone_id < 1 or drone_id > fleet_size:
                errors.append(f"{phrase.phrase_id}: drone id out of range: {drone_id}")
            if drone_id in assigned_drones:
                errors.append(f"{phrase.phrase_id}: drone {drone_id} appears in multiple groups")
            assigned_drones.add(drone_id)


def _validate_role_mapping(phrase: MotionPhrase, fleet_size: int, errors: list[str]) -> None:
    for drone_id, role in phrase.role_mapping.items():
        if drone_id < 1 or drone_id > fleet_size:
            errors.append(f"{phrase.phrase_id}: role mapping drone id out of range: {drone_id}")
        if not role:
            errors.append(f"{phrase.phrase_id}: role mapping for drone {drone_id} is empty")


def _count_overlapping_phrase_pairs(phrases: list[MotionPhrase]) -> int:
    count = 0
    for idx, left in enumerate(phrases):
        for right in phrases[idx + 1 :]:
            if left.start < right.end and right.start < left.end:
                count += 1
    return count
