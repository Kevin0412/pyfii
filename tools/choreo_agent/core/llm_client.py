"""LLM Client — 统一调用接口"""
import json
import math
import signal
import threading
import time
import httpx
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "ai_providers.local.json"
DEFAULT_WALL_TIMEOUT_S = 900
DEFAULT_READ_TIMEOUT_S = 300
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF_S = 2.0


@dataclass
class LlmResponse:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_text: str = ""
    system_prompt_chars: int | None = None
    user_prompt_chars: int | None = None
    prompt_chars: int | None = None
    estimated_input_tokens: int | None = None
    estimated_output_tokens: int | None = None
    prompt_cache_hit_tokens: int | None = None
    prompt_cache_miss_tokens: int | None = None
    total_tokens: int | None = None
    raw_usage: dict[str, Any] | None = None


class LlmTimeoutError(TimeoutError):
    pass


class LlmRequestError(RuntimeError):
    pass


def load_config(provider_name: str = "deepseek") -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"missing provider config: {CONFIG_PATH}")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    providers = cfg.get("providers", {})
    if provider_name not in providers:
        raise KeyError(f"unknown provider: {provider_name}")
    return providers[provider_name]


def list_provider_names() -> list[str]:
    """已配置的 provider 名称列表；配置文件缺失（本机未配置）时返回空列表，
    供 UI 层拼错误提示用，不用于校验（校验仍走 load_config 的 KeyError）。"""
    if not CONFIG_PATH.exists():
        return []
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return sorted(cfg.get("providers", {}).keys())


