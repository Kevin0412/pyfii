"""导演回路离线场景（3a）：反馈必达 prompt、安全不妥协、override 留痕。

样例对照（PLAN playful-greeting-yeti C7）：
- B: 直接生成路径的导演反馈必须进入实际发送的 prompt
- D: round-1 planning pass 路径同样必须携带反馈（防回归曾经的静默丢弃 bug）
- C: 物理安全（Tier-0）导演 override 也不能锁
- E: 演出完整性（Tier-1）可 override 锁定且留痕
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import Session
from core.llm_client import LlmResponse
from core.validator import ValidationResult

TOOL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = TOOL_ROOT / "project_template"
S01_FIXTURE = TOOL_ROOT / "agent_projects" / "cannon_agent_test_s01"

DIRECTOR_NOTE = "导演要求：第二个 keyframe 明显放慢，收在暖白"


def _temp_project(source: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="director_test_"))
    project = tmp / "proj"
    shutil.copytree(source, project)
    return project


def test_b_direct_generation_prompt_carries_director_feedback():
    project = _temp_project(TEMPLATE)
    captured: list[str] = []

    def fake_chat(system, user, **_kwargs):
        captured.append(user)
        return LlmResponse(text="不是代码", model="mock")

    try:
        with patch("core.session.chat", side_effect=fake_chat):
            session = Session(project, gate_profile="safety")
            session.generate_until_safe_with_llm(
                provider="mock", feedback=DIRECTOR_NOTE, max_attempts=1,
                use_planning_pass=True,
            )
        assert captured, "chat was never called"
        assert any(DIRECTOR_NOTE in prompt for prompt in captured), (
            "director feedback missing from every sent prompt"
        )
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: direct generation prompt carries director feedback")


def test_d_planning_pass_prompt_carries_director_feedback():
    project = _temp_project(S01_FIXTURE)
    # 让 S01 携带出口坐标，触发 S02 的 round-1 planning pass
    state_path = project / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    exit_state = [[100 + 60 * i, 100, 150] for i in range(int(state["drone_count"]))]
    state["segments"][0]["exit_state"] = exit_state
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    captured: list[str] = []

    def fake_chat(system, user, **_kwargs):
        captured.append(user)
        # 非 JSON → planning 解析失败走 fallback 直接生成（同样应携带反馈）
        return LlmResponse(text="不是 JSON 也不是代码", model="mock")

    try:
        with patch("core.session.chat", side_effect=fake_chat):
            session = Session(project, gate_profile="safety")
            seg = session.state.current_segment
            assert seg is not None and seg.id == "S02", f"fixture unexpected: {seg}"
            session.generate_until_safe_with_llm(
                provider="mock", feedback=DIRECTOR_NOTE, max_attempts=1,
                use_planning_pass=True,
            )
        assert captured, "chat was never called"
        planning_prompts = [p for p in captured if p.lstrip().startswith("## 规划")]
        assert planning_prompts, f"planning pass did not fire; prompts={len(captured)}"
        assert all(DIRECTOR_NOTE in p for p in planning_prompts), (
            "planning prompt dropped the director feedback (regression of the "
            "round-1 silent-drop bug)"
        )
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: planning pass prompt carries director feedback")


def _crafted_result(**overrides) -> ValidationResult:
    result = ValidationResult(
        compile_ok=True, run_ok=True, read_fii_ok=True,
        distance_warnings=0, action_warnings=0,
        dense_min_distance_cm=63.0, continuity_required=True,
        hover_check_ok=True, expected_drone_count=7,
    )
    result.exit_state = [[100 + 60 * i, 100, 150] for i in range(7)]
    for key, value in overrides.items():
        setattr(result, key, value)
    return result


def test_c_director_override_cannot_pass_tier0():
    project = _temp_project(TEMPLATE)
    try:
        session = Session(project, gate_profile="safety")
        colliding = _crafted_result(dense_min_distance_cm=45.0)
        assert not colliding.tier0_ok
        with patch.object(Session, "validate", return_value=colliding):
            approval = session.approve_and_lock(allow_human_override=True)
        assert not approval.locked, "collision must not be lockable even by override"
        assert "物理安全" in (approval.reason or "")
        assert session.state.current_segment.id == "S01"  # 没有推进
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: director override cannot pass tier-0 safety")


def test_e_director_override_locks_tier1_and_records():
    project = _temp_project(TEMPLATE)
    try:
        session = Session(project, gate_profile="safety")
        hovering = _crafted_result(hover_segments=[(6.0, 11.0)], gate_profile="safety")
        assert hovering.tier0_ok and not hovering.passed
        with patch.object(Session, "validate", return_value=hovering):
            approval = session.approve_and_lock(allow_human_override=True)
        assert approval.locked, f"tier-1 override should lock: {approval.reason}"
        assert approval.human_override
        seg = session.state.segments[0]
        assert seg.locked and seg.attempts
        assert seg.attempts[-1].get("human_override") is True
        snapshot = seg.attempts[-1].get("validation") or {}
        assert snapshot.get("passed") is False
        assert snapshot.get("gate_profile") == "safety"

        # 留痕：design_memory 记录 override 理由并能回灌 prompt 偏好
        from core.design_memory import load_preferences, record

        record(project, "segment_feedback", "[导演 override 锁定] 刻意悬停呼吸", context="S01")
        assert "刻意悬停呼吸" in load_preferences(project)
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: director override locks tier-1 with audit trail")


if __name__ == "__main__":
    test_b_direct_generation_prompt_carries_director_feedback()
    test_d_planning_pass_prompt_carries_director_feedback()
    test_c_director_override_cannot_pass_tier0()
    test_e_director_override_locks_tier1_and_records()
    print("\nALL DIRECTOR SESSION TESTS PASSED")
