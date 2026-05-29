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



def _build_user_content(text: str, image_paths: list[str] | None = None):
    """构建用户消息内容，支持图片"""
    if not image_paths:
        return text
    import base64
    content = [{"type": "text", "text": text}]
    for path in image_paths:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ext = path.rsplit(".", 1)[-1].lower()
        mime = f"image/{ext}" if ext in ("png","jpg","jpeg","gif","webp") else "image/png"
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"}
        })
    return content


def chat(
    system: str,
    user: str,
    provider: str = "deepseek",
    temperature: float = 0.2,
    image_paths: list[str] | None = None,
    on_delta: Callable[[str], None] | None = None,
    on_heartbeat: Callable[[], None] | None = None,
) -> LlmResponse:
    """发送 chat completion 请求"""
    cfg = load_config(provider)

    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _build_user_content(user, image_paths)},
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
        connect=float(cfg.get("connect_timeout_s", 60)),
        read=read_timeout_s,
        write=float(cfg.get("write_timeout_s", 30)),
        pool=float(cfg.get("pool_timeout_s", 30)),
    )

    def on_timeout(_signum, _frame):
        raise LlmTimeoutError(
            f"LLM request timed out after {wall_timeout_s:.0f}s: "
            f"provider={provider} model={cfg['model']}"
        )

    import time as _time
    _max_retries = 6
    _last_error = None
    url = f"{cfg['base_url'].rstrip('/')}/chat/completions"
    for _attempt in range(_max_retries):
        try:
            previous_handler = signal.getsignal(signal.SIGALRM)
            signal.signal(signal.SIGALRM, on_timeout)
            signal.setitimer(signal.ITIMER_REAL, wall_timeout_s)
            try:
                if use_stream:
                    return _chat_stream(url=url, payload=payload, headers=headers, timeout=timeout,
                                        fallback_model=cfg["model"], on_delta=on_delta, on_heartbeat=on_heartbeat)
                return _chat_once(url=url, payload=payload, headers=headers, timeout=timeout)
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, previous_handler)
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            _last_error = e
            if _attempt < _max_retries - 1:
                _time.sleep(2 ** _attempt)  # 1s, 2s, 4s backoff
    raise _last_error


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
        )

    return LlmResponse(text="", model=cfg["model"])