def chat(
    system: str,
    user: str,
    provider: str = "deepseek",
    temperature: float = 0.2,
    history: list[dict] | None = None,
    on_delta: Callable[[str], None] | None = None,
    on_reasoning_delta: Callable[[str], None] | None = None,
    on_heartbeat: Callable[[], None] | None = None,
) -> LlmResponse:
    """发送 chat completion 请求

    history: 之前轮次的 {role, content} 列表（role 只能是 user/assistant，严格交替），
    插在 system 之后、这一轮 user 之前。默认 None——不传时 payload 与历史行为字节相同
    （这是持久会话历史重构可以按纯重构验收的支点，见 core/conversation.py）。
    """
    cfg = load_config(provider)

    # 协议风格：openai（/chat/completions，默认）或 anthropic（/v1/messages）。
    # 两者共用下面的墙钟/重试/SIGALRM 包裹，只是 url/headers/payload 和流式解析不同。
    api_style = str(cfg.get("api_style", "openai")).lower()
    # CLI/debug callers pass callbacks specifically because they need live visibility.
    # In that case force streaming even if an older local config still has stream=false.
    use_stream = bool(cfg.get("stream", True) or on_delta or on_reasoning_delta or on_heartbeat)

    if api_style == "anthropic":
        # Anthropic Messages API：system 是顶层字段（不是一条消息），messages 只有
        # user/assistant，max_tokens 必填，鉴权用 x-api-key + anthropic-version。
        payload = {
            "model": cfg["model"],
            "max_tokens": cfg.get("max_output_tokens", 16384),
            "system": system,
            "messages": (history or []) + [{"role": "user", "content": user}],
        }
        # 新版 Claude（Opus 4.x 等）弃用 temperature——provider 配 omit_temperature:true 时不发送；
        # 其它 anthropic 端点（如 DeepSeek anthropic）默认仍带 temperature，行为不变。
        if not cfg.get("omit_temperature", False):
            payload["temperature"] = temperature
        payload.update(cfg.get("extra_body", {}))
        if use_stream:
            payload["stream"] = True
        headers = {
            "x-api-key": cfg["api_key"],
            "anthropic-version": cfg.get("anthropic_version", "2023-06-01"),
            "content-type": "application/json",
        }
    else:
        payload = {
            "model": cfg["model"],
            "messages": (
                [{"role": "system", "content": system}]
                + (history or [])
                + [{"role": "user", "content": user}]
            ),
            "temperature": temperature,
            "max_tokens": cfg.get("max_output_tokens", 16384),
        }
        payload.update(cfg.get("extra_body", {}))
        if use_stream:
            payload["stream"] = True
            stream_options = cfg.get("stream_options")
            if stream_options is None and _should_request_stream_usage(cfg):
                stream_options = {"include_usage": True}
            if stream_options:
                payload["stream_options"] = stream_options
        headers = {
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        }

    wall_timeout_s = float(cfg.get("timeout_s", DEFAULT_WALL_TIMEOUT_S))
    read_timeout_s = float(cfg.get("read_timeout_s", min(DEFAULT_READ_TIMEOUT_S, wall_timeout_s)))
    no_content_timeout_s = float(cfg.get("no_content_timeout_s", STREAM_NO_CONTENT_TIMEOUT_S))
    timeout = httpx.Timeout(
        connect=float(cfg.get("connect_timeout_s", 30)),
        read=read_timeout_s,
        write=float(cfg.get("write_timeout_s", 30)),
        pool=float(cfg.get("pool_timeout_s", 30)),
    )

    def on_timeout(_signum, _frame):
        raise LlmTimeoutError(
            f"LLM request timed out after {wall_timeout_s:.0f}s: "
            f"provider={provider} model={cfg['model']}"
        )

    # SIGALRM 只能装在主线程；worker 线程靠传入流式循环的单调时钟 deadline——
    # no-content 看门狗会被持续的 reasoning 增量不断重置，挡不住 40 分钟的长篇
    # 思考流，deadline 是线程内唯一的硬性时长上限。
    use_alarm = threading.current_thread() is threading.main_thread()
    if use_alarm:
        previous_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, on_timeout)
        signal.setitimer(signal.ITIMER_REAL, wall_timeout_s)
    started_at = time.monotonic()
    try:
        if api_style == "anthropic":
            url = f"{cfg['base_url'].rstrip('/')}/v1/messages"
            stream_fn = _chat_stream_anthropic
            once_fn = _chat_once_anthropic
        else:
            url = f"{cfg['base_url'].rstrip('/')}/chat/completions"
            stream_fn = _chat_stream
            once_fn = _chat_once
        attempts = max(1, int(cfg.get("max_retries", DEFAULT_MAX_RETRIES)) + 1)
        retry_backoff_s = float(cfg.get("retry_backoff_s", DEFAULT_RETRY_BACKOFF_S))
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            if time.monotonic() - started_at > wall_timeout_s:
                raise LlmTimeoutError(
                    f"LLM request exceeded wall timeout {wall_timeout_s:.0f}s before attempt {attempt}: "
                    f"provider={provider} model={cfg['model']}"
                )
            try:
                if use_stream:
                    response = stream_fn(
                        url=url,
                        payload=payload,
                        headers=headers,
                        timeout=timeout,
                        fallback_model=cfg["model"],
                        on_delta=on_delta,
                        on_reasoning_delta=on_reasoning_delta,
                        on_heartbeat=on_heartbeat,
                        no_content_timeout_s=no_content_timeout_s,
                        deadline=started_at + wall_timeout_s,
                    )
                else:
                    response = once_fn(
                        url=url,
                        payload=payload,
                        headers=headers,
                        timeout=timeout,
                    )
                return _attach_prompt_usage(response, system, user, history)
            except Exception as exc:
                last_exc = exc
                if attempt >= attempts or not _is_retryable_exception(exc):
                    if attempt > 1 and _is_retryable_exception(exc):
                        raise LlmRequestError(
                            f"LLM request failed after {attempt} attempts: "
                            f"provider={provider} model={cfg['model']} "
                            f"last_error={type(exc).__name__}: {str(exc)[-300:]}"
                        ) from exc
                    raise
                if on_heartbeat:
                    on_heartbeat()
                time.sleep(_retry_delay_s(attempt, retry_backoff_s))
        raise last_exc or LlmRequestError("LLM request failed before sending")
    finally:
        if use_alarm:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)


