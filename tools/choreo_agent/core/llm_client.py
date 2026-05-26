"""LLM Client — 统一调用接口"""
import json
import signal
import httpx
from pathlib import Path
from dataclasses import dataclass

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "ai_providers.local.json"


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

    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }

    wall_timeout_s = float(cfg.get("timeout_s", 180))
    read_timeout_s = float(cfg.get("read_timeout_s", min(60, wall_timeout_s)))
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
        resp = httpx.post(
            f"{cfg['base_url'].rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
            timeout=timeout,
        )
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
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
