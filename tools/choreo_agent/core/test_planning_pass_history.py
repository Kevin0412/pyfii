"""Phase 3：三段式规划（plan JSON → 检查器修正 → code）接入真实会话历史。

修正阶段此前用 `system=""`（该任务本来就需要 planning 阶段的坐标/间距规则，空 system
让模型只能凭 revision prompt 里的只言片语猜规则）——现在传 `build_planning_system_prompt`。
三个阶段都接入 `seg.conversation`：同一轮内 coding 阶段应该看得到 planning 阶段刚产出的
plan JSON 作为历史；跨轮/跨 cycle 时，本轮的 planning_json 也应该看得到上一轮真实发生的
交换（不再是 Phase 3 之前那样固定拿到 use_history=False 的空历史）。
"""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import Session  # noqa: E402
from core.llm_client import LlmResponse  # noqa: E402

TOOL_ROOT = Path(__file__).resolve().parent.parent
S01_FIXTURE = TOOL_ROOT / "agent_projects" / "cannon_agent_test_s01"


def _temp_project(source: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="planning_history_test_"))
    project = tmp / "proj"
    shutil.copytree(source, project)
    return project


def test_revision_stage_gets_real_planning_system_prompt_not_empty():
    """_refine_plan_with_checker 的修正调用不能再传 system=""。"""
    project = _temp_project(S01_FIXTURE)
    captured_systems: list[str] = []

    def fake_chat(system, user, **_kwargs):
        captured_systems.append(system)
        return LlmResponse(text='{"keyframes": []}', model="mock")  # 解析后仍然违规，触发继续修正

    try:
        with patch("core.session.chat", side_effect=fake_chat):
            session = Session(project, gate_profile="safety")
            seg = session.state.current_segment
            bad_plan = {"keyframes": []}  # evaluate_plan_safety 对空 keyframes 直接判违规
            session._refine_plan_with_checker(
                seg=seg, provider="mock", plan=bad_plan,
                prev_state=[[100 + 60 * i, 100, 150] for i in range(7)],
                feedback="",
            )
        assert captured_systems, "revision stage never called chat()"
        assert all(s.strip() for s in captured_systems), (
            "revision stage must not send an empty system prompt"
        )
        from core.planning_pass import build_planning_system_prompt
        expected = build_planning_system_prompt(session.state.drone_count)
        assert captured_systems[0] == expected, "revision system prompt must be the real planning system prompt"
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: revision stage gets the real planning system prompt")


def test_coding_stage_sees_planning_stage_history_in_same_round():
    """同一轮内：planning_json 产出的 plan JSON 必须以 assistant turn 出现在
    planning_code 收到的 history 里（不再是 Phase 3 之前的 use_history=False 空历史）。"""
    project = _temp_project(S01_FIXTURE)
    histories_by_stage: dict[str, list] = {}
    call_count = {"n": 0}

    PLAN_MARKER = "PLAN_JSON_MARKER_7f2a"

    def fake_chat(system, user, history=None, **_kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Stage 1: planning_json —— 返回一个安全、合法的 plan(带可识别 marker 便于断言)
            histories_by_stage["planning_json"] = history
            return LlmResponse(
                text=(
                    '{"'
                    + PLAN_MARKER
                    + '": true, "keyframes": [{"targets": '
                    + str([[100 + 60 * i, 160, 150] for i in range(7)])
                    + ', "flying_ms": 3000}]}'
                ),
                model="mock",
            )
        # Stage 3: planning_code（本次 plan 应该直接过检查器，不触发修正轮）
        histories_by_stage["planning_code"] = history
        return LlmResponse(text="prev = [(d.x, d.y, d.z) for d in drones]\n", model="mock")

    try:
        with patch("core.session.chat", side_effect=fake_chat):
            session = Session(project, gate_profile="safety")
            session.generate_until_safe_with_llm(
                provider="mock", feedback="", max_attempts=1,
                use_planning_pass=True,
            )
        assert "planning_code" in histories_by_stage, "planning_code stage was never reached"
        coding_history = histories_by_stage["planning_code"] or []
        assert any(
            PLAN_MARKER in str(turn.get("content", "")) and turn.get("role") == "assistant"
            for turn in coding_history
        ), "planning_code must see planning_json's actual plan output as a real assistant turn"
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: coding stage sees planning stage's history within the same round")


if __name__ == "__main__":
    test_revision_stage_gets_real_planning_system_prompt_not_empty()
    test_coding_stage_sees_planning_stage_history_in_same_round()
    print("\nALL PLANNING-PASS HISTORY TESTS PASSED")
