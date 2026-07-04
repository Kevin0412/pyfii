"""修复反馈必须带上一轮实际代码。

Phase 2a/2b 之后，within-cycle 和跨 cycle 的"带代码"都是靠真实会话历史
（seg.conversation，通过 chat(history=...) 送回模型）实现的，不再是手动把代码字符串
粘回 repair_feedback/feedback——只有 conversation_history_enabled=False（矩阵 A/B 对照 /
应急回退）时才退回旧的字符串拼接方案。这里同时守住 within-cycle（session.py 内部轮次）、
cross-cycle（run_pipeline.py 跨 cycle 续跑，段级持久不随 cycle 边界清空）和黑洞熔断
（scheme reset 必须清空会话，否则"方案作废换思路"的指令和历史里的旧尝试自相矛盾）。
"""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run_pipeline  # noqa: E402
from core import Session  # noqa: E402
from core import conversation  # noqa: E402
from core.llm_client import LlmResponse  # noqa: E402
from core.preflight import PreflightResult  # noqa: E402
from core.validator import ValidationResult  # noqa: E402

TOOL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = TOOL_ROOT / "project_template"

ROUND1_MARKER = "ROUND1_MARKER_CODE_9f3a"
ROUND1_CODE = f"# {ROUND1_MARKER}\nprev = [(d.x, d.y, d.z) for d in drones]\n"


def _temp_project(source: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="repair_code_test_"))
    project = tmp / "proj"
    shutil.copytree(source, project)
    return project


def _failing_result() -> ValidationResult:
    result = ValidationResult(
        compile_ok=True, run_ok=True, read_fii_ok=True,
        distance_warnings=0, action_warnings=0,
        dense_min_distance_cm=42.0, expected_drone_count=7,
    )
    result.exit_state = [[100 + 60 * i, 100, 150] for i in range(7)]
    return result


def test_within_cycle_repair_feedback_carries_previous_code():
    """session.py: 第 2 轮发给模型的 history 必须含第 1 轮实际生成的代码
    （Phase 2a 起靠真实会话历史，不再靠字符串拼接进 repair_feedback）。"""
    project = _temp_project(TEMPLATE)
    histories: list = []
    call_count = {"n": 0}

    def fake_chat(system, user, history=None, **_kwargs):
        call_count["n"] += 1
        histories.append(history)
        if call_count["n"] == 1:
            return LlmResponse(text=f"```python\n{ROUND1_CODE}```", model="mock")
        return LlmResponse(text="```python\n# round2\nprev = [(d.x, d.y, d.z) for d in drones]\n```", model="mock")

    try:
        with patch("core.session.chat", side_effect=fake_chat), \
             patch("core.session.preflight_check", return_value=PreflightResult()), \
             patch.object(Session, "validate", return_value=_failing_result()):
            session = Session(project, gate_profile="full")
            rounds = session.generate_until_safe_with_llm(
                provider="mock", feedback="", max_attempts=2,
                use_planning_pass=False,
            )
        assert len(histories) == 2, f"expected 2 chat calls, got {len(histories)}"
        assert histories[0] in (None, []), "round 1 has no prior turns yet"
        assert histories[1], "round 2 must receive non-empty history"
        assert any(
            ROUND1_MARKER in str(turn.get("content", "")) and turn.get("role") == "assistant"
            for turn in histories[1]
        ), (
            "round-2's history is missing round-1's actual generated code as an "
            "assistant turn — the model would be regenerating blind"
        )
        # 顺带守住新增的 GenerationRound.code 字段（跨 cycle 续跑靠它拿代码）
        assert rounds[0].code.strip(), "GenerationRound.code was not populated"
        assert ROUND1_MARKER in rounds[0].code
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: within-cycle repair feedback carries previous round's code")


