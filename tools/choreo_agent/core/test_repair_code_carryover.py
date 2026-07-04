"""修复反馈必须带上一轮实际代码。

chat() 是无状态单轮调用（system+user 各一条，不带历史，core/llm_client.py:96-104），
模型看不到自己上一轮写了什么。validate() 失败后的 repair feedback 曾经只有诊断文字
（distance/motion/... 数值 + 定向修复提示），完全不含上一轮生成/写入的代码——模型
每次都在盲写整段，_targeted_validation_repair_feedback 里"保留现有结构只外推
15-30cm"这类提示离开代码就是空中楼阁。这里同时守住 within-cycle（session.py 内部
轮次）和 cross-cycle（run_pipeline.py 跨 cycle 续跑）两条路径。
"""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run_pipeline  # noqa: E402
from core import Session  # noqa: E402
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
    """session.py: 第 2 轮发出的 prompt 必须含第 1 轮实际生成的代码。"""
    project = _temp_project(TEMPLATE)
    prompts: list[str] = []
    call_count = {"n": 0}

    def fake_chat(system, user, **_kwargs):
        call_count["n"] += 1
        prompts.append(user)
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
        assert len(prompts) == 2, f"expected 2 chat calls, got {len(prompts)}"
        assert ROUND1_MARKER in prompts[1], (
            "round-2 prompt is missing round-1's actual generated code — "
            "the model would be regenerating blind"
        )
        # 顺带守住新增的 GenerationRound.code 字段（跨 cycle 续跑靠它拿代码）
        assert rounds[0].code.strip(), "GenerationRound.code was not populated"
        assert ROUND1_MARKER in rounds[0].code
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: within-cycle repair feedback carries previous round's code")


def test_empty_code_feedback_shows_raw_response_when_available():
    """提取不到代码时：响应为空只说"为空"；响应非空(如纯 marker 行)要把原文带回去，
    否则模型不知道自己刚才实际输出了什么、为什么没被当成代码。"""
    MARKER_ONLY_TEXT = "```python\n# PYFII_AGENT_SEGMENT_START id=S01\n# PYFII_AGENT_SEGMENT_END\n```"

    def _round2_prompt_for(round1_text: str) -> str:
        project = _temp_project(TEMPLATE)
        prompts: list[str] = []
        call_count = {"n": 0}

        def fake_chat(system, user, **_kwargs):
            call_count["n"] += 1
            prompts.append(user)
            if call_count["n"] == 1:
                return LlmResponse(text=round1_text, model="mock")
            return LlmResponse(text="```python\nprev = [(d.x, d.y, d.z) for d in drones]\n```", model="mock")

        try:
            with patch("core.session.chat", side_effect=fake_chat):
                session = Session(project, gate_profile="full")
                rounds = session.generate_until_safe_with_llm(
                    provider="mock", feedback="", max_attempts=2,
                    use_planning_pass=False,
                )
            assert rounds[0].validation is None and not rounds[0].code.strip()
            assert len(prompts) == 2
            return prompts[1]
        finally:
            shutil.rmtree(project.parent, ignore_errors=True)

    empty_round2_prompt = _round2_prompt_for("")
    assert "为空" in empty_round2_prompt or "空响应" in empty_round2_prompt

    marker_only_round2_prompt = _round2_prompt_for(MARKER_ONLY_TEXT)
    assert "PYFII_AGENT_SEGMENT_START" in marker_only_round2_prompt, (
        "round-1's raw (unparsed) response text should be echoed back when it's "
        "non-empty but yielded no extractable code"
    )
    print("PASSED: empty-code feedback differentiates truly-empty vs unparsed-content")


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


def test_cross_cycle_feedback_carries_previous_cycle_code():
    """run_pipeline.py: cycle 2 的 feedback 必须含 cycle 1 最后一轮实际生成的代码。"""
    tmp = Path(tempfile.mkdtemp(prefix="repair_code_cross_cycle_"))
    project = tmp / "proj"
    shutil.copytree(TEMPLATE, project)
    feedbacks: list[str] = []
    call_count = {"n": 0}

    def _round_with_code(code: str):
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

    def fake_generate(self, provider=None, feedback="", **_kwargs):
        call_count["n"] += 1
        feedbacks.append(feedback)
        return _round_with_code(f"# CYCLE{call_count['n']}_MARKER\nprev = [(d.x, d.y, d.z) for d in drones]\n")

    try:
        with patch.object(Session, "generate_until_safe_with_llm", fake_generate):
            run_pipeline.run_full_flow(
                project_root=project,
                provider="mock",
                max_cycles_per_segment=2,
                max_attempts_per_cycle=1,
                retry_sleep_s=0,
            )
        assert len(feedbacks) >= 2, f"expected >=2 cycles, got {len(feedbacks)}"
        assert "CYCLE1_MARKER" in feedbacks[1], (
            "cycle-2 feedback is missing cycle-1's actual generated code — "
            "the model would be regenerating blind across cycles too"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASSED: cross-cycle feedback carries previous cycle's code")


if __name__ == "__main__":
    test_within_cycle_repair_feedback_carries_previous_code()
    test_empty_code_feedback_shows_raw_response_when_available()
    test_write_failure_feedback_carries_previous_code()
    test_cross_cycle_feedback_carries_previous_cycle_code()
    print("\nALL REPAIR-CODE-CARRYOVER TESTS PASSED")
