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
            _, out = session.generate_candidates_parallel(k=3, base_temperature=0.3)
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
            _, out = session.generate_candidates_parallel(k=3, base_temperature=0.3)
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


def test_only_winner_candidate_becomes_a_conversation_turn():
    """Phase 4: K 个并行分支问的是同一个问题，但只有胜出者的这次真实交换该进入
    seg.conversation——分支不是真实发生过的多轮对话，输家不能也留一条 turn。"""
    from unittest.mock import patch
    from core.preflight import PreflightResult

    def run(session):
        WINNER_MARKER = "WINNER_MARKER_a1b2"
        LOSER_MARKER = "LOSER_MARKER_c3d4"

        def fake_chat(system, user, temperature, **kw):
            # 低温度候选先返回，赢得 preflight 竞争
            if temperature <= 0.31:
                time.sleep(0.02)
                return _FakeResponse(f"prev = [(d.x, d.y, d.z) for d in drones]  # {WINNER_MARKER}")
            time.sleep(0.08)
            return _FakeResponse(f"prev = [(d.x, d.y, d.z) for d in drones]  # {LOSER_MARKER}")

        orig = session_mod.chat
        session_mod.chat = fake_chat
        try:
            with patch("core.session.preflight_check", return_value=PreflightResult()), \
                 patch.object(Session, "validate", side_effect=RuntimeError("stop after round 1")):
                try:
                    session.generate_until_safe_with_llm(
                        provider="mock", feedback="", max_attempts=1,
                        use_planning_pass=False, parallel_candidates=2,
                    )
                except RuntimeError:
                    pass  # 只需要跑到 validate() 之前，用异常短路避免继续跑真实校验
        finally:
            session_mod.chat = orig

        seg = session.state.current_segment
        turns = seg.conversation
        assert any(
            WINNER_MARKER in str(t.get("content", "")) and t.get("role") == "assistant"
            for t in turns
        ), "the winning candidate must become a real assistant turn"
        assert not any(LOSER_MARKER in str(t.get("content", "")) for t in turns), (
            "the losing candidate must never appear in conversation history — "
            "it went into the candidate pool instead, not a fabricated turn"
        )
        # 赢家只记一次（一个 user + 一个 assistant），不是每个分支各记一次
        assert sum(1 for t in turns if t.get("role") == "user") == 1

    _with_temp_session(run)


def test_pool_hit_round_gets_factual_code_recap_even_with_history_enabled():
    """候选池弹出的代码从没有过真实 assistant turn（零 API 调用）——即便
    conversation_history_enabled=True，这一轮如果后续验证失败，repair feedback 也必须
    把代码贴回去，不能假设"历史里已经有了"。"""
    from unittest.mock import patch
    from core.validator import ValidationResult

    def run(session):
        POOL_MARKER = "POOL_CODE_MARKER_9z8y"
        seg = session.state.current_segment
        session._pool_for_segment(seg.id).append(
            f"prev = [(d.x, d.y, d.z) for d in drones]  # {POOL_MARKER}"
        )

        failing = ValidationResult(
            compile_ok=True, run_ok=True, read_fii_ok=True,
            distance_warnings=0, action_warnings=0,
            dense_min_distance_cm=42.0, expected_drone_count=7,
        )
        failing.exit_state = [[100 + 60 * i, 100, 150] for i in range(7)]

        captured_feedback: list[str] = []
        orig = session_mod.chat

        def fake_chat(system, user, **kw):
            captured_feedback.append(user)
            return _FakeResponse("prev = [(d.x, d.y, d.z) for d in drones]  # round2")

        session_mod.chat = fake_chat
        try:
            with patch.object(Session, "validate", return_value=failing):
                session.generate_until_safe_with_llm(
                    provider="mock", feedback="", max_attempts=2,
                    use_planning_pass=False, parallel_candidates=2,
                )
        finally:
            session_mod.chat = orig

        assert captured_feedback, "round 2 should have been reached"
        assert POOL_MARKER in captured_feedback[0], (
            "the pool-hit segment's code never became a conversation turn, so it must "
            "still be recapped in the repair feedback text for the next round"
        )

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


def test_candidate_pool_clears_after_validator_feedback():
    def run(session):
        seg_id = session.state.current_segment.id
        session._pool_for_segment(seg_id).extend(["# stale A", "# stale B"])
        session._clear_candidate_pool(seg_id)
        assert session._pool_for_segment(seg_id) == []
        # Clearing a different segment must not disturb the current scoped pool.
        session._pool_for_segment(seg_id).append("# fresh")
        session._clear_candidate_pool("S99")
        assert session._pool_for_segment(seg_id) == ["# fresh"]

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
