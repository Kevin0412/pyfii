"""Music-driven composition planner tests (offline, chat injected)."""

import json

from core.composition_planner import (
    build_planner_prompt,
    generate_composition_plan,
    parse_planner_json,
    to_legacy_plan,
    validate_music_plan,
)

_BRIEF = {
    "music_source": "x.mp3",
    "duration_s": 70.0,
    "tempo_bpm": 120.0,
    "beat_interval_s": 0.5,
    "hard_cues": [4.1, 12.8, 23.0, 31.2, 46.8, 58.1, 63.0],
    "sections": [
        {"time_range": [0, 4], "energy": 0.2, "energy_label": "low", "onset_per_s": 2.0},
        {"time_range": [4, 30], "energy": 0.45, "energy_label": "mid", "onset_per_s": 3.0},
        {"time_range": [30, 60], "energy": 0.7, "energy_label": "high", "onset_per_s": 3.5},
        {"time_range": [60, 70], "energy": 0.3, "energy_label": "low", "onset_per_s": 2.0},
    ],
}


def _good_plan():
    seg = lambda sid, a, b: {
        "id": sid, "start_s": a, "end_s": b, "role": f"{sid} 角色",
        "motifs": ["m"], "avoid": [], "lighting_register": "identity",
        "music_cue": "cue",
    }
    return {
        "theme": "T", "dramaturgy": "D", "light_arc": "L", "centroid_arc": "C",
        "movement_motifs": ["a"], "continuity_rules": ["r"],
        "segments": [
            seg("S01", 4.0, 13.0), seg("S02", 13.0, 23.0), seg("S03", 23.0, 31.0),
            seg("S04", 31.0, 47.0), seg("S05", 47.0, 58.0), seg("S06", 58.0, 63.0),
            {"id": "LAND", "start_s": 63.0, "end_s": 68.0},
        ],
    }


def test_prompt_carries_music_evidence_and_no_fake_climax_rule():
    p = build_planner_prompt(_BRIEF, 9)
    assert "hard cues" in p and "12.8" in p
    assert "能量曲线" in p
    assert "没有 high 能量段" not in p  # this brief HAS high sections
    flat = dict(_BRIEF, sections=[dict(s, energy_label="mid") for s in _BRIEF["sections"]])
    p2 = build_planner_prompt(flat, 9)
    assert "不要伪造爆发" in p2  # cjxq guard appears for flat music


def test_validator_accepts_good_plan():
    ok, report = validate_music_plan(_good_plan(), _BRIEF)
    assert ok, report


def test_validator_rejects_structural_problems():
    plan = _good_plan()
    plan["segments"][2]["start_s"] = 24.0  # gap with S02 end 23.0
    ok, report = validate_music_plan(plan, _BRIEF)
    assert not ok and "不连续" in report

    plan2 = _good_plan()
    plan2["segments"][-1]["end_s"] = 80.0  # beyond music
    ok2, r2 = validate_music_plan(plan2, _BRIEF)
    assert not ok2 and "超出音乐" in r2

    plan3 = _good_plan()
    del plan3["segments"][4]  # missing S05
    ok3, r3 = validate_music_plan(plan3, _BRIEF)
    assert not ok3 and "S05" in r3

    plan4 = _good_plan()
    plan4["segments"][0]["role"] = ""
    ok4, r4 = validate_music_plan(plan4, _BRIEF)
    assert not ok4 and "role" in r4


def test_legacy_shape_compatible_with_prompt_builder():
    legacy = to_legacy_plan(_good_plan())
    assert legacy["segment_roles"]["S03"]["role"]
    assert "LAND" not in legacy["segment_roles"]
    from core.prompt_builder import build_segment_prompt  # consumes composition_plan
    from core.planning_pass import _format_planning_composition_plan
    text = _format_planning_composition_plan(legacy, "S03")
    assert "current role" in text


def test_generate_with_revision_loop(monkeypatch=None):
    calls = []

    def fake_chat(prompt):
        calls.append(prompt)
        if len(calls) == 1:
            bad = _good_plan()
            bad["segments"][-1]["end_s"] = 90.0  # invalid first try
            return json.dumps(bad, ensure_ascii=False)
        return json.dumps(_good_plan(), ensure_ascii=False)

    import core.composition_planner as cp
    orig = cp.__dict__.get("generate_music_brief")

    # inject brief by patching music_brief module function
    import core.music_brief as mb
    real = mb.generate_music_brief
    mb.generate_music_brief = lambda path, **kw: dict(_BRIEF)
    try:
        result = generate_composition_plan("fake.mp3", "deepseek", 9, chat_fn=fake_chat)
    finally:
        mb.generate_music_brief = real
    assert len(calls) == 2  # one revision
    assert "上一版输出的问题" in calls[1]
    assert result["legacy"]["segment_roles"]["S01"]["role"]
    assert result["plan"]["segments"][-1]["end_s"] == 68.0


def test_parse_extracts_json_from_noise():
    text = "好的，这是计划：\n```json\n" + json.dumps(_good_plan()) + "\n```\n以上。"
    assert parse_planner_json(text) is not None
    assert parse_planner_json("没有 json") is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASSED: {name}")
    print("\nALL COMPOSITION PLANNER TESTS PASSED")
