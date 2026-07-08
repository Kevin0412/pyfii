"""Session.checkpoint_save/list/restore 端到端测试。

覆盖 core/checkpoint.py（原来是从未被调用的死代码）接线进 Session 之后的正确性，
尤其是 restore 之后必须重新按 design.py marker 同步 state（否则 state.json 里的
锁定信息会跟还原后的文件内容对不上，续写会按错误的段结构规划），以及因还原而
从"已锁定"变回"未锁定"的段要清空会话历史（AI 记得的"自己写了什么"不再对应
磁盘上的内容）。
"""
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import Session, conversation  # noqa: E402
from core.validator import ValidationResult  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "project_template"


def _project() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="ckpt_session_test_"))
    project = tmp / "proj"
    shutil.copytree(TEMPLATE, project)
    return project


def _passing_result() -> ValidationResult:
    result = ValidationResult(
        compile_ok=True, run_ok=True, read_fii_ok=True,
        distance_warnings=0, action_warnings=0,
        dense_min_distance_cm=63.0, expected_drone_count=7,
    )
    result.exit_state = [[100 + 60 * i, 120, 150] for i in range(7)]
    return result


def test_checkpoint_restore_resyncs_locks_and_resets_conversation():
    project = _project()
    try:
        session = Session(project, gate_profile="safety")
        with patch.object(Session, "validate", return_value=_passing_result()):
            approval = session.approve_and_lock(allow_human_override=True)
            assert approval.locked and session.state.locked_segment_ids == ["S01"]

            checkpoint_path = session.checkpoint_save()
            assert checkpoint_path is not None
            checkpoint_name = checkpoint_path.name

            seg02 = session.state.current_segment
            assert seg02.id == "S02"
            conversation.append_user(seg02.conversation, "test feedback", stage="direct_generation")
            conversation.append_assistant(seg02.conversation, "prev = [...]", stage="direct_generation")
            session.save()

            approval2 = session.approve_and_lock(allow_human_override=True)
            assert approval2.locked and session.state.locked_segment_ids == ["S01", "S02"]

        ok = session.checkpoint_restore(checkpoint_name)
        assert ok
        # 内存里的 session 立刻就要反映还原后的状态——不用等下次 Session() 重建。
        assert session.state.locked_segment_ids == ["S01"]
        assert session.state.current_segment.id == "S02"

        # 落盘也要一致：重新从磁盘加载一份验证 state.json/design.py 没有互相矛盾。
        reloaded = Session(project, gate_profile="safety")
        assert reloaded.state.locked_segment_ids == ["S01"]
        assert reloaded.state.current_segment.id == "S02"

        seg02_after = next(s for s in reloaded.state.segments if s.id == "S02")
        assert seg02_after.conversation == []
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)


def test_checkpoint_restore_unknown_name_returns_false():
    project = _project()
    try:
        session = Session(project, gate_profile="safety")
        assert session.checkpoint_restore("does_not_exist.py") is False
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)


def test_checkpoint_list_empty_before_any_save():
    project = _project()
    try:
        session = Session(project, gate_profile="safety")
        assert session.checkpoint_list() == []
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)


def test_checkpoint_save_and_list_round_trip():
    project = _project()
    try:
        session = Session(project, gate_profile="safety")
        path = session.checkpoint_save()
        assert path is not None and path.exists()
        assert session.checkpoint_list() == [path.name]
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)


if __name__ == "__main__":
    print("This test file requires pytest; run via pytest.")