def test_conversation_history_disabled_falls_back_to_string_reconstruction():
    """conversation_history_enabled=False（矩阵 A/B / 应急回退）时，行为等同 Phase 2a 之前：
    没有 history，但 repair_feedback 字符串里手动带回代码。"""
    project = _temp_project(TEMPLATE)
    histories: list = []
    prompts: list[str] = []
    call_count = {"n": 0}

    def fake_chat(system, user, history=None, **_kwargs):
        call_count["n"] += 1
        histories.append(history)
        prompts.append(user)
        if call_count["n"] == 1:
            return LlmResponse(text=f"```python\n{ROUND1_CODE}```", model="mock")
        return LlmResponse(text="```python\n# round2\nprev = [(d.x, d.y, d.z) for d in drones]\n```", model="mock")

    try:
        with patch("core.session.chat", side_effect=fake_chat), \
             patch("core.session.preflight_check", return_value=PreflightResult()), \
             patch.object(Session, "validate", return_value=_failing_result()):
            session = Session(project, gate_profile="full", conversation_history_enabled=False)
            session.generate_until_safe_with_llm(
                provider="mock", feedback="", max_attempts=2,
                use_planning_pass=False,
            )
        assert all(h in (None, []) for h in histories), "history disabled must never pass history to chat()"
        assert ROUND1_MARKER in prompts[1], (
            "with history disabled, the old string-reconstruction fallback must still "
            "carry the code -- this is the emergency-rollback / matrix-A/B path"
        )
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: conversation_history_enabled=False falls back to string reconstruction")


def test_empty_code_round1_response_reaches_round2_via_history_or_fallback_text():
    """提取不到代码时，round 1 的实际响应必须以某种方式让 round 2 看到——历史开启时
    靠真实 assistant turn，关闭时靠 repair_feedback 字符串里手动带回原文。"""
    MARKER_ONLY_TEXT = "```python\n# PYFII_AGENT_SEGMENT_START id=S01\n# PYFII_AGENT_SEGMENT_END\n```"

    def _round2_signal_for(round1_text: str, conversation_history_enabled: bool):
        project = _temp_project(TEMPLATE)
        prompts: list[str] = []
        histories: list = []
        call_count = {"n": 0}

        def fake_chat(system, user, history=None, **_kwargs):
            call_count["n"] += 1
            prompts.append(user)
            histories.append(history)
            if call_count["n"] == 1:
                return LlmResponse(text=round1_text, model="mock")
            return LlmResponse(text="```python\nprev = [(d.x, d.y, d.z) for d in drones]\n```", model="mock")

        try:
            with patch("core.session.chat", side_effect=fake_chat):
                session = Session(
                    project, gate_profile="full",
                    conversation_history_enabled=conversation_history_enabled,
                )
                rounds = session.generate_until_safe_with_llm(
                    provider="mock", feedback="", max_attempts=2,
                    use_planning_pass=False,
                )
            assert rounds[0].validation is None and not rounds[0].code.strip()
            assert len(prompts) == 2
            return prompts[1], histories[1]
        finally:
            shutil.rmtree(project.parent, ignore_errors=True)

    # 历史关闭（矩阵 A/B / 回退）：字符串拼接方案原样保留
    empty_round2_prompt, empty_round2_history = _round2_signal_for("", conversation_history_enabled=False)
    assert "为空" in empty_round2_prompt or "空响应" in empty_round2_prompt
    assert empty_round2_history in (None, [])

    marker_only_round2_prompt, _ = _round2_signal_for(MARKER_ONLY_TEXT, conversation_history_enabled=False)
    assert "PYFII_AGENT_SEGMENT_START" in marker_only_round2_prompt, (
        "with history disabled, round-1's raw (unparsed) response text should be "
        "echoed back in the reconstructed feedback string"
    )

    # 历史开启（默认）：round 1 的原始响应作为真实 assistant turn 出现在 round 2 的 history 里，
    # 不需要（也不应该）在 repair_feedback 字符串里再贴一遍
    _, marker_only_history = _round2_signal_for(MARKER_ONLY_TEXT, conversation_history_enabled=True)
    assert marker_only_history, "round 2 must receive non-empty history when enabled"
    assert any(
        "PYFII_AGENT_SEGMENT_START" in str(turn.get("content", "")) and turn.get("role") == "assistant"
        for turn in marker_only_history
    ), "round-1's raw response must appear as a real assistant turn when history is enabled"
    print("PASSED: empty-code round-1 response reaches round-2 via history or fallback text")


