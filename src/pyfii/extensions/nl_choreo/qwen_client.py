# -*- coding: utf-8 -*-
# 该文件封装本地/私有部署 Qwen 视频理解调用

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI


@dataclass
class QwenConfig:
    # Qwen 接入配置：默认兼容现有 qwen3.5_video.py 方案
    base_url: str = "https://ai.kevin0412.top/v1"
    api_key: str = "EMPTY"
    upload_endpoint: str = "https://ai.kevin0412.top/video-upload/v1/videos"
    model: str = "Qwen/Qwen3.5-27B-FP8"
    fps: int = 2


class QwenVideoClient:
    # 视频理解客户端：上传视频后走 OpenAI 兼容接口
    def __init__(self, config: QwenConfig | None = None):
        self.config = config or QwenConfig()
        self.client = OpenAI(base_url=self.config.base_url, api_key=self.config.api_key)

    def upload_video(self, video_path: str | Path) -> str:
        # 上传本地视频，返回可访问 URL
        path = Path(video_path)
        if not path.is_file():
            raise FileNotFoundError(f"video file not found: {path}")
        with path.open("rb") as f:
            files = {"file": (path.name, f, "video/mp4")}
            response = httpx.post(self.config.upload_endpoint, files=files, timeout=120.0)
        response.raise_for_status()
        payload = response.json()
        if "url" in payload:
            return str(payload["url"])
        if isinstance(payload.get("payload"), dict) and "url" in payload["payload"]:
            return str(payload["payload"]["url"])
        raise ValueError("upload response missing url")

    def inspect_video(self, video_url: str, prompt_zh: str, max_tokens: int = 4096) -> dict[str, Any]:
        # 使用中文提示词进行视觉评估
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "video_url", "video_url": {"url": video_url}},
                    {"type": "text", "text": prompt_zh},
                ],
            }
        ]
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.2,
            top_p=0.9,
            extra_body={
                "top_k": 20,
                "mm_processor_kwargs": {"fps": self.config.fps, "do_sample_frames": True},
            },
        )
        return response.model_dump()
