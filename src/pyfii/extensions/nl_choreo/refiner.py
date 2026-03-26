# -*- coding: utf-8 -*-
# 该文件根据检查结果做段级局部修正

from __future__ import annotations

from dataclasses import dataclass

from .contracts import InspectionReport, SegmentSpec


@dataclass
class RefineResult:
    # 重整结果：记录是否有变更
    updated_segments: list[SegmentSpec]
    changed_segment_ids: list[str]


def refine_segments(segments: list[SegmentSpec], report: InspectionReport) -> RefineResult:
    # 简化版局部修正：按问题段降低速度并增加缓冲
    issue_segments = {issue.segment_id for issue in report.issues}
    changed: list[str] = []

    for seg in segments:
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

    return RefineResult(updated_segments=segments, changed_segment_ids=sorted(set(changed)))
