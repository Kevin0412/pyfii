# -*- coding: utf-8 -*-
# 该文件负责构建中文视觉检查提示词并解析结果

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .contracts import InspectionReport, SegmentIssue
from .qwen_client import QwenVideoClient


@dataclass
class InspectInput:
    # 检查输入：视频路径与表演目标
    video_path: str
    vibe_target: str


def build_visual_prompt(vibe_target: str) -> str:
    # 严格中文提示词：覆盖队形、流畅、转场、间距、气质、节奏
    return (
        "请检查这段无人机编队仿真画面，重点评估：\n\n"
        "1. 队形是否清晰\n"
        "2. 动作是否流畅\n"
        "3. 转场是否突兀\n"
        "4. 是否有明显过近、疑似碰撞或视觉拥挤\n"
        "5. 表演气质是否符合目标描述\n"
        "6. 节奏视觉上是否和时间规划基本一致\n\n"
        "用户目标：" + vibe_target + "\n\n"
        "请仅输出 JSON，不要输出 markdown 代码块："
        "{\"issues\":[{\"segment_id\":\"SG01\",\"severity\":\"low|medium|high\",\"detail\":\"...\",\"recommendation_zh\":\"...\"}],\"suggest_regenerate\":true|false}"
    )


def _extract_text_from_response(resp: dict[str, Any]) -> str:
    # 尽量从标准 chat completion 结构提取文本
    choices = resp.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(parts)
    return ""


def _strip_code_block(text: str) -> str:
    # 兼容模型返回 markdown 代码块的情况
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            return "\n".join(lines[1:-1]).strip()
    return t


def parse_inspection_response(text: str) -> InspectionReport:
    # 解析 JSON 结果，失败时降级为单条问题
    normalized = _strip_code_block(text)
    try:
        data = json.loads(normalized)
        issues = [
            SegmentIssue(
                segment_id=str(item.get("segment_id", "SG00")),
                severity=str(item.get("severity", "medium")),
                detail=str(item.get("detail", "")),
                recommendation_zh=str(item.get("recommendation_zh", "")),
            )
            for item in data.get("issues", [])
        ]
        return InspectionReport(issues=issues, suggest_regenerate=bool(data.get("suggest_regenerate", False)))
    except Exception:
        fallback = SegmentIssue(
            segment_id="SG00",
            severity="medium",
            detail=normalized[:500],
            recommendation_zh="请人工确认后再进行局部重生成。",
        )
        return InspectionReport(issues=[fallback], suggest_regenerate=True)


def inspect_with_qwen(client: QwenVideoClient, data: InspectInput) -> InspectionReport:
    # 上传视频并执行视觉评估
    video_url = client.upload_video(data.video_path)
    prompt = build_visual_prompt(data.vibe_target)
    response = client.inspect_video(video_url=video_url, prompt_zh=prompt)
    text = _extract_text_from_response(response)
    return parse_inspection_response(text)