def test_write_failure_feedback_carries_previous_code():
    """写入失败（marker 不匹配）分支也要带上代码，而不是一句空泛提示。"""
    project = _temp_project(TEMPLATE)

    def fake_chat(system, user, **_kwargs):
        return LlmResponse(text=f"```python\n{ROUND1_CODE}```", model="mock")

    try:
        with patch("core.session.chat", side_effect=fake_chat), \
             patch("core.session.preflight_check", return_value=PreflightResult()), \
             patch("core.session.replace_active_segment", return_value=False):
            session = Session(project, gate_profile="full")
            rounds = session.generate_until_safe_with_llm(
                provider="mock", feedback="", max_attempts=1,
                use_planning_pass=False,
            )
        assert len(rounds) == 1
        assert rounds[0].code.strip() and ROUND1_MARKER in rounds[0].code
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: write-failure feedback path records the previous code")


def _cross_cycle_round_with_code(code: str):
    validation = ValidationResult(
        compile_ok=True, run_ok=True, read_fii_ok=True,
        distance_warnings=0, action_warnings=0,
        dense_min_distance_cm=42.0, expected_drone_count=7,
    )
    validation.exit_state = [[100 + 60 * i, 120, 150] for i in range(7)]
    round_item = MagicMock()
    round_item.index = 1
    round_item.response = MagicMock(model="mock")
    round_item.validation = validation
    round_item.code = code
    return [round_item]


