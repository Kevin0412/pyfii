# -*- coding: utf-8 -*-
# 该文件根据检查结果做段级局部修正

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from .contracts import InspectionReport, SegmentSpec


@dataclass
class RefineResult:
    # 重整结果：记录是否有变更
    updated_segments: list[SegmentSpec]
    changed_segment_ids: list[str]


def refine_segments(
    segments: list[SegmentSpec],
    report: InspectionReport,
    allowed_segment_ids: set[str] | None = None,
) -> RefineResult:
    # 局部修正：仅修改指定问题段，且默认深拷贝避免原地污染
    issue_segments = {issue.segment_id for issue in report.issues}
    if allowed_segment_ids is not None:
        issue_segments = issue_segments.intersection(allowed_segment_ids)

    cloned = deepcopy(segments)
    changed: list[str] = []

    for seg in cloned:
        if seg.segment_id not in issue_segments:
            continue
        for track in seg.tracks:
            for op in track.ops:
                if op.op in {"VelXY", "VelZ"} and len(op.args) >= 2:
                    op.args[0] = max(20, int(op.args[0] * 0.85))
                    op.args[1] = max(50, int(op.args[1] * 0.85))
                if op.op == "delay" and op.args:
                    op.args[0] = int(op.args[0]) + 120
        changed.append(seg.segment_id)

    return RefineResult(updated_segments=cloned, changed_segment_ids=sorted(set(changed)))
