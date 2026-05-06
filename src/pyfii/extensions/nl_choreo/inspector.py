# -*- coding: utf-8 -*-
# 该文件负责构建中文视觉检查提示词并解析结果

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .contracts import InspectionReport, SegmentIssue
from .qwen_client import QwenVideoClient, extract_response_text


@dataclass
class InspectInput:
    # 检查输入：视频路径与表演目标
    video_path: str
    vibe_target: str
    video_paths: list[str] | None = None


def build_visual_prompt(vibe_target: str) -> str:
    # 严格中文提示词：覆盖队形、流畅、转场、间距、气质、节奏与运动质量
    return (
        "请检查这段无人机编队仿真画面，重点评估：\n\n"
        "1. 队形是否清晰\n"
        "2. 动作是否流畅\n"
        "3. 转场是否突兀\n"
        "4. 是否有明显过近、疑似碰撞或视觉拥挤\n"
        "5. 表演气质是否符合目标描述\n"
        "6. 节奏视觉上是否和时间规划基本一致\n"
        "7. 是否存在明显大尺度位移（建议主轴跨度至少约320cm）\n"
        "8. 动作频率是否足够（是否存在超过4秒的明显静止/停滞）\n"
        "9. 队形变化是否多样（避免反复同构图形、同向同速）\n"
        "10. 是否体现分组关系与呼应（而非全机同路径同目标）\n"
        "11. 是否存在固定中心机模式：一架无人机长期停在中心，其他无人机始终围绕它运动\n"
        "12. 视觉重心是否随音乐段落变化（中心/领舞/外圈职责是否有轮换）\n"
        "13. 复杂度是否来自清晰的段落/分组/轨迹设计，而不是杂乱堆坐标或无意义频繁抖动\n"
        "14. 是否过度依赖单一环形/中心旋转套路，缺少多中心、线性、对角、符号或前后场交换等非中心化结构\n"
        "15. 若存在角色交换，是否能看出中间路径或错峰转场，而不是突然互相对穿\n"
        "16. 问题主要出在关键动作设计，还是出在相邻关键动作之间的衔接/速度调节\n"
        "17. 速度是否有音乐层次：是否存在慢进入、急促进入、错峰追随、高潮加速，而不是全程同速\n\n"
        "判定规则：若第4项存在高风险，或第7/8/9/10/11/12/13/14/15/16/17项明显不足，请设置 suggest_regenerate=true。\n\n"
        "用户目标：" + vibe_target + "\n\n"
        "请仅输出 JSON，不要输出 markdown 代码块："
        "{\"issues\":[{\"segment_id\":\"SG01\",\"severity\":\"low|medium|high\",\"detail\":\"...\",\"recommendation_zh\":\"...\"}],\"suggest_regenerate\":true|false}"
    )


def _extract_text_from_response(resp: dict[str, Any]) -> str:
    # 尽量从标准 chat completion 结构提取文本，并兼容 reasoning_content 回退
    return extract_response_text(resp)


def _extract_finish_reason(resp: dict[str, Any]) -> str:
    choices = resp.get("choices", [])
    if not choices:
        return ""
    return str(choices[0].get("finish_reason", "") or "")


def _looks_truncated(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return t[-1] not in "。！？.!?；;：:】》）)]\n"


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
    paths = data.video_paths or [data.video_path]
    if client.config.use_local_video_path:
        video_inputs = [str(p) for p in paths]
    else:
        video_inputs = [client.upload_video(p) for p in paths]
    prompt = build_visual_prompt(data.vibe_target)
    response = client.inspect_video(video_urls=video_inputs, prompt_zh=prompt)
    text = _extract_text_from_response(response)
    return parse_inspection_response(text)


def build_final_design_narration_prompt(vibe_target: str, script_text: str) -> str:
    # 终稿解说提示：参考 qwen3.5_video.py 的“视频+代码”叙述风格
    trimmed = (script_text or "")[:12000]
    return (
        "这是一段无人机编队飞行表演（蜂群舞蹈）仿真视频，请先简述你的设计意图，"
        "再按时间阶段解释关键队形与转场，并说明如何兼顾安全间距与艺术表现。\n"
        "要求：\n"
        "1) 只输出中文纯文本，不要 markdown 代码块；\n"
        "2) 描述要具体到编队关系与层次变化，避免空泛；\n"
        "3) 最后给出 3 条可进一步提升多样性的建议。\n\n"
        f"用户目标：{vibe_target}\n\n"
        "该视频对应脚本（节选）：\n"
        f"{trimmed}"
    )


def generate_final_design_narration(
    client: QwenVideoClient,
    *,
    vibe_target: str,
    script_text: str,
    video_paths: list[str],
) -> str:
    # 终稿阶段让 Qwen 输出设计解说文本
    if client.config.use_local_video_path:
        video_inputs = [str(p) for p in video_paths]
    else:
        video_inputs = [client.upload_video(p) for p in video_paths]
    prompt = build_final_design_narration_prompt(vibe_target=vibe_target, script_text=script_text)

    def _continue_if_needed(text: str, force_continue: bool = False) -> str:
        out = text.strip()
        for _ in range(2):
            if out and not force_continue and not _looks_truncated(out):
                return out
            continuation_prompt = (
                "你上一条终稿解说被截断了。请在不重复前文的前提下继续补全到自然收尾。"
                "要求：中文纯文本；补全“时间阶段说明+安全与艺术平衡+3条多样性建议”。\n\n"
                f"用户目标：{vibe_target}\n\n"
                f"已生成前文（末尾可能被截断）：\n{out[-2500:]}"
            )
            addon = _strip_code_block(client.generate_design_text(prompt_zh=continuation_prompt, max_tokens=1024).strip())
            if not addon:
                break
            out = (out + "\n" + addon).strip() if out else addon.strip()
            force_continue = False
        return out

    # 优先多路视频；若显存/负载压力导致失败，逐级降载并保留可用解说产物
    attempts: list[tuple[list[str], int]] = []
    if video_inputs:
        attempts.append((video_inputs, 3072))
        attempts.append((video_inputs[:1], 3072))
    last_exc: Exception | None = None
    for urls, max_tokens in attempts:
        try:
            response = client.inspect_video(video_urls=urls, prompt_zh=prompt, max_tokens=max_tokens)
            text = _strip_code_block(_extract_text_from_response(response).strip())
            if not text:
                continue
            finish_reason = _extract_finish_reason(response).lower()
            force_continue = finish_reason == "length"
            completed = _continue_if_needed(text, force_continue=force_continue)
            if completed:
                return completed
        except Exception as exc:
            last_exc = exc

    # 最后降级为纯文本设计解说，保证产物可生成（非视频多模态）
    fallback_prompt = (
        "请基于以下用户目标与无人机脚本，输出终稿设计解说。"
        "先说明整体设计意图，再按时间阶段解释关键队形与转场，"
        "并说明如何兼顾安全间距与艺术表现。最后给出3条提升多样性的建议。\n\n"
        f"用户目标：{vibe_target}\n\n"
        f"脚本（节选）：\n{(script_text or '')[:12000]}"
    )
    try:
        text = _strip_code_block(client.generate_design_text(prompt_zh=fallback_prompt, max_tokens=3072).strip())
        text = _continue_if_needed(text)
        if text:
            return text
    except Exception as exc:
        last_exc = exc

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("final narration generation failed with empty response")