def test_cross_cycle_conversation_carries_previous_cycle_code():
    """run_pipeline.py: Phase 2b 起，跨 cycle 靠 seg.conversation（段级持久，不随 cycle
    边界清空）携带上一 cycle 的实际代码，不再是 run_pipeline.py 手动拼接进 feedback 字符串。
    这里的 fake_generate 模拟 _chat_stage 在真实调用里会做的会话历史写入。"""
    tmp = Path(tempfile.mkdtemp(prefix="repair_code_cross_cycle_"))
    project = tmp / "proj"
    shutil.copytree(TEMPLATE, project)
    conversation_at_call: list = []
    call_count = {"n": 0}

    def fake_generate(self, provider=None, feedback="", **_kwargs):
        call_count["n"] += 1
        seg = self.state.current_segment
        conversation_at_call.append(list(seg.conversation))  # 调用时刻的快照(浅拷贝列表)
        code = f"# CYCLE{call_count['n']}_MARKER\nprev = [(d.x, d.y, d.z) for d in drones]\n"
        if self.conversation_history_enabled:
            conversation.append_user(seg.conversation, f"cycle {call_count['n']} prompt", stage="direct_generation")
            conversation.append_assistant(seg.conversation, code, stage="direct_generation")
        return _cross_cycle_round_with_code(code)

    try:
        with patch.object(Session, "generate_until_safe_with_llm", fake_generate):
            run_pipeline.run_full_flow(
                project_root=project,
                provider="mock",
                max_cycles_per_segment=2,
                max_attempts_per_cycle=1,
                retry_sleep_s=0,
            )
        assert len(conversation_at_call) >= 2, f"expected >=2 cycles, got {len(conversation_at_call)}"
        assert conversation_at_call[0] == [], "cycle 1 should start with no prior conversation"
        assert any(
            "CYCLE1_MARKER" in str(turn.get("content", "")) and turn.get("role") == "assistant"
            for turn in conversation_at_call[1]
        ), (
            "cycle 2 must see cycle 1's actual generated code as a real assistant turn in "
            "seg.conversation — the cycle boundary must not clear it"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASSED: cross-cycle conversation carries previous cycle's code")


def test_cross_cycle_history_disabled_falls_back_to_string():
    """conversation_history_enabled=False 时跨 cycle 也要退回字符串拼接方案。"""
    tmp = Path(tempfile.mkdtemp(prefix="repair_code_cross_cycle_disabled_"))
    project = tmp / "proj"
    shutil.copytree(TEMPLATE, project)
    feedbacks: list[str] = []
    call_count = {"n": 0}

    def fake_generate(self, provider=None, feedback="", **_kwargs):
        call_count["n"] += 1
        feedbacks.append(feedback)
        return _cross_cycle_round_with_code(f"# CYCLE{call_count['n']}_MARKER\nprev = [(d.x, d.y, d.z) for d in drones]\n")

    try:
        with patch.object(Session, "generate_until_safe_with_llm", fake_generate):
            run_pipeline.run_full_flow(
                project_root=project,
                provider="mock",
                max_cycles_per_segment=2,
                max_attempts_per_cycle=1,
                retry_sleep_s=0,
                conversation_history_enabled=False,
            )
        assert len(feedbacks) >= 2
        assert "CYCLE1_MARKER" in feedbacks[1], (
            "with history disabled, cross-cycle feedback must still fall back to the "
            "string-reconstruction code re-embed"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASSED: cross-cycle history-disabled falls back to string reconstruction")


def test_scheme_reset_clears_conversation_history():
    """黑洞熔断触发时，seg.conversation 必须跟 candidate_pool 一起清空——否则"方案重置，
    换思路重来"的文字指令和历史里完整的旧尝试自相矛盾。3 个 cycle：cycle 1 正常（设
    prev_category），cycle 2 同类失败触发重置（清空 conversation），cycle 3 必须以空
    conversation 开始。"""
    tmp = Path(tempfile.mkdtemp(prefix="repair_code_scheme_reset_"))
    project = tmp / "proj"
    shutil.copytree(TEMPLATE, project)
    conversation_at_call: list = []
    call_count = {"n": 0}

    def fake_generate(self, provider=None, feedback="", **_kwargs):
        call_count["n"] += 1
        seg = self.state.current_segment
        conversation_at_call.append(list(seg.conversation))
        code = f"# CYCLE{call_count['n']}_MARKER\nprev = [(d.x, d.y, d.z) for d in drones]\n"
        conversation.append_user(seg.conversation, f"cycle {call_count['n']} prompt", stage="direct_generation")
        conversation.append_assistant(seg.conversation, code, stage="direct_generation")
        return _cross_cycle_round_with_code(code)

    try:
        with patch.object(Session, "generate_until_safe_with_llm", fake_generate):
            run_pipeline.run_full_flow(
                project_root=project,
                provider="mock",
                max_cycles_per_segment=3,
                max_attempts_per_cycle=1,
                retry_sleep_s=0,
            )
        assert len(conversation_at_call) >= 3, f"expected 3 cycles, got {len(conversation_at_call)}"
        # cycle 2 应该还看得到 cycle 1(尚未触发重置——同类判定要连续两次才触发，
        # 第一次"同类"识别发生在 cycle2 结束时决定 cycle3 怎么走)
        assert conversation_at_call[1], "cycle 2 should still see cycle 1's turns (reset hasn't fired yet)"
        # cycle 3 必须是空的：cycle 1/2 同类失败 → cycle 2 结束时触发重置 → 清空
        assert conversation_at_call[2] == [], (
            "cycle 3 must start with empty conversation -- scheme reset must clear "
            "seg.conversation, not just the candidate pool"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASSED: scheme reset clears conversation history")


if __name__ == "__main__":
    test_within_cycle_repair_feedback_carries_previous_code()
    test_conversation_history_disabled_falls_back_to_string_reconstruction()
    test_empty_code_round1_response_reaches_round2_via_history_or_fallback_text()
    test_write_failure_feedback_carries_previous_code()
    test_cross_cycle_conversation_carries_previous_cycle_code()
    test_cross_cycle_history_disabled_falls_back_to_string()
    test_scheme_reset_clears_conversation_history()
    print("\nALL REPAIR-CODE-CARRYOVER TESTS PASSED")