def _chat_once(
    url: str,
    payload: dict,
    headers: dict,
    timeout: httpx.Timeout,
) -> LlmResponse:
    resp = httpx.post(
        url,
        json=payload,
        headers=headers,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()

    choice = data["choices"][0]
    usage = data.get("usage", {})
    message = choice.get("message", {})

    return LlmResponse(
        text=message.get("content", ""),
        model=data.get("model", ""),
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
        prompt_cache_hit_tokens=usage.get("prompt_cache_hit_tokens"),
        prompt_cache_miss_tokens=usage.get("prompt_cache_miss_tokens"),
        total_tokens=usage.get("total_tokens"),
        raw_usage=dict(usage) if usage else None,
        reasoning_text=_as_text(message.get("reasoning_content") or message.get("reasoning") or message.get("thinking")),
    )


STREAM_NO_CONTENT_TIMEOUT_S = 240

def _chat_stream(
    url: str,
    payload: dict,
    headers: dict,
    timeout: httpx.Timeout,
    fallback_model: str,
    on_delta: Callable[[str], None] | None,
    on_reasoning_delta: Callable[[str], None] | None,
    on_heartbeat: Callable[[], None] | None,
    no_content_timeout_s: float = STREAM_NO_CONTENT_TIMEOUT_S,
    deadline: float | None = None,
) -> LlmResponse:
    chunks: list[str] = []
    reasoning_chunks: list[str] = []
    model = fallback_model
    usage = {}
    last_semantic_at = time.monotonic()

    with httpx.stream(
        "POST",
        url,
        json=payload,
        headers=headers,
        timeout=timeout,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            _raise_if_deadline_exceeded(deadline, model)
            if not line:
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if not line:
                continue
            if line == "[DONE]":
                break

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                if on_heartbeat:
                    on_heartbeat()
                continue

            model = event.get("model") or model
            if event.get("usage"):
                usage = event["usage"]

            choices = event.get("choices") or []
            if not choices:
                if on_heartbeat:
                    on_heartbeat()
                _raise_if_no_semantic_delta(last_semantic_at, no_content_timeout_s)
                continue

            delta = choices[0].get("delta") or {}
            reasoning = _as_text(delta.get("reasoning_content") or delta.get("reasoning") or delta.get("thinking"))
            content = delta.get("content") or ""
            if reasoning:
                reasoning_chunks.append(reasoning)
                last_semantic_at = time.monotonic()
                if on_reasoning_delta:
                    on_reasoning_delta(reasoning)
            if content:
                chunks.append(content)
                last_semantic_at = time.monotonic()
                if on_delta:
                    on_delta(content)
            elif not reasoning:
                if on_heartbeat:
                    on_heartbeat()
                _raise_if_no_semantic_delta(last_semantic_at, no_content_timeout_s)

    return LlmResponse(
        text="".join(chunks),
        model=model,
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
        prompt_cache_hit_tokens=usage.get("prompt_cache_hit_tokens"),
        prompt_cache_miss_tokens=usage.get("prompt_cache_miss_tokens"),
        total_tokens=usage.get("total_tokens"),
        raw_usage=dict(usage) if usage else None,
        reasoning_text="".join(reasoning_chunks),
    )


# ---------------------------------------------------------------------------
# Anthropic Messages API (/v1/messages) — used by providers with
# api_style="anthropic" (e.g. DeepSeek's https://api.deepseek.com/anthropic).
# Same request once/stream contract as the OpenAI path (url/payload/headers/
# timeout in, LlmResponse out) so the shared retry/wall-timeout wrapper above
# works unchanged; only the wire format differs.
# ---------------------------------------------------------------------------
def _anthropic_response(
    text: str,
    reasoning: str,
    model: str,
    usage: dict,
) -> LlmResponse:
    in_tokens = usage.get("input_tokens")
    out_tokens = usage.get("output_tokens")
    total = (in_tokens or 0) + (out_tokens or 0)
    return LlmResponse(
        text=text,
        model=model,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        # Anthropic usage names cache tokens differently than DeepSeek's OpenAI
        # endpoint; map what's present, keep the rest in raw_usage.
        prompt_cache_hit_tokens=usage.get("cache_read_input_tokens"),
        prompt_cache_miss_tokens=usage.get("cache_creation_input_tokens"),
        total_tokens=total or None,
        raw_usage=dict(usage) if usage else None,
        reasoning_text=reasoning,
    )


def _chat_once_anthropic(
    url: str,
    payload: dict,
    headers: dict,
    timeout: httpx.Timeout,
) -> LlmResponse:
    resp = httpx.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    content = data.get("content") or []
    text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
    reasoning = "".join(b.get("thinking", "") for b in content if b.get("type") == "thinking")
    return _anthropic_response(text, reasoning, data.get("model", ""), data.get("usage") or {})


def _chat_stream_anthropic(
    url: str,
    payload: dict,
    headers: dict,
    timeout: httpx.Timeout,
    fallback_model: str,
    on_delta: Callable[[str], None] | None,
    on_reasoning_delta: Callable[[str], None] | None,
    on_heartbeat: Callable[[], None] | None,
    no_content_timeout_s: float = STREAM_NO_CONTENT_TIMEOUT_S,
    deadline: float | None = None,
) -> LlmResponse:
    """Parse the Anthropic Messages SSE stream.

    Events (each `data:` line is JSON with a `type`): message_start (usage.input_tokens),
    content_block_start, content_block_delta (text_delta.text / thinking_delta.thinking),
    content_block_stop, message_delta (usage.output_tokens), message_stop, ping.
    The `event:` line mirrors the data `type`, so we switch on the JSON `type`.
    """
    chunks: list[str] = []
    reasoning_chunks: list[str] = []
    model = fallback_model
    usage: dict = {}
    last_semantic_at = time.monotonic()

    with httpx.stream(
        "POST",
        url,
        json=payload,
        headers=headers,
        timeout=timeout,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            _raise_if_deadline_exceeded(deadline, model)
            if not line:
                continue
            if line.startswith("event:"):
                continue  # redundant with the data payload's `type`
            if line.startswith("data:"):
                line = line[5:].strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                if on_heartbeat:
                    on_heartbeat()
                continue

            etype = event.get("type")
            if etype == "message_start":
                msg = event.get("message") or {}
                model = msg.get("model") or model
                u = msg.get("usage") or {}
                usage.update(u)
            elif etype == "content_block_delta":
                delta = event.get("delta") or {}
                dtype = delta.get("type")
                if dtype == "text_delta":
                    text = delta.get("text") or ""
                    if text:
                        chunks.append(text)
                        last_semantic_at = time.monotonic()
                        if on_delta:
                            on_delta(text)
                elif dtype == "thinking_delta":
                    think = delta.get("thinking") or ""
                    if think:
                        reasoning_chunks.append(think)
                        last_semantic_at = time.monotonic()
                        if on_reasoning_delta:
                            on_reasoning_delta(think)
                else:
                    if on_heartbeat:
                        on_heartbeat()
            elif etype == "message_delta":
                u = event.get("usage") or {}
                usage.update(u)
            elif etype in ("error",):
                err = event.get("error") or {}
                raise LlmRequestError(
                    f"anthropic stream error: {err.get('type')}: {str(err.get('message'))[:300]}"
                )
            elif etype == "message_stop":
                break
            else:
                # ping / content_block_start / content_block_stop / unknown
                if on_heartbeat:
                    on_heartbeat()
                _raise_if_no_semantic_delta(last_semantic_at, no_content_timeout_s)

    return _anthropic_response(
        "".join(chunks), "".join(reasoning_chunks), model, usage
    )


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("content", "text", "reasoning_content"):
            if key in value:
                return _as_text(value[key])
    return str(value)


def _should_request_stream_usage(cfg: dict) -> bool:
    """DeepSeek stream usage requires stream_options.include_usage."""
    base_url = str(cfg.get("base_url", "")).lower()
    if cfg.get("include_stream_usage") is False:
        return False
    return "deepseek" in base_url


def _attach_prompt_usage(
    response: LlmResponse, system: str, user: str, history: list[dict] | None = None,
) -> LlmResponse:
    system_chars = len(system or "")
    user_chars = len(user or "")
    history_chars = sum(len(str(msg.get("content", ""))) for msg in (history or []))
    prompt_chars = system_chars + user_chars + history_chars
    response.system_prompt_chars = system_chars
    response.user_prompt_chars = user_chars
    response.prompt_chars = prompt_chars
    response.estimated_input_tokens = (
        response.input_tokens if response.input_tokens is not None
        else _estimate_tokens_from_chars(prompt_chars)
    )
    output_chars = len(response.text or "") + len(response.reasoning_text or "")
    response.estimated_output_tokens = (
        response.output_tokens if response.output_tokens is not None
        else _estimate_tokens_from_chars(output_chars)
    )
    return response


def _estimate_tokens_from_chars(chars: int) -> int:
    return int(math.ceil(max(0, chars) / 2.0))


def _raise_if_deadline_exceeded(deadline: float | None, model: str) -> None:
    if deadline is not None and time.monotonic() > deadline:
        raise LlmTimeoutError(
            f"LLM stream exceeded wall deadline mid-stream: model={model}"
        )


def _raise_if_no_semantic_delta(last_semantic_at: float, no_content_timeout_s: float) -> None:
    if no_content_timeout_s <= 0:
        return
    elapsed = time.monotonic() - last_semantic_at
    if elapsed > no_content_timeout_s:
        raise LlmTimeoutError(
            f"LLM stream produced no thinking/content delta for {elapsed:.0f}s"
        )


def _is_retryable_exception(exc: Exception) -> bool:
    if isinstance(exc, LlmTimeoutError):
        return True
    retryable_types = (
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.ReadError,
        httpx.RemoteProtocolError,
        httpx.ProtocolError,
        httpx.NetworkError,
    )
    if isinstance(exc, retryable_types):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or 500 <= status <= 599
    return False


def _retry_delay_s(attempt: int, base_s: float) -> float:
    if base_s <= 0:
        return 0
    return min(30.0, base_s * (2 ** (attempt - 1)))


def chat_prefix(
    system: str,
    user: str,
    provider: str = "deepseek",
    temperature: float = 0.2,
    timeout: float = 300,
) -> LlmResponse:
    """对话前缀续写：强制模型续写 Python 代码，不输出解释。
    使用 /beta endpoint，assistant 消息 prefix=True。
    """
    import json, httpx, time
    from pathlib import Path
    cfg_check = load_config(provider)
    if not cfg_check.get("supports_prefix_completion", False):
        raise RuntimeError(f"Provider '{provider}' does not support prefix. Use chat().")

    config_path = Path(__file__).resolve().parents[3] / "ai_providers.local.json"
    cfg = json.loads(config_path.read_text())["providers"].get(provider)
    if not cfg:
        raise KeyError(f"Unknown provider: {provider}")

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
        {"role": "assistant", "content": "```python\n", "prefix": True},
    ]

    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": cfg.get("max_output_tokens", 16384),
        "stop": ["```"],
    }
    payload.update(cfg.get("extra_body", {}))

    url = f"{cfg['base_url'].rstrip('/')}/beta/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }

    t0 = time.time()
    resp = httpx.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    body = resp.json()

    content = body["choices"][0]["message"]["content"]
    # 去掉可能残留的 ``` 和 # === marker
    content = content.strip()
    if content.endswith("```"):
        content = content[:-3].strip()

    usage = body.get("usage", {})
    return LlmResponse(
        text=content,
        model=body.get("model", cfg["model"]),
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
        prompt_cache_hit_tokens=usage.get("prompt_cache_hit_tokens"),
        prompt_cache_miss_tokens=usage.get("prompt_cache_miss_tokens"),
        total_tokens=usage.get("total_tokens"),
        raw_usage=dict(usage) if usage else None,
    )


# ---- Tool Calls ----

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "best_assign",
            "description": "给定起点列表和目标点列表，计算最优一对一排列，使最近距离最大化。返回排列和最小距离。",
            "parameters": {
                "type": "object",
                "properties": {
                    "starts": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}, "description": "起点列表 [(x1,y1), (x2,y2), ...]"},
                    "targets": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}, "description": "目标点列表 [(x1,y1,z1), ...]"}
                },
                "required": ["starts", "targets"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "flight_time_ms",
            "description": "计算给定3D距离和速度、加速度下的飞行时间（毫秒）",
            "parameters": {
                "type": "object",
                "properties": {
                    "distance_cm": {"type": "number", "description": "3D距离（厘米）"},
                    "speed_cms": {"type": "number", "description": "速度（cm/s）"},
                    "acc_cms2": {"type": "number", "description": "加速度（cm/s²）"}
                },
                "required": ["distance_cm", "speed_cms", "acc_cms2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "distance_3d",
            "description": "计算两点间的3D欧氏距离",
            "parameters": {
                "type": "object",
                "properties": {
                    "p1": {"type": "array", "items": {"type": "number"}, "description": "点1 (x,y,z)"},
                    "p2": {"type": "array", "items": {"type": "number"}, "description": "点2 (x,y,z)"}
                },
                "required": ["p1", "p2"]
            }
        }
    }
]


