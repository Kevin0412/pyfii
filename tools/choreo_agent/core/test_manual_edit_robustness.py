"""人工改 design.py 的鲁棒性（C11b）：检测、告警、采纳。"""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import Session
from core import conversation
from core.script_editor import (
    lock_segment,
    replace_active_segment,
    segment_body_hashes,
)
from core.validator import ValidationResult

TEMPLATE = Path(__file__).resolve().parent.parent / "project_template"

S01_CODE = (
    "    auto_init(drones)\n"
    "    prev = [(d.x, d.y, d.z) for d in drones]\n"
    "    for i, drone in enumerate(drones):\n"
    "        move2(drone, (100 + 60 * i, 120, 150), 3000)\n"
    "        apply_light(drone, \"#44aaff\", 4)\n"
    "        drone.delay(2700)\n"
)


def _project() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="manual_edit_"))
    project = tmp / "proj"
    shutil.copytree(TEMPLATE, project)
    return project


def _lock_s01_manually(project: Path) -> Session:
    """模拟一次正常锁定：写码 → 标记 locked → state 记录哈希与出口。"""
    script = project / "scripts" / "design.py"
    session = Session(project, gate_profile="safety")
    assert replace_active_segment(script, "S01", S01_CODE, [])
    assert lock_segment(script, "S01")
    seg = session.state.segments[0]
    seg.locked = True
    seg.exit_state = [[100 + 60 * i, 120, 150] for i in range(7)]
    seg.locked_hash = segment_body_hashes(script, ["S01"])["S01"]
    session.state.locked_segment_ids = ["S01"]
    session.state.current_segment_index = 1
    session.state.save(project)
    return Session(project, gate_profile="safety")


def _tamper_s01(project: Path) -> None:
    script = project / "scripts" / "design.py"
    text = script.read_text(encoding="utf-8")
    script.write_text(text.replace("(100 + 60 * i, 120, 150)", "(100 + 60 * i, 200, 150)"),
                      encoding="utf-8")


def test_clean_project_reports_clean():
    project = _project()
    try:
        session = _lock_s01_manually(project)
        report = session.integrity_report()
        assert report["tampered_locked"] == []
        assert not report["active_edited"]
        assert report["missing_markers"] == []
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: clean project reports clean")


def test_tampered_locked_segment_detected_and_adopted():
    project = _project()
    try:
        session = _lock_s01_manually(project)
        _tamper_s01(project)
        session = Session(project, gate_profile="safety")
        report = session.integrity_report()
        assert report["tampered_locked"] == ["S01"], report

        # 采纳：脚本能跑 → 刷新出口坐标与指纹
        good = ValidationResult(
            compile_ok=True, run_ok=True, read_fii_ok=True,
            distance_warnings=0, action_warnings=0,
            dense_min_distance_cm=70.0, expected_drone_count=7,
        )
        good.exit_state = [[100 + 60 * i, 200, 150] for i in range(7)]
        new_exit = [[100 + 60 * i, 200, 150] for i in range(7)]
        with patch.object(Session, "validate", return_value=good), \
                patch("core.validator._sample_exit_state", return_value=new_exit):
            outcome = session.adopt_manual_edits()
        assert outcome["adopted"] == ["S01"], outcome
        assert session.state.segments[0].exit_state == new_exit
        assert session.integrity_report()["tampered_locked"] == []
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: tampered locked segment detected and adopted")


def test_adopt_rejects_broken_script():
    project = _project()
    try:
        session = _lock_s01_manually(project)
        _tamper_s01(project)
        session = Session(project, gate_profile="safety")
        broken = ValidationResult(compile_ok=False, expected_drone_count=7)
        with patch.object(Session, "validate", return_value=broken):
            outcome = session.adopt_manual_edits()
        assert outcome["adopted"] == [] and outcome["rejected"] == ["S01"]
        assert "先修复" in outcome["reason"]
        # 指纹未被刷新，警告保持
        assert session.integrity_report()["tampered_locked"] == ["S01"]
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: adopt rejects broken script")


def test_active_segment_external_edit_detected():
    project = _project()
    try:
        script = project / "scripts" / "design.py"
        session = Session(project, gate_profile="safety")
        seg = session.state.segments[0]
        assert replace_active_segment(script, "S01", S01_CODE, [])
        seg.last_agent_hash = segment_body_hashes(script, ["S01"])["S01"]
        session.state.save(project)

        session = Session(project, gate_profile="safety")
        assert not session.integrity_report()["active_edited"]
        _tamper_s01(project)
        assert session.integrity_report()["active_edited"]
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: active segment external edit detected")


def test_adopting_active_edit_clears_stale_conversation():
    """人工改了当前(未锁定)段后 adopt：AI 自己那份"我写了什么"的会话记忆已经不描述
    design.py 实际内容了，必须清空——否则下一次 g 会把过时的旧尝试当成现状看待。"""
    project = _project()
    try:
        script = project / "scripts" / "design.py"
        session = Session(project, gate_profile="safety")
        seg = session.state.segments[0]
        assert replace_active_segment(script, "S01", S01_CODE, [])
        seg.last_agent_hash = segment_body_hashes(script, ["S01"])["S01"]
        conversation.append_user(seg.conversation, "AI 的上一轮 prompt", stage="direct_generation")
        conversation.append_assistant(seg.conversation, S01_CODE, stage="direct_generation")
        session.state.save(project)

        session = Session(project, gate_profile="safety")
        assert session.state.segments[0].conversation, "fixture 应该带着非空历史"
        _tamper_s01(project)
        assert session.integrity_report()["active_edited"]

        with patch.object(
            Session, "validate",
            return_value=ValidationResult(compile_ok=True, run_ok=True, read_fii_ok=True, expected_drone_count=7),
        ):
            outcome = session.adopt_manual_edits()
        assert any("active" in item for item in outcome["adopted"]), outcome
        assert session.state.segments[0].conversation == [], (
            "adopting a hand-edit to the active segment must clear its stale conversation history"
        )
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)
    print("PASSED: adopting an active-segment edit clears stale conversation")


if __name__ == "__main__":
    test_clean_project_reports_clean()
    test_tampered_locked_segment_detected_and_adopted()
    test_adopt_rejects_broken_script()
    test_active_segment_external_edit_detected()
    test_adopting_active_edit_clears_stale_conversation()
    print("\nALL MANUAL EDIT ROBUSTNESS TESTS PASSED")
