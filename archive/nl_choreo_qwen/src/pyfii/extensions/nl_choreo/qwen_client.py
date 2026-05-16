# -*- coding: utf-8 -*-
# 该文件封装 Qwen 视频理解调用，并提供超时重试能力

from __future__ import annotations

import json
import os
import random
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - optional dependency for use_qwen=False workflows
    httpx = None  # type: ignore[assignment]

try:
    from openai import OpenAI
except ModuleNotFoundError:  # pragma: no cover - optional dependency for use_qwen=False workflows
    OpenAI = None  # type: ignore[assignment]


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
    # OpenAI-compatible provider 接入配置
    base_url: str = ""
    api_key: str = ""
    upload_endpoint: str = ""
    model: str = "Qwen3.5-35B-A3B-FP8"
    fps: int = 2
    use_local_video_path: bool = False
    local_video_mode: str = "file_url"  # file_url | path_text
    inspect_auto_fallback_to_upload: bool = False
    design_temperature: float = 0.85
    design_top_p: float = 0.95
    codegen_temperature: float = 0.1
    codegen_top_p: float = 0.9
    enable_thinking: bool | None = None
    reasoning_effort: str | None = None
    max_output_tokens: int | None = None
    thinking: dict[str, Any] = field(default_factory=dict)
    extra_body: dict[str, Any] = field(default_factory=dict)
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    timeout: TimeoutPolicy = field(default_factory=TimeoutPolicy)


_PROVIDER_ENV_PREFIXES = {
    "qwen": "PYFII_QWEN",
    "custom_gpt": "PYFII_CUSTOM_GPT",
    "deepseek": "PYFII_DEEPSEEK",
    "deepseek_pro": "PYFII_DEEPSEEK_PRO",
}

_QWEN_CONFIG_KEYS = {
    "base_url",
    "api_key",
    "upload_endpoint",
    "model",
    "fps",
    "use_local_video_path",
    "local_video_mode",
    "inspect_auto_fallback_to_upload",
    "design_temperature",
    "design_top_p",
    "codegen_temperature",
    "codegen_top_p",
    "enable_thinking",
    "reasoning_effort",
    "max_output_tokens",
    "thinking",
    "extra_body",
}

