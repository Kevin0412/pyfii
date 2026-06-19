"""Anthropic-compatible LLM-client path tests (offline, httpx mocked).

Verifies the api_style="anthropic" wire format (POST /v1/messages, x-api-key +
anthropic-version, top-level system, user-only messages, max_tokens), the SSE
and non-streaming response parsing, and that the OpenAI path is unchanged.
"""

import core.llm_client as lc


# ---------- fakes ----------

class _FakeOnceResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _FakeStreamResp:
    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self):
        pass

    def iter_lines(self):
        yield from self._lines


class _FakeStreamCtx:
    def __init__(self, lines):
        self._r = _FakeStreamResp(lines)

    def __enter__(self):
        return self._r

    def __exit__(self, *a):
        return False


def _with_config(monkey_cfg):
    real = lc.load_config
    lc.load_config = lambda name="x": dict(monkey_cfg)
    return real


_ANTHROPIC_CFG = {
    "api_style": "anthropic",
    "base_url": "https://api.deepseek.com/anthropic",
    "api_key": "sk-test-key",
    "model": "deepseek-v4-flash",
    "stream": False,
    "max_output_tokens": 4096,
}
_OPENAI_CFG = {
    "base_url": "https://api.deepseek.com",
    "api_key": "sk-test-key",
    "model": "deepseek-v4-flash",
    "stream": False,
    "max_output_tokens": 4096,
}


# ---------- request shape ----------

def test_anthropic_request_shape():
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, payload=json, headers=headers)
        return _FakeOnceResp({"model": "m", "content": [{"type": "text", "text": "x"}],
                              "usage": {"input_tokens": 1, "output_tokens": 1}})

    real_cfg = _with_config(_ANTHROPIC_CFG)
    real_post = lc.httpx.post
    lc.httpx.post = fake_post
    try:
        lc.chat("SYS", "USER", provider="deepseek_anthropic", temperature=0.3)
    finally:
        lc.load_config = real_cfg
        lc.httpx.post = real_post

    assert captured["url"].endswith("/v1/messages"), captured["url"]
    h = captured["headers"]
    assert h.get("x-api-key") == "sk-test-key"
    assert h.get("anthropic-version")  # present
    assert "Authorization" not in h, "anthropic path must not send Bearer auth"
    p = captured["payload"]
    assert p["system"] == "SYS", "system must be a top-level field"
    assert p["messages"] == [{"role": "user", "content": "USER"}], "no system role in messages"
    assert p["max_tokens"] == 4096, "max_tokens required"
    assert p["temperature"] == 0.3


def test_anthropic_omit_temperature_drops_field():
    # Newer Claude models (Opus 4.x) deprecate `temperature` and 400 if it is sent.
    # omit_temperature:true must drop the field; the default keeps it (tested above).
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(payload=json)
        return _FakeOnceResp({"model": "m", "content": [{"type": "text", "text": "x"}],
                              "usage": {"input_tokens": 1, "output_tokens": 1}})

    real_cfg = _with_config(dict(_ANTHROPIC_CFG, omit_temperature=True))
    real_post = lc.httpx.post
    lc.httpx.post = fake_post
    try:
        lc.chat("SYS", "USER", provider="custom_claude", temperature=0.3)
    finally:
        lc.load_config = real_cfg
        lc.httpx.post = real_post

    assert "temperature" not in captured["payload"], "omit_temperature must drop the field"
    assert captured["payload"]["system"] == "SYS"  # rest of the shape intact


def test_openai_request_shape_unchanged():
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, payload=json, headers=headers)
        return _FakeOnceResp({"model": "m", "choices": [{"message": {"content": "x"}}],
                              "usage": {"prompt_tokens": 1, "completion_tokens": 1}})

    real_cfg = _with_config(_OPENAI_CFG)
    real_post = lc.httpx.post
    lc.httpx.post = fake_post
    try:
        lc.chat("SYS", "USER", provider="deepseek", temperature=0.3)
    finally:
        lc.load_config = real_cfg
        lc.httpx.post = real_post

    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"].get("Authorization") == "Bearer sk-test-key"
    assert captured["payload"]["messages"][0] == {"role": "system", "content": "SYS"}


# ---------- response parsing ----------

def test_anthropic_once_parsing():
    real_cfg = _with_config(_ANTHROPIC_CFG)
    real_post = lc.httpx.post
    lc.httpx.post = lambda *a, **k: _FakeOnceResp({
        "model": "deepseek-v4-flash",
        "content": [
            {"type": "thinking", "thinking": "reason-"},
            {"type": "text", "text": "Hello "},
            {"type": "text", "text": "world"},
        ],
        "usage": {"input_tokens": 7, "output_tokens": 3,
                  "cache_read_input_tokens": 4},
        "stop_reason": "end_turn",
    })
    try:
        r = lc.chat("s", "u", provider="deepseek_anthropic")
    finally:
        lc.load_config = real_cfg
        lc.httpx.post = real_post

    assert r.text == "Hello world"
    assert r.reasoning_text == "reason-"
    assert r.input_tokens == 7 and r.output_tokens == 3 and r.total_tokens == 10
    assert r.prompt_cache_hit_tokens == 4
    assert r.model == "deepseek-v4-flash"


_SSE_LINES = [
    "event: message_start",
    'data: {"type":"message_start","message":{"id":"m1","model":"deepseek-v4-flash","usage":{"input_tokens":10,"output_tokens":0}}}',
    "",
    "event: content_block_start",
    'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}',
    "",
    "event: ping",
    'data: {"type":"ping"}',
    "",
    "event: content_block_delta",
    'data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"hmm"}}',
    "",
    "event: content_block_delta",
    'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}',
    "",
    "event: content_block_delta",
    'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" world"}}',
    "",
    "event: content_block_stop",
    'data: {"type":"content_block_stop","index":0}',
    "",
    "event: message_delta",
    'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":5}}',
    "",
    "event: message_stop",
    'data: {"type":"message_stop"}',
]


def test_anthropic_stream_parsing():
    deltas, reasonings = [], []
    real_cfg = _with_config(dict(_ANTHROPIC_CFG, stream=True))
    real_stream = lc.httpx.stream
    lc.httpx.stream = lambda *a, **k: _FakeStreamCtx(_SSE_LINES)
    try:
        r = lc.chat("s", "u", provider="deepseek_anthropic",
                    on_delta=deltas.append, on_reasoning_delta=reasonings.append)
    finally:
        lc.load_config = real_cfg
        lc.httpx.stream = real_stream

    assert r.text == "Hello world"
    assert r.reasoning_text == "hmm"
    assert r.input_tokens == 10 and r.output_tokens == 5
    assert r.model == "deepseek-v4-flash"
    assert deltas == ["Hello", " world"]
    assert reasonings == ["hmm"]


def test_anthropic_stream_error_event_raises():
    real_cfg = _with_config(dict(_ANTHROPIC_CFG, stream=True, max_retries=0))
    real_stream = lc.httpx.stream
    lc.httpx.stream = lambda *a, **k: _FakeStreamCtx([
        'data: {"type":"error","error":{"type":"overloaded_error","message":"busy"}}',
    ])
    try:
        raised = False
        try:
            lc.chat("s", "u", provider="deepseek_anthropic")
        except Exception as exc:
            raised = True
            assert "overloaded_error" in str(exc)
        assert raised, "error event must surface as an exception"
    finally:
        lc.load_config = real_cfg
        lc.httpx.stream = real_stream


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASSED: {name}")
    print("\nALL ANTHROPIC CLIENT TESTS PASSED")
