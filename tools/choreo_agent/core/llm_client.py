"""LLM Client — 统一调用接口"""
import json
import signal
import httpx
from pathlib import Path
from dataclasses import dataclass
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "ai_providers.local.json"
DEFAULT_WALL_TIMEOUT_S = 900
DEFAULT_READ_TIMEOUT_S = 300


@dataclass
class LlmResponse:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LlmTimeoutError(TimeoutError):
    pass


def load_config(provider_name: str = "deepseek") -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"missing provider config: {CONFIG_PATH}")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    providers = cfg.get("providers", {})
    if provider_name not in providers:
        raise KeyError(f"unknown provider: {provider_name}")
    return providers[provider_name]


def chat(
    system: str,
    user: str,
    provider: str = "deepseek",
    temperature: float = 0.2,
    on_delta: Callable[[str], None] | None = None,
    on_heartbeat: Callable[[], None] | None = None,
) -> LlmResponse:
    """发送 chat completion 请求"""
    cfg = load_config(provider)

    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": cfg.get("max_output_tokens", 16384),
    }
    payload.update(cfg.get("extra_body", {}))
    use_stream = bool(cfg.get("stream", True))
    if use_stream:
        payload["stream"] = True
        if "stream_options" in cfg:
            payload["stream_options"] = cfg["stream_options"]

    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }

    wall_timeout_s = float(cfg.get("timeout_s", DEFAULT_WALL_TIMEOUT_S))
    read_timeout_s = float(cfg.get("read_timeout_s", min(DEFAULT_READ_TIMEOUT_S, wall_timeout_s)))
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

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, on_timeout)
    signal.setitimer(signal.ITIMER_REAL, wall_timeout_s)
    try:
        url = f"{cfg['base_url'].rstrip('/')}/chat/completions"
        if use_stream:
            return _chat_stream(
                url=url,
                payload=payload,
                headers=headers,
                timeout=timeout,
                fallback_model=cfg["model"],
                on_delta=on_delta,
                on_heartbeat=on_heartbeat,
            )
        return _chat_once(
            url=url,
            payload=payload,
            headers=headers,
            timeout=timeout,
        )
    finally:
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

    return LlmResponse(
        text=choice["message"]["content"],
        model=data.get("model", ""),
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
    )


def _chat_stream(
    url: str,
    payload: dict,
    headers: dict,
    timeout: httpx.Timeout,
    fallback_model: str,
    on_delta: Callable[[str], None] | None,
    on_heartbeat: Callable[[], None] | None,
) -> LlmResponse:
    chunks: list[str] = []
    model = fallback_model
    usage = {}

    with httpx.stream(
        "POST",
        url,
        json=payload,
        headers=headers,
        timeout=timeout,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
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
                continue

            delta = choices[0].get("delta") or {}
            content = delta.get("content") or ""
            if content:
                chunks.append(content)
                if on_delta:
                    on_delta(content)
            elif on_heartbeat:
                on_heartbeat()

    return LlmResponse(
        text="".join(chunks),
        model=model,
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
    )


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
    )
