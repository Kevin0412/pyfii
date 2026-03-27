# -*- coding: utf-8 -*-
# 该文件封装本地/私有部署 Qwen 视频理解调用，并提供超时重试能力

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI


@dataclass
class RetryPolicy:
    # 重试策略：指数退避 + 抖动
    max_attempts: int = 5
    backoff_base_sec: float = 1.0
    backoff_factor: float = 2.0
    backoff_max_sec: float = 20.0
    jitter_ratio: float = 0.2


@dataclass
class TimeoutPolicy:
    # 超时策略：上传和推理分离
    upload_sec: float = 180.0
    inspect_sec: float = 420.0


@dataclass
class QwenConfig:
    # Qwen 接入配置：默认指向本机环境中的本地部署域名
    base_url: str = "https://ai.kevin0412.top/v1"
    api_key: str = "EMPTY"
    upload_endpoint: str = "https://ai.kevin0412.top/video-upload/v1/videos"
    model: str = "Qwen3.5-35B-A3B-FP8"
    fps: int = 2
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    timeout: TimeoutPolicy = field(default_factory=TimeoutPolicy)


class QwenRetryableError(RuntimeError):
    # 可重试异常：网络抖动、超时、限流、服务暂时不可用
    pass


class QwenNonRetryableError(RuntimeError):
    # 不可重试异常：请求格式、权限、模型配置等问题
    pass


class QwenVideoClient:
    # 视频理解客户端：上传视频后走 OpenAI 兼容接口
    def __init__(self, config: QwenConfig | None = None, telemetry_path: str | Path | None = None):
        self.config = config or QwenConfig()
        self.client = OpenAI(base_url=self.config.base_url, api_key=self.config.api_key)
        self.telemetry_path = Path(telemetry_path) if telemetry_path else None

    def _log_attempt(self, event: dict[str, Any]) -> None:
        # 记录每次调用尝试，便于长流程回溯
        if not self.telemetry_path:
            return
        self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        with self.telemetry_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False))
            f.write("\n")

    def _is_retryable_status(self, status_code: int) -> bool:
        # 状态码分类：429/5xx/408 可重试
        return status_code in {408, 429, 500, 502, 503, 504}

    def _sleep_backoff(self, attempt: int) -> None:
        # 指数退避 + 抖动
        delay = min(
            self.config.retry.backoff_max_sec,
            self.config.retry.backoff_base_sec * (self.config.retry.backoff_factor ** (attempt - 1)),
        )
        jitter = delay * self.config.retry.jitter_ratio
        time.sleep(max(0.0, delay + random.uniform(-jitter, jitter)))

    def _retry_loop(self, action: str, func):
        # 通用重试执行器
        last_exc: Exception | None = None
        for attempt in range(1, self.config.retry.max_attempts + 1):
            start = time.time()
            try:
                result = func()
                self._log_attempt(
                    {
                        "action": action,
                        "attempt": attempt,
                        "ok": True,
                        "elapsed_sec": round(time.time() - start, 3),
                        "model": self.config.model,
                    }
                )
                return result
            except QwenNonRetryableError:
                raise
            except QwenRetryableError as exc:
                last_exc = exc
                self._log_attempt(
                    {
                        "action": action,
                        "attempt": attempt,
                        "ok": False,
                        "retryable": True,
                        "error": str(exc),
                        "elapsed_sec": round(time.time() - start, 3),
                        "model": self.config.model,
                    }
                )
                if attempt >= self.config.retry.max_attempts:
                    break
                self._sleep_backoff(attempt)
            except Exception as exc:
                # 未知异常按可重试处理，直到达到上限
                last_exc = exc
                self._log_attempt(
                    {
                        "action": action,
                        "attempt": attempt,
                        "ok": False,
                        "retryable": True,
                        "error": f"unexpected: {exc}",
                        "elapsed_sec": round(time.time() - start, 3),
                        "model": self.config.model,
                    }
                )
                if attempt >= self.config.retry.max_attempts:
                    break
                self._sleep_backoff(attempt)
        raise QwenRetryableError(f"{action} failed after retries: {last_exc}")

    def upload_video(self, video_path: str | Path) -> str:
        # 上传本地视频，返回可访问 URL
        path = Path(video_path)
        if not path.is_file():
            raise FileNotFoundError(f"video file not found: {path}")

        def _do_upload() -> str:
            with path.open("rb") as f:
                files = {"file": (path.name, f, "video/mp4")}
                try:
                    response = httpx.post(
                        self.config.upload_endpoint,
                        files=files,
                        timeout=self.config.timeout.upload_sec,
                    )
                except httpx.TimeoutException as exc:
                    raise QwenRetryableError(f"upload timeout: {exc}") from exc
                except httpx.RequestError as exc:
                    raise QwenRetryableError(f"upload request error: {exc}") from exc

            if self._is_retryable_status(response.status_code):
                raise QwenRetryableError(f"upload status={response.status_code}")
            if response.status_code >= 400:
                raise QwenNonRetryableError(f"upload status={response.status_code} body={response.text[:200]}")

            payload = response.json()
            if "url" in payload:
                return str(payload["url"])
            if isinstance(payload.get("payload"), dict) and "url" in payload["payload"]:
                return str(payload["payload"]["url"])
            raise QwenRetryableError("upload response missing url")

        return self._retry_loop("upload_video", _do_upload)

    def inspect_video(self, video_url: str, prompt_zh: str, max_tokens: int = 8192) -> dict[str, Any]:
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

        def _do_inspect() -> dict[str, Any]:
            try:
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.2,
                    top_p=0.9,
                    timeout=self.config.timeout.inspect_sec,
                    extra_body={
                        "top_k": 20,
                        "mm_processor_kwargs": {"fps": self.config.fps, "do_sample_frames": True},
                    },
                )
                return response.model_dump()
            except Exception as exc:
                msg = str(exc)
                # OpenAI SDK 异常在不同版本类型不稳定，采用文本+关键字分类
                lower = msg.lower()
                if any(x in lower for x in ["timeout", "timed out", "429", "503", "502", "500", "connection"]):
                    raise QwenRetryableError(f"inspect retryable error: {msg}") from exc
                if any(x in lower for x in ["401", "403", "404", "invalid", "model", "permission"]):
                    raise QwenNonRetryableError(f"inspect non-retryable error: {msg}") from exc
                raise QwenRetryableError(f"inspect unknown error: {msg}") from exc

        return self._retry_loop("inspect_video", _do_inspect)
