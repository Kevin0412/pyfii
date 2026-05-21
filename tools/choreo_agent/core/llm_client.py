"""LLM Client — 统一调用接口"""
import json
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


def load_config(provider_name: str = "deepseek") -> dict:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return cfg["providers"][provider_name]


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
        "max_tokens": 16384,
    }

    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }

    resp = httpx.post(
        f"{cfg['base_url']}/chat/completions",
        json=payload,
        headers=headers,
        timeout=300,
    )
    data = resp.json()

    choice = data["choices"][0]
    usage = data.get("usage", {})

    return LlmResponse(
        text=choice["message"]["content"],
        model=data.get("model", ""),
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
    )
