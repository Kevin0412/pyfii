"""core/conversation.py: 段级持久会话历史的纯函数操作。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shutil
import tempfile

from core import conversation as conv  # noqa: E402
from core.state import ProjectState, SegmentState  # noqa: E402


def test_segment_conversation_round_trips_through_save_load():
    tmp = Path(tempfile.mkdtemp(prefix="conv_state_"))
    try:
        seg = SegmentState(id="S01", start_time=0.0, end_time=10.0)
        conv.append_user(seg.conversation, "把颜色改暖一点", stage="direct_generation")
        conv.append_assistant(seg.conversation, "prev = [...]", stage="direct_generation")
        state = ProjectState(name="proj", segments=[seg])
        state.save(tmp)

        reloaded = ProjectState.load(tmp)
        assert len(reloaded.segments[0].conversation) == 2
        assert reloaded.segments[0].conversation[0]["role"] == "user"
        assert reloaded.segments[0].conversation[1]["content"] == "prev = [...]"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASSED: SegmentState.conversation round-trips through save/load")


def test_fresh_segment_state_has_empty_conversation():
    seg = SegmentState(id="S01", start_time=0.0, end_time=10.0)
    assert seg.conversation == [], "segment-boundary reset must be free -- a new segment starts empty"
    print("PASSED: fresh SegmentState starts with empty conversation")


def test_append_user_then_assistant_alternates():
    turns: list = []
    conv.append_user(turns, "hello", stage="direct_generation")
    conv.append_assistant(turns, "world", stage="direct_generation", meta={"model": "mock"})
    assert [t["role"] for t in turns] == ["user", "assistant"]
    assert turns[0]["content"] == "hello"
    assert turns[1]["content"] == "world"
    assert turns[1]["meta"] == {"model": "mock"}
    print("PASSED: append alternates user/assistant")


def test_same_role_appends_merge_instead_of_breaking_alternation():
    turns: list = []
    conv.append_user(turns, "first", stage="a")
    conv.append_user(turns, "second", stage="b")  # 正常路径不该发生，异常/重试路径可能漏配对
    assert len(turns) == 1, "same-role appends must merge, not create two adjacent same-role turns"
    assert turns[0]["content"] == "first\n\nsecond"
    print("PASSED: same-role appends merge rather than break strict alternation")


def test_to_messages_strips_stage_and_meta():
    turns: list = []
    conv.append_user(turns, "hello", stage="direct_generation")
    conv.append_assistant(turns, "world", stage="direct_generation", meta={"model": "mock"})
    messages = conv.to_messages(turns)
    assert messages == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ], "to_messages must only surface role/content -- stage/meta are internal bookkeeping"
    print("PASSED: to_messages strips stage/meta")


def test_total_chars_sums_content_length():
    turns: list = []
    conv.append_user(turns, "abc", stage="x")
    conv.append_assistant(turns, "defgh", stage="x")
    assert conv.total_chars(turns) == 8
    print("PASSED: total_chars sums content length")


def test_reset_clears_in_place():
    turns: list = []
    conv.append_user(turns, "abc", stage="x")
    conv.append_assistant(turns, "def", stage="x")
    same_object = turns
    conv.reset(turns)
    assert turns == []
    assert same_object is turns, "reset must clear in place, not rebind to a new list"
    print("PASSED: reset clears in place")


def test_format_debug_transcript_empty_and_nonempty():
    assert conv.format_debug_transcript([]) == "(空会话)"
    turns: list = []
    conv.append_user(turns, "把颜色改暖一点", stage="direct_generation")
    conv.append_assistant(turns, "prev = [(d.x, d.y, d.z) for d in drones]", stage="direct_generation")
    text = conv.format_debug_transcript(turns)
    assert "turn 1 [user/direct_generation]" in text
    assert "turn 2 [assistant/direct_generation]" in text
    assert "把颜色改暖一点" in text
    print("PASSED: format_debug_transcript renders empty and non-empty transcripts")


def test_limit_text_truncates_with_marker():
    assert conv.limit_text("short", 100) == "short"
    truncated = conv.limit_text("x" * 20, 10)
    assert truncated.startswith("x" * 10)
    assert "truncated 10 chars" in truncated
    print("PASSED: limit_text truncates with a marker")


if __name__ == "__main__":
    test_segment_conversation_round_trips_through_save_load()
    test_fresh_segment_state_has_empty_conversation()
    test_append_user_then_assistant_alternates()
    test_same_role_appends_merge_instead_of_breaking_alternation()
    test_to_messages_strips_stage_and_meta()
    test_total_chars_sums_content_length()
    test_reset_clears_in_place()
    test_format_debug_transcript_empty_and_nonempty()
    test_limit_text_truncates_with_marker()
    print("\nALL CONVERSATION MODULE TESTS PASSED")
