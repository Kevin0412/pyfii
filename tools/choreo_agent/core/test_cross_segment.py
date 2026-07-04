"""跨段语义（P2）：设计卡在锁定时留存、生成下一段时前传进 prompt。"""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import Session
from core.llm_client import LlmResponse
from core.prompt_builder import format_prev_design_card
from core.script_editor import lock_segment, replace_active_segment
from core.validator import ValidationResult

TEMPLATE = Path(__file__).resolve().parent.parent / "project_template"

S01_WITH_CARD = (
    "    # role: 主题引入\n"
    "    # motifs: 斜线推进; 宽V\n"
    "    # beat: 两拍推进\n"
    "    # formation: 斜线到宽V\n"
    "    # lighting: 浅蓝白开场\n"
    "    auto_init(drones)\n"
    "    prev = [(d.x, d.y, d.z) for d in drones]\n"
)


def _project() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="cross_seg_"))
    project = tmp / "proj"
    shutil.copytree(TEMPLATE, project)
    return project


def _passing_result() -> ValidationResult:
    result = ValidationResult(
        compile_ok=True, run_ok=True, read_fii_ok=True,
        distance_warnings=0, action_warnings=0,
        dense_min_distance_cm=70.0, expected_drone_count=7,
    )
    result.exit_state = [[100 + 60 * i, 120, 150] for i in range(7)]
    return result


def test_format_prev_design_card():
    assert format_prev_design_card(None) == ""
    assert format_prev_design_card({}) == ""
    text = format_prev_design_card({"motifs": "斜线推进; 宽V", "lighting": "浅蓝白"})
    assert "上一段设计卡" in text and "斜线推进" in text and "承接" in text
    print("PASSED: prev design card formatting")


def test_lock_stores_design_card():
    project = _project()
    try:
        script = project / "scripts" / "design.py"
        session = Session(project, gate_profile="safety")
        assert replace_active_segment(script, "S01", S01_WITH_CARD, [])
        with patch.object(Session, "validate", return_value=_passing_result()):
            approval = session.approve_and_lock()
        assert approval.locked
        card = session.state.segments[0].design_card
        assert card.get("motifs") == "斜线推进; 宽V", card
        # 持久化往返
        reloaded = Session(project, gate_profile="safety")
        assert reloaded.state.segments[0].design_card.get("motifs") == "斜线推进; 宽V"
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: lock stores design card")


def test_next_segment_prompts_carry_prev_card():
    project = _project()
    captured: list[str] = []

    def fake_chat(system, user, **_kwargs):
        captured.append(user)
        return LlmResponse(text="不是代码", model="mock")

    try:
        script = project / "scripts" / "design.py"
        session = Session(project, gate_profile="safety")
        assert replace_active_segment(script, "S01", S01_WITH_CARD, [])
        with patch.object(Session, "validate", return_value=_passing_result()):
            assert session.approve_and_lock().locked

        with patch("core.session.chat", side_effect=fake_chat):
            session = Session(project, gate_profile="safety")
            assert session.state.current_segment.id == "S02"
            session.generate_until_safe_with_llm(
                provider="mock", feedback="呼应上一段的斜线母题", max_attempts=1,
                use_planning_pass=True,
            )
        assert captured
        carriers = [p for p in captured if "上一段设计卡" in p and "斜线推进" in p]
        assert carriers, "prev design card 没有进入任何实际发送的 prompt"
        # planning 路径也要携带（S01 有 exit_state → planning 触发）
        planning = [p for p in captured if p.lstrip().startswith("## 规划")]
        assert planning and all("上一段设计卡" in p for p in planning), (
            "planning prompt 未携带上一段设计卡"
        )
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: next segment prompts carry prev card")


if __name__ == "__main__":
    test_format_prev_design_card()
    test_lock_stores_design_card()
    test_next_segment_prompts_carry_prev_card()
    print("\nALL CROSS SEGMENT TESTS PASSED")