def execute_tool(name: str, args: dict) -> str:
    """执行 agent tool call，返回 JSON 字符串"""
    import json, math
    from core.best_assign import best_assign

    if name == "best_assign":
        starts = [(p[0], p[1]) for p in args["starts"]]
        targets = [(p[0], p[1]) for p in args["targets"]]
        perm, min_d = best_assign(starts, targets)
        return json.dumps({"perm": list(perm), "min_d_cm": round(min_d, 1)})

    if name == "flight_time_ms":
        d, v, a = args["distance_cm"], args["speed_cms"], args["acc_cms2"]
        if d <= 0: ms = 0
        else:
            accel_dist = v*v/(2*a)
            t = 2*v/a + (d-2*accel_dist)/v if d >= 2*accel_dist else 2*math.sqrt(d/a)
            ms = int(math.ceil(t*1000))
        return json.dumps({"flight_ms": ms})

    if name == "distance_3d":
        p1, p2 = args["p1"], args["p2"]
        d = math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2 + (p2[2]-p1[2])**2)
        return json.dumps({"distance_cm": round(d, 1)})

    return json.dumps({"error": f"unknown tool: {name}"})


def chat_with_tools(
    system: str,
    user: str,
    provider: str = "deepseek",
    temperature: float = 0.2,
    timeout: float = 300,
    max_tool_rounds: int = 5,
):
    """Tool Calls mode + stop marker. Agent can call tools, final output is code."""
    import json as _json, httpx, time, re as _re
    from pathlib import Path

    config_path = Path(__file__).resolve().parents[3] / "ai_providers.local.json"
    cfg = _json.loads(config_path.read_text())["providers"].get(provider)
    if not cfg:
        raise KeyError(f"Unknown provider: {provider}")

    messages = [
        {"role": "system", "content": system + "\n\nOutput ONLY Python code inside a ```python block. No explanations. Use tools for calculations."},
        {"role": "user", "content": user},
    ]

    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    url = f"{cfg['base_url'].rstrip('/')}/beta/chat/completions"

    for _round in range(max_tool_rounds):
        payload = {
            "model": cfg["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": cfg.get("max_output_tokens", 16384),
            "stop": ["```"],
            "tools": AGENT_TOOLS,
        }
        payload.update(cfg.get("extra_body", {}))

        resp = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        body = resp.json()
        choice = body["choices"][0]
        msg = choice["message"]

        if msg.get("tool_calls"):
            messages.append(msg)
            for tc in msg["tool_calls"]:
                fn = tc["function"]
                result = execute_tool(fn["name"], _json.loads(fn["arguments"]))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
            continue

        content = msg.get("content", "")
        m = _re.search(r"```(?:python)?\s*(.*?)\s*```", content, _re.DOTALL)
        if m:
            content = m.group(1).strip()
        else:
            content = content.strip()

        usage = body.get("usage", {})
        return LlmResponse(
            text=content,
            model=body.get("model", cfg["model"]),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            prompt_cache_hit_tokens=usage.get("prompt_cache_hit_tokens"),
            prompt_cache_miss_tokens=usage.get("prompt_cache_miss_tokens"),
            total_tokens=usage.get("total_tokens"),
            raw_usage=dict(usage) if usage else None,
        )

    return LlmResponse(text="", model=cfg["model"])
