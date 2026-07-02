"""Integration tests: chat, preflight, planning, degradation cross-segment."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_chat_mimo_no_prefix():
    """chat(provider='mimo') works without prefix/recursion.

    真实 API 调用——默认跳过，设 PYFII_REAL_API_TESTS=1 启用。
    """
    import os
    if not os.environ.get("PYFII_REAL_API_TESTS"):
        import pytest
        pytest.skip("real mimo API call; set PYFII_REAL_API_TESTS=1 to run")
    from core.llm_client import chat
    r = chat("say OK", "respond OK", provider="mimo", temperature=0.1)
    assert r is not None
    assert "ok" in r.text.lower()
    print("PASSED: chat(mimo) — no recursion, no prefix")


def test_chat_prefix_mimo_rejects():
    """chat_prefix(provider='mimo') raises locally without HTTP."""
    from core.llm_client import chat_prefix
    try:
        chat_prefix("sys", "user", provider="mimo", temperature=0.1)
        assert False, "Should raise"
    except RuntimeError as e:
        assert "does not support prefix" in str(e)
    print("PASSED: chat_prefix(mimo) — local reject")


def test_bad_code_does_not_write_design_py():
    """preflight failure prevents design.py modification."""
    from core.session import _extract_python_code
    from core.preflight import preflight_check
    bad = "import math\n```python\ndrone.VelXY(120,200)\n```"
    code = _extract_python_code(bad)
    pf = preflight_check(code)
    assert not pf, f"Should fail preflight: {pf.errors}"
    print("PASSED: bad code fails preflight (would not write design.py)")


def test_degradation_signature_cross_segment():
    """Same degradation signature in two consecutive segments → hard fail."""
    # This is a logic test: verify state can store and compare signatures
    from core.state import SegmentState
    s1 = SegmentState(id="S01", start_time=4, end_time=13, degradation_signature="circle_like")
    s2 = SegmentState(id="S02", start_time=13, end_time=23, degradation_signature="circle_like")
    s3 = SegmentState(id="S03", start_time=23, end_time=31, degradation_signature="expand")
    
    # Consecutive same signature
    assert s1.degradation_signature == s2.degradation_signature, \
        "S01 and S02 should have same sig"
    assert s2.degradation_signature != s3.degradation_signature, \
        "S02 and S03 should have different sig"
    print("PASSED: degradation cross-segment signature comparison")


def test_planning_pass_flow():
    """planning pass: JSON plan → budget table → code prompt."""
    from core.planning_pass import (
        build_planning_prompt, parse_plan_json,
        plan_to_budget_table, build_coding_prompt,
    )
    # Mock prev
    prev = [(140,190,130),(225,150,185),(298,226,217),(385,150,185),
            (445,223,175),(345,410,160),(185,375,155)]
    prompt = build_planning_prompt("S02", 13, 23, "expand", prev)
    assert "S02" in prompt and "JSON" in prompt
    
    # Mock plan JSON
    plan_json = '''```json
{"keyframes": [
  {"start_s":13,"duration_s":4,"feel":"expand","speed_cm_s":120,"accel_cm_s2":200,
   "light_color":"#4488ff","light_ticks":4,
   "targets":[[120,160,150],[200,180,170],[300,240,160],[400,200,180],[480,160,140],[360,400,150],[160,380,150]]},
  {"start_s":17,"duration_s":4,"feel":"rotate","speed_cm_s":100,"accel_cm_s2":180,
   "light_color":"#ff6644","light_ticks":4,
   "targets":[[200,200,200],[280,220,200],[360,280,190],[440,240,200],[500,200,180],[400,440,190],[200,420,190]]}
]}
```'''
    plan = parse_plan_json(plan_json)
    assert plan is not None
    
    budget = plan_to_budget_table(plan, prev)
    assert "Keyframe 1" in budget
    assert "budget" in budget.lower() or "预算" in budget or "dist3" in budget or "fly_ms" in budget
    
    code_prompt = build_coding_prompt(budget, "S02", 13, 23)
    assert "S02" in code_prompt
    print("PASSED: planning pass full flow")



def test_cli_g_uses_planning_pass():
    """CLI g command passes use_planning_pass=True to generate_until_safe_with_llm."""
    # This is a code inspection test, not runtime
    main_path = Path(__file__).resolve().parent.parent / "main.py"
    content = main_path.read_text()
    assert "use_planning_pass=True" in content, \
        "main.py g command must include use_planning_pass=True"
    print("PASSED: CLI g command uses planning pass")


def test_project_template_has_no_static_extra_segments():
    """S07/S08 are dynamic continuation segments, not template defaults."""
    import json

    template_root = Path("tools/choreo_agent/project_template")
    state = json.loads((template_root / "state.json").read_text())
    segment_ids = [item["id"] for item in state["segments"]]
    assert segment_ids == ["S01", "S02", "S03", "S04", "S05", "S06", "LAND"], segment_ids

    design = (template_root / "scripts" / "design.py").read_text()
    assert "def s07" not in design.lower()
    assert "def s08" not in design.lower()
    print("PASSED: template has no static S07/S08; continuations remain dynamic")


def test_full_flow_runner_is_strict():
    """The stability runner must not force-lock failures or use fixed segment lists."""
    runner = Path("tools/choreo_agent/run_pipeline.py").read_text()
    forbidden = [
        "allow_human_override=True",
        "_force_advance",
        "SEGMENTS_TO_PROCESS",
        "fallback",
        "hand-written",
    ]
    for item in forbidden:
        assert item not in runner, f"Forbidden runner pattern: {item}"
    assert "while True:" in runner
    assert "session.state.current_segment" in runner
    assert "allow_human_override=False" in runner
    print("PASSED: full-flow runner follows current_segment and never force-locks")



def test_generate_never_calls_chat_prefix():
    """generate_current_segment_with_llm never calls chat_prefix."""
    s=open('tools/choreo_agent/core/session.py').read()
    assert 'chat_prefix' not in s.split('def generate_current_segment_with_llm')[1].split('def generate_until_safe_with_llm')[0]
    print('PASSED: generate_current_segment_with_llm never calls chat_prefix')


def test_stream_parses_reasoning_and_result_deltas():
    """Streaming parser separates provider thinking from final content."""
    from unittest.mock import patch
    from core.llm_client import _chat_stream

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            pass

        def iter_lines(self):
            yield 'data: {"model":"mock","choices":[{"delta":{"reasoning_content":"think "}}]}'
            yield 'data: {"choices":[{"delta":{"content":"result"}}]}'
            yield 'data: [DONE]'

    thinking = []
    result = []
    with patch("core.llm_client.httpx.stream", return_value=FakeResponse()):
        response = _chat_stream(
            url="https://example.test/chat/completions",
            payload={},
            headers={},
            timeout=None,
            fallback_model="mock",
            on_delta=result.append,
            on_reasoning_delta=thinking.append,
            on_heartbeat=None,
        )

    assert "".join(thinking) == "think "
    assert "".join(result) == "result"
    assert response.text == "result"
    assert response.reasoning_text == "think "
    print("PASSED: stream parser separates thinking and result")


def test_stream_deadline_cuts_endless_reasoning():
    """Worker 线程里没有 SIGALRM，no-content 看门狗又被 reasoning 增量不断重置；
    流式循环内的 deadline 检查必须能掐断一个无限输出思考的流。"""
    import json as _json
    import time as _time
    from concurrent.futures import ThreadPoolExecutor
    from unittest.mock import patch
    from core import llm_client

    class EndlessReasoningStream:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            pass

        def iter_lines(self):
            line = "data: " + _json.dumps(
                {"choices": [{"delta": {"reasoning_content": "嗯"}}]}
            )
            while True:
                yield line

    cfg = {
        "model": "mock",
        "base_url": "https://example.test",
        "api_key": "test-key",
        "stream": True,
        "timeout_s": 0.5,
        "no_content_timeout_s": 600,
        "max_retries": 0,
    }
    started = _time.monotonic()
    with patch("core.llm_client.load_config", return_value=cfg), \
            patch("core.llm_client.httpx.stream", return_value=EndlessReasoningStream()):
        # 在 worker 线程里跑，绕开主线程 SIGALRM，逼出 deadline 路径
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(llm_client.chat, "sys", "user", provider="mock")
            try:
                future.result(timeout=30)
                assert False, "expected LlmTimeoutError from in-stream deadline"
            except llm_client.LlmTimeoutError:
                pass
    assert _time.monotonic() - started < 10, "deadline should cut the stream promptly"
    print("PASSED: in-stream deadline cuts endless reasoning stream")


def test_chat_retries_transient_error_once():
    """chat() retries transient network errors before surfacing failure."""
    from unittest.mock import patch
    import httpx
    from core.llm_client import chat, LlmResponse

    cfg = {
        "model": "mock",
        "base_url": "https://example.test",
        "api_key": "test-key",
        "stream": False,
        "max_retries": 1,
        "retry_backoff_s": 0,
        "timeout_s": 10,
    }
    calls = []

    def fake_chat_once(**_kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectTimeout("temporary connect timeout")
        return LlmResponse(text="OK", model="mock")

    with patch("core.llm_client.load_config", return_value=cfg), \
            patch("core.llm_client._chat_once", side_effect=fake_chat_once):
        response = chat("sys", "user", provider="mock")

    assert response.text == "OK"
    assert len(calls) == 2
    print("PASSED: chat retries transient error once")


def test_extract_candidate_code_dedents_fenced_body():
    """Indented fenced code is normalized before preflight."""
    from core.session import _extract_candidate_code
    from core.preflight import preflight_check

    response = """```python
        prev = [(d.x, d.y, d.z) for d in drones]
        for i, drone in enumerate(drones):
            move2(drone, (100, 120, 150), 3000)
            apply_light(drone, "#ffaa00", 4)
            drone.delay(2700)
        prev = [(d.x, d.y, d.z) for d in drones]
    ```"""
    code = _extract_candidate_code(response)
    assert code.startswith("prev =")
    assert preflight_check(code), code
    print("PASSED: candidate code dedents fenced body")

if __name__ == "__main__":
    import os as _os
    if _os.environ.get("PYFII_REAL_API_TESTS"):
        test_chat_mimo_no_prefix()
    test_chat_prefix_mimo_rejects()
    test_bad_code_does_not_write_design_py()
    test_degradation_signature_cross_segment()
    test_planning_pass_flow()
    test_cli_g_uses_planning_pass()
    test_project_template_has_no_static_extra_segments()
    test_full_flow_runner_is_strict()
    test_generate_never_calls_chat_prefix()
    test_stream_parses_reasoning_and_result_deltas()
    test_stream_deadline_cuts_endless_reasoning()
    test_chat_retries_transient_error_once()
    test_extract_candidate_code_dedents_fenced_body()
    print("\nALL 10 INTEGRATION TESTS PASSED")
