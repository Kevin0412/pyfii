"""Design memory (HITL 偏好持久化) tests."""

import json
import tempfile
from pathlib import Path

from core.design_memory import format_preferences_block, load_preferences, record
from core.prompt_builder import build_segment_prompt
from core.composition_planner import build_planner_prompt

_BRIEF = {
    "music_source": "x.mp3", "duration_s": 70.0, "tempo_bpm": 120.0,
    "beat_interval_s": 0.5, "hard_cues": [4.0],
    "sections": [{"time_range": [0, 4], "energy": 0.3, "energy_label": "mid", "onset_per_s": 2}],
}


def test_record_and_load_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        record(d, "plan_directive", "开场要更神秘", context="测试曲")
        record(d, "session_verdict", "整体太快，S03 最好")
        prefs = load_preferences(d)
        assert "开场要更神秘" in prefs
        assert "章法评审意见" in prefs and "Session 验收" in prefs
        assert "测试曲" in prefs


def test_load_caps_to_recent():
    with tempfile.TemporaryDirectory() as d:
        for i in range(60):
            record(d, "segment_feedback", f"意见编号 {i} " + "x" * 50)
        prefs = load_preferences(d, max_chars=500)
        assert len(prefs) <= 540
        assert "意见编号 59" in prefs  # 最近的保留
        assert "截断" in prefs


def test_empty_memory_yields_empty_block():
    with tempfile.TemporaryDirectory() as d:
        assert load_preferences(d) == ""
    assert format_preferences_block("") == ""
    assert "人类偏好记忆" in format_preferences_block("xx")


def test_segment_prompt_injects_preferences():
    _system, user = build_segment_prompt(
        "S03", 23.0, 31.0, "x", [[100, 100, 120]] * 9, "", drone_count=9,
        human_preferences="不要纯圆形，导演讨厌正圆",
    )
    assert "人类偏好记忆" in user and "讨厌正圆" in user
    _system2, user2 = build_segment_prompt(
        "S03", 23.0, 31.0, "x", [[100, 100, 120]] * 9, "", drone_count=9,
    )
    assert "人类偏好记忆" not in user2


def test_planner_prompt_injects_preferences():
    p = build_planner_prompt(_BRIEF, 9, preferences="高潮永远不要超过 50s 处")
    assert "人类偏好记忆" in p and "50s" in p


def test_review_loop_records_to_memory():
    from core.composition_planner import plan_review_loop
    import core.music_brief as mb
    from core.test_composition_planner import _good_plan

    inputs = iter(["S05 要留白", ""])
    real = mb.generate_music_brief
    mb.generate_music_brief = lambda path, **kw: dict(_BRIEF, hard_cues=[4.0], sections=_BRIEF["sections"])
    try:
        with tempfile.TemporaryDirectory() as d:
            plan_review_loop(
                "fake.mp3", "deepseek", 9,
                chat_fn=lambda prompt: json.dumps(_good_plan(), ensure_ascii=False),
                input_fn=lambda _: next(inputs),
                print_fn=lambda _: None,
                memory_root=d,
            )
            text = (Path(d) / "design_memory.md").read_text(encoding="utf-8")
            assert "S05 要留白" in text
            assert "章法通过" in text
    finally:
        mb.generate_music_brief = real


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASSED: {name}")
    print("\nALL DESIGN MEMORY TESTS PASSED")
