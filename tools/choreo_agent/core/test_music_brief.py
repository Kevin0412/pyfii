"""Music brief formatting and planning-prompt injection tests."""

from core.music_brief import format_segment_music_hint
from core.planning_pass import build_planning_prompt

_BRIEF = {
    "music_source": "cannon_in_D.mp3",
    "duration_s": 68.0,
    "tempo_bpm": 103.4,
    "beat_interval_s": 0.58,
    "hard_cues": [4.1, 10.2, 17.7, 19.8, 23.1, 37.0],
    "sections": [
        {"time_range": [12.0, 16.0], "energy": 0.27, "energy_label": "low", "onset_per_s": 3.4},
        {"time_range": [16.0, 20.0], "energy": 0.41, "energy_label": "mid", "onset_per_s": 3.9},
        {"time_range": [20.0, 24.0], "energy": 0.43, "energy_label": "mid", "onset_per_s": 3.8},
    ],
}

_PREV_9 = [[80, 80, 110]] * 9


def test_hint_covers_window_sections_and_cues():
    hint = format_segment_music_hint(_BRIEF, 13.0, 23.0)
    assert "能量曲线" in hint
    assert "low(0.27)" in hint
    assert "17.7s" in hint and "19.8s" in hint
    assert "37.0" not in hint  # outside window
    assert "100ms tick" in hint


def test_hint_empty_for_missing_brief():
    assert format_segment_music_hint(None, 13.0, 23.0) == ""
    assert format_segment_music_hint({}, 13.0, 23.0) == ""
    assert format_segment_music_hint(_BRIEF, 200.0, 210.0) == ""


def test_planning_prompt_includes_music_evidence():
    prompt = build_planning_prompt(
        "S02", 13.0, 23.0, "展开", _PREV_9, drone_count=9, music_brief=_BRIEF
    )
    assert "音乐证据" in prompt
    assert "tempo 103.4" in prompt

    bare = build_planning_prompt(
        "S02", 13.0, 23.0, "展开", _PREV_9, drone_count=9
    )
    assert "音乐证据" not in bare


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASSED: {name}")
    print("\nALL MUSIC BRIEF TESTS PASSED")
