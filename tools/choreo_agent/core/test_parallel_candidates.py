"""Parallel candidate generation + candidate pool tests (chat mocked, offline)."""

import shutil
import tempfile
import threading
import time
from pathlib import Path

import core.session as session_mod
from core.session import Session

TEMPLATE = Path(__file__).resolve().parents[1] / "project_template"


class _FakeResponse:
    def __init__(self, text, model="fake"):
        self.text = text
        self.model = model
        self.input_tokens = 10
        self.output_tokens = 10
        self.prompt_cache_hit_tokens = 0
        self.prompt_cache_miss_tokens = 10
        self.total_tokens = 20
        self.estimated_input_tokens = 10
        self.estimated_output_tokens = 10
        self.reasoning_text = ""
        self.raw_usage = {}


def _with_temp_session(fn):
    tmp = Path(tempfile.mkdtemp(prefix="par_test_"))
    project = tmp / "proj"
    shutil.copytree(TEMPLATE, project)
    try:
        fn(Session(project))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_parallel_returns_all_successes_and_records():
    def run(session):
        calls = []
        lock = threading.Lock()

        def fake_chat(system, user, provider, temperature, **kw):
            with lock:
                calls.append(temperature)
            time.sleep(0.05)
            return _FakeResponse(f"# code at temp {temperature}")

        orig = session_mod.chat
        session_mod.chat = fake_chat
        try:
            out = session.generate_candidates_parallel(k=3, base_temperature=0.3)
        finally:
            session_mod.chat = orig
        assert len(out) == 3
        assert len(set(calls)) == 3  # 温度梯度：三个不同温度
        seg = session.state.current_segment
        par_stages = [a.get("stage") for a in seg.attempts if str(a.get("stage", "")).startswith("generation_par")]
        assert len(par_stages) == 3  # 记录串行落盘

    _with_temp_session(run)


def test_parallel_survives_partial_stream_failure():
    def run(session):
        def fake_chat(system, user, provider, temperature, **kw):
            if temperature > 0.4:
                raise RuntimeError("RemoteProtocolError: peer closed")
            return _FakeResponse("# survivor")

        orig = session_mod.chat
        session_mod.chat = fake_chat
        try:
            out = session.generate_candidates_parallel(k=3, base_temperature=0.3)
        finally:
            session_mod.chat = orig
        assert len(out) == 1  # 一条流活着就不毁整轮

    _with_temp_session(run)


def test_parallel_raises_only_when_all_fail():
    def run(session):
        def fake_chat(*a, **kw):
            raise RuntimeError("all dead")

        orig = session_mod.chat
        session_mod.chat = fake_chat
        try:
            try:
                session.generate_candidates_parallel(k=2)
                raised = False
            except RuntimeError:
                raised = True
        finally:
            session_mod.chat = orig
        assert raised

    _with_temp_session(run)


def test_candidate_pool_scoped_per_segment():
    def run(session):
        seg_id = session.state.current_segment.id
        pool = session._pool_for_segment(seg_id)
        pool.append("# candidate A")
        assert session._pool_for_segment(seg_id) == ["# candidate A"]
        # 换段即清空
        assert session._pool_for_segment("S99") == []
        assert session._pool_for_segment("S99") is session._candidate_pool

    _with_temp_session(run)


def test_chat_works_in_worker_thread_without_sigalrm():
    """SIGALRM 只允许主线程；worker 线程里的 chat() 必须改走软墙，不得 ValueError。"""
    import core.llm_client as lc

    def fake_stream(**_kw):
        return lc.LlmResponse(text="ok", model="fake")

    real_stream, real_once = lc._chat_stream, lc._chat_once
    lc._chat_stream = fake_stream
    lc._chat_once = lambda **_kw: lc.LlmResponse(text="ok", model="fake")
    try:
        outcome = {}

        def run():
            try:
                outcome["resp"] = lc.chat("sys", "user", provider="deepseek")
            except Exception as exc:  # noqa: BLE001 — 断言用
                outcome["exc"] = exc

        worker = threading.Thread(target=run)
        worker.start()
        worker.join(timeout=10)
        assert "exc" not in outcome, f"worker 线程 chat() 抛错: {outcome.get('exc')!r}"
        assert outcome["resp"].text == "ok"

        # 主线程路径不回归
        main_resp = lc.chat("sys", "user", provider="deepseek")
        assert main_resp.text == "ok"
    finally:
        lc._chat_stream, lc._chat_once = real_stream, real_once


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASSED: {name}")
    print("\nALL PARALLEL CANDIDATE TESTS PASSED")