_ROOT_PROVIDER_OWNED_KEYS = {
    "api_key",
    "base_url",
    "enable_thinking",
    "extra_body",
    "max_output_tokens",
    "model",
    "reasoning_effort",
    "thinking",
    "upload_endpoint",
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _provider_env_prefix(provider: str) -> str:
    return _PROVIDER_ENV_PREFIXES.get(provider, f"PYFII_{provider.upper().replace('-', '_')}")


def _first_value(*values: Any, default: Any = "") -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return default


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def qwen_config_from_dict(
    data: Mapping[str, Any],
    *,
    provider: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> QwenConfig:
    env = os.environ if environ is None else environ
    provider_name = str(provider or data.get("provider") or env.get("PYFII_NL_CHOREO_PROVIDER") or "qwen")
    providers = _mapping(data.get("providers"))
    provider_data = _mapping(providers.get(provider_name) or data.get(provider_name))

    merged: dict[str, Any] = {}
    for key in _QWEN_CONFIG_KEYS:
        if key in data and (provider_name == "qwen" or key not in _ROOT_PROVIDER_OWNED_KEYS):
            merged[key] = data[key]
    merged.update({k: v for k, v in provider_data.items() if k in _QWEN_CONFIG_KEYS})

    retry_data = dict(_mapping(data.get("retry")))
    retry_data.update(_mapping(provider_data.get("retry")))
    timeout_data = dict(_mapping(data.get("timeout")))
    timeout_data.update(_mapping(provider_data.get("timeout")))
    extra_body = dict(_mapping(data.get("extra_body")))
    extra_body.update(_mapping(provider_data.get("extra_body")))
    thinking = dict(_mapping(data.get("thinking")))
    thinking.update(_mapping(provider_data.get("thinking")))

    prefix = _provider_env_prefix(provider_name)
    max_output_tokens = _first_value(
        merged.get("max_output_tokens"),
        env.get(f"{prefix}_MAX_OUTPUT_TOKENS"),
        default=None,
    )
    enable_thinking = _first_value(merged.get("enable_thinking"), env.get(f"{prefix}_ENABLE_THINKING"), default=None)
    return QwenConfig(
        base_url=str(_first_value(merged.get("base_url"), env.get(f"{prefix}_BASE_URL"))),
        api_key=str(_first_value(merged.get("api_key"), env.get(f"{prefix}_API_KEY"))),
        upload_endpoint=str(
            _first_value(merged.get("upload_endpoint"), env.get(f"{prefix}_UPLOAD_ENDPOINT"), env.get("PYFII_QWEN_UPLOAD_ENDPOINT"))
        ),
        model=str(_first_value(merged.get("model"), env.get(f"{prefix}_MODEL"), default=QwenConfig.model)),
        fps=int(_first_value(merged.get("fps"), env.get(f"{prefix}_FPS"), default=QwenConfig.fps)),
        use_local_video_path=_as_bool(merged.get("use_local_video_path"), QwenConfig.use_local_video_path),
        local_video_mode=str(_first_value(merged.get("local_video_mode"), default=QwenConfig.local_video_mode)),
        inspect_auto_fallback_to_upload=_as_bool(
            merged.get("inspect_auto_fallback_to_upload"),
            QwenConfig.inspect_auto_fallback_to_upload,
        ),
        design_temperature=float(
            _first_value(merged.get("design_temperature"), default=QwenConfig.design_temperature)
        ),
        design_top_p=float(_first_value(merged.get("design_top_p"), default=QwenConfig.design_top_p)),
        codegen_temperature=float(
            _first_value(merged.get("codegen_temperature"), default=QwenConfig.codegen_temperature)
        ),
        codegen_top_p=float(_first_value(merged.get("codegen_top_p"), default=QwenConfig.codegen_top_p)),
        enable_thinking=None if enable_thinking is None else _as_bool(enable_thinking),
        reasoning_effort=_first_value(
            merged.get("reasoning_effort"),
            env.get(f"{prefix}_REASONING_EFFORT"),
            default=None,
        ),
        max_output_tokens=None if max_output_tokens is None else int(max_output_tokens),
        thinking=thinking,
        extra_body=extra_body,
        retry=RetryPolicy(**retry_data),
        timeout=TimeoutPolicy(**timeout_data),
    )


AIProviderConfig = QwenConfig


def ai_provider_config_from_dict(
    data: Mapping[str, Any],
    *,
    provider: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> AIProviderConfig:
    return qwen_config_from_dict(data, provider=provider, environ=environ)


class QwenRetryableError(RuntimeError):
    # 可重试异常：网络抖动、超时、限流、服务暂时不可用
    pass


class QwenNonRetryableError(RuntimeError):
    # 不可重试异常：请求格式、权限、模型配置等问题
    pass


def extract_response_text(resp: dict[str, Any]) -> str:
    choices = resp.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {}) or {}
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text", ""))
                if text:
                    parts.append(text)
        if parts:
            return "\n".join(parts)
    reasoning_content = message.get("reasoning_content")
    if isinstance(reasoning_content, str):
        return reasoning_content
    if isinstance(reasoning_content, list):
        parts = []
        for item in reasoning_content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text", ""))
                if text:
                    parts.append(text)
            elif isinstance(item, str) and item:
                parts.append(item)
        if parts:
            return "\n".join(parts)
    if content is None:
        return ""
    return str(content)


class QwenVideoClient:
    # 视频理解客户端：上传视频后走 OpenAI 兼容接口
    def __init__(self, config: QwenConfig | None = None, telemetry_path: str | Path | None = None):
        self.config = config or QwenConfig()
        self.client: OpenAI | None = None
        self.telemetry_path = Path(telemetry_path) if telemetry_path else None
        self._token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    @property
    def token_usage(self) -> dict[str, int]:
        return dict(self._token_usage)

    def _accumulate_usage(self, dumped: dict[str, Any]) -> dict[str, int]:
        usage = dumped.get("usage", {}) or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)
        self._token_usage["prompt_tokens"] += prompt_tokens
        self._token_usage["completion_tokens"] += completion_tokens
        self._token_usage["total_tokens"] += total_tokens
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    def _log_attempt(self, event: dict[str, Any]) -> None:
        # 记录每次调用尝试，便于长流程回溯
        if not self.telemetry_path:
            return
        self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        with self.telemetry_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False))
            f.write("\n")

    def _require_client(self) -> Any:
        if self.client is None:
            raise QwenNonRetryableError("openai package is required when use_qwen=True")
        return self.client

    def _is_retryable_status(self, status_code: int) -> bool:
        # 状态码分类：429/5xx/408 可重试
        return status_code in {408, 429, 500, 502, 503, 504}

    def _openai_client(self) -> OpenAI:
        if self.client is None:
            if OpenAI is None:
                raise QwenNonRetryableError("openai package is required when use_qwen=True")
            if not self.config.base_url:
                raise QwenNonRetryableError(
                    "AI provider base_url is not configured. Pass AIProviderConfig(base_url=..., api_key=..., "
                    "upload_endpoint=...) from the calling workflow."
                )
            api_key = self.config.api_key or "EMPTY"
            self.client = OpenAI(base_url=self.config.base_url, api_key=api_key)
        return self.client

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
        if not self.config.upload_endpoint:
            raise QwenNonRetryableError(
                "AI provider upload_endpoint is not configured. Pass AIProviderConfig(base_url=..., api_key=..., "
                "upload_endpoint=...) from the calling workflow."
            )

        def _do_upload() -> str:
            if httpx is None:
                raise QwenNonRetryableError("httpx package is required for video upload")
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

    def _to_file_url(self, p: str) -> str:
        path = Path(p).expanduser().resolve()
        return f"file://{quote(path.as_posix(), safe='/:._-')}"

    def _build_inspect_content(self, video_urls: list[str], prompt_zh: str, local_mode: str) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = []
        for u in video_urls:
            is_remote = u.startswith("http://") or u.startswith("https://") or u.startswith("file://")
            if is_remote:
                content.append({"type": "video_url", "video_url": {"url": u}})
            elif local_mode == "file_url":
                content.append({"type": "video_url", "video_url": {"url": self._to_file_url(u)}})
            else:
                content.append({"type": "text", "text": f"[local_video_path] {u}"})
        content.append({"type": "text", "text": prompt_zh})
        return content

    def _completion_kwargs(self, **kwargs: Any) -> dict[str, Any]:
        payload = dict(kwargs)
        if self.config.reasoning_effort:
            payload["reasoning_effort"] = self.config.reasoning_effort

        extra_body = dict(self.config.extra_body)
        extra_body.update(dict(payload.get("extra_body") or {}))
        if self.config.thinking:
            extra_body["thinking"] = dict(self.config.thinking)
        if extra_body.get("thinking"):
            payload.pop("temperature", None)
            payload.pop("top_p", None)
        if self.config.enable_thinking is not None:
            chat_template_kwargs = dict(extra_body.get("chat_template_kwargs") or {})
            chat_template_kwargs["enable_thinking"] = bool(self.config.enable_thinking)
            extra_body["chat_template_kwargs"] = chat_template_kwargs
        if extra_body:
            payload["extra_body"] = extra_body
        return payload

    def inspect_video(self, video_urls: list[str], prompt_zh: str, max_tokens: int = 8192) -> dict[str, Any]:
        # 使用中文提示词进行视觉评估（可携带多路视频）
        local_mode = self.config.local_video_mode if self.config.use_local_video_path else "video_url"
        content = self._build_inspect_content(video_urls=video_urls, prompt_zh=prompt_zh, local_mode=local_mode)
        messages = [{"role": "user", "content": content}]

        def _do_inspect() -> dict[str, Any]:
            try:
                response = self._openai_client().chat.completions.create(
                    **self._completion_kwargs(
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
                )
                dumped = response.model_dump()
                usage = self._accumulate_usage(dumped)
                self._log_attempt(
                    {
                        "action": "inspect_video_usage",
                        "ok": True,
                        "usage": usage,
                        "usage_cumulative": dict(self._token_usage),
                        "model": self.config.model,
                    }
                )
                return dumped
            except QwenNonRetryableError:
                raise
            except Exception as exc:
                msg = str(exc)
                lower = msg.lower()
                if (
                    self.config.use_local_video_path
                    and self.config.inspect_auto_fallback_to_upload
                    and local_mode == "file_url"
                    and any(k in lower for k in ["400", "invalid", "validation", "video_url", "schema"])
                ):
                    uploaded_urls = [self.upload_video(p) for p in video_urls]
                    retry_content = self._build_inspect_content(
                        video_urls=uploaded_urls,
                        prompt_zh=prompt_zh,
                        local_mode="file_url",
                    )
                    retry_messages = [{"role": "user", "content": retry_content}]
                    response = self._openai_client().chat.completions.create(
                        **self._completion_kwargs(
                            model=self.config.model,
                            messages=retry_messages,
                            max_tokens=max_tokens,
                            temperature=0.2,
                            top_p=0.9,
                            timeout=self.config.timeout.inspect_sec,
                            extra_body={
                                "top_k": 20,
                                "mm_processor_kwargs": {"fps": self.config.fps, "do_sample_frames": True},
                            },
                        )
                    )
                    dumped = response.model_dump()
                    usage = self._accumulate_usage(dumped)
                    self._log_attempt(
                        {
                            "action": "inspect_video_local_fallback_upload",
                            "ok": True,
                            "usage": usage,
                            "usage_cumulative": dict(self._token_usage),
                            "model": self.config.model,
                        }
                    )
                    return dumped
                # OpenAI SDK 异常在不同版本类型不稳定，采用文本+关键字分类
                if any(x in lower for x in ["timeout", "timed out", "429", "503", "502", "500", "connection"]):
                    raise QwenRetryableError(f"inspect retryable error: {msg}") from exc
                if any(x in lower for x in ["401", "403", "404", "invalid", "model", "permission"]):
                    raise QwenNonRetryableError(f"inspect non-retryable error: {msg}") from exc
                raise QwenRetryableError(f"inspect unknown error: {msg}") from exc

        return self._retry_loop("inspect_video", _do_inspect)

    def generate_text(
        self,
        prompt_zh: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        action_name: str = "generate_python_code",
    ) -> str:
        # 通用文本生成：允许按阶段设置不同温度参数
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt_zh}]}]
        effective_max_tokens = int(
            max_tokens
            if max_tokens is not None
            else self.config.max_output_tokens
            if self.config.max_output_tokens is not None
            else 8192
        )

        def _do_generate() -> str:
            try:
                response = self._openai_client().chat.completions.create(
                    **self._completion_kwargs(
                        model=self.config.model,
                        messages=messages,
                        max_tokens=effective_max_tokens,
                        temperature=float(self.config.codegen_temperature if temperature is None else temperature),
                        top_p=float(self.config.codegen_top_p if top_p is None else top_p),
                        timeout=self.config.timeout.inspect_sec,
                    )
                )
                dumped = response.model_dump()
                usage = self._accumulate_usage(dumped)
                self._log_attempt(
                    {
                        "action": f"{action_name}_usage",
                        "ok": True,
                        "usage": usage,
                        "usage_cumulative": dict(self._token_usage),
                        "model": self.config.model,
                    }
                )
                choices = dumped.get("choices", [])
                if not choices:
                    raise QwenRetryableError("code generation empty choices")
                return extract_response_text(dumped)
            except QwenNonRetryableError:
                raise
            except Exception as exc:
                msg = str(exc)
                lower = msg.lower()
                if any(x in lower for x in ["timeout", "timed out", "429", "503", "502", "500", "connection"]):
                    raise QwenRetryableError(f"generate retryable error: {msg}") from exc
                if any(x in lower for x in ["401", "403", "404", "invalid", "model", "permission"]):
                    raise QwenNonRetryableError(f"generate non-retryable error: {msg}") from exc
                raise QwenRetryableError(f"generate unknown error: {msg}") from exc

        return self._retry_loop(action_name, _do_generate)

    def generate_python_code(self, prompt_zh: str, max_tokens: int | None = None) -> str:
        return self.generate_text(prompt_zh=prompt_zh, max_tokens=max_tokens, action_name="generate_python_code")

    def generate_design_text(self, prompt_zh: str, max_tokens: int | None = None) -> str:
        return self.generate_text(
            prompt_zh=prompt_zh,
            max_tokens=max_tokens,
            temperature=float(self.config.design_temperature),
            top_p=float(self.config.design_top_p),
            action_name="generate_design_text",
        )
