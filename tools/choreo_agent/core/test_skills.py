"""Skill registry tests — Stage 1 internal skillization.

Enforce that the registry (core/skills.py) is the single source of truth: every
documented skill maps to a real function.py primitive, every composite composes
only known primitives, the generated SKILL.md is in sync, and the prompts carry
the skill guidance.
"""

import importlib.util
from pathlib import Path

import core.skills as sk
from core.prompt_builder import build_segment_prompt
from core.composition_planner import build_planner_prompt

ROOT = Path(__file__).resolve().parents[1]

# The primitives the brief explicitly requires to be documented.
REQUIRED_PRIMITIVES = {
    "ripple_move", "follow_chain", "group_relay", "light_wave", "fade_group",
    "breathe_group", "flash_group", "spatial_ranks", "ripple_delays",
    "split_groups", "beat_ms",
}


def _function_all() -> set[str]:
    path = ROOT / "project_template" / "scripts" / "function.py"
    spec = importlib.util.spec_from_file_location("template_function_skills", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return set(module.__all__)


# ---------- registry ↔ function.py ----------

def test_primitive_functions_exist_in_function_all():
    allset = _function_all()
    missing = [s["function"] for s in sk.PRIMITIVE_SKILLS if s["function"] not in allset]
    assert not missing, f"primitive skills point at non-exported functions: {missing}"


def test_required_primitives_are_documented():
    documented = sk.primitive_functions()
    missing = REQUIRED_PRIMITIVES - documented
    assert not missing, f"brief-required primitives lack a skill card: {sorted(missing)}"


def test_composite_uses_are_known_primitives():
    known = sk.primitive_functions()
    for s in sk.COMPOSITE_SKILLS:
        unknown = [u for u in s["uses"] if u not in known]
        assert not unknown, f"composite {s['name']} uses unknown primitives: {unknown}"
        assert s["uses"], f"composite {s['name']} composes nothing"


# ---------- metadata shape ----------

def test_categories_and_roles_valid():
    required_fields_prim = {
        "name", "function", "category", "role_fit", "purpose", "when_to_use",
        "when_not", "key_params", "safety", "validation_risks", "example",
        "combines_with", "music_fit",
    }
    required_fields_comp = {
        "name", "uses", "category", "role_fit", "music_fit", "visual_effect",
        "constraints", "how_to_choose", "avoid_overuse", "example",
    }
    for s in sk.PRIMITIVE_SKILLS:
        assert required_fields_prim <= set(s), f"{s.get('name')} missing fields"
        assert s["category"] in sk.VALID_CATEGORIES, (s["name"], s["category"])
        assert s["role_fit"] and set(s["role_fit"]) <= sk.VALID_ROLES, (s["name"], s["role_fit"])
    for s in sk.COMPOSITE_SKILLS:
        assert required_fields_comp <= set(s), f"{s.get('name')} missing fields"
        assert s["category"] in sk.VALID_CATEGORIES, (s["name"], s["category"])
        assert s["role_fit"] and set(s["role_fit"]) <= sk.VALID_ROLES, (s["name"], s["role_fit"])


def test_skill_names_unique():
    names = [s["name"] for s in sk.PRIMITIVE_SKILLS] + [s["name"] for s in sk.COMPOSITE_SKILLS]
    dups = {n for n in names if names.count(n) > 1}
    assert not dups, f"duplicate skill names: {dups}"


def test_combines_with_references_real_skills():
    names = sk.all_skill_names()
    for s in sk.PRIMITIVE_SKILLS:
        bad = [c for c in s["combines_with"] if c not in names]
        assert not bad, f"{s['name']} combines_with unknown skills: {bad}"


_FORBIDDEN_IN_EXAMPLES = [
    r"^\s*import\s", r"\binittime\s*\(", r"\.move2\s*\(", r"\.VelXY\s*\(",
    r"\.VelZ\s*\(", r"\bgeo_wide_v\b", r"\bgeo_arrow\b", r"\bgeo_box\b",
    r"\bgeo_diagonal\b", r"\bgeo_wave\b", r"\bgeo_grid\b", r"\bjitter_points\b",
]


def test_examples_teach_no_forbidden_patterns():
    """Skill examples are templates the model imitates — they must not teach
    anything preflight/validator rejects (bare API, imports, retired geo_*)."""
    import re
    for s in sk.PRIMITIVE_SKILLS + sk.COMPOSITE_SKILLS:
        ex = s["example"]
        for pat in _FORBIDDEN_IN_EXAMPLES:
            assert not re.search(pat, ex, re.M), f"{s['name']} example teaches forbidden `{pat}`: {ex[:60]}"


def test_examples_demonstrate_their_skill():
    """Each primitive example must call its own function; each composite example
    must reference at least one primitive it claims to compose."""
    for s in sk.PRIMITIVE_SKILLS:
        assert s["function"] + "(" in s["example"], f"{s['name']} example doesn't call {s['function']}"
    for s in sk.COMPOSITE_SKILLS:
        assert any(u + "(" in s["example"] for u in s["uses"]), (
            f"composite {s['name']} example references none of its uses {s['uses']}"
        )


# ---------- SKILL.md ↔ registry ----------

def test_skill_doc_in_sync_with_registry():
    doc_path = ROOT / "SKILL.md"
    assert doc_path.exists(), "SKILL.md missing — generate it from core.skills.render_full_skill_doc()"
    on_disk = doc_path.read_text(encoding="utf-8")
    expected = sk.render_full_skill_doc()
    assert on_disk == expected, (
        "SKILL.md is stale. Regenerate:\n"
        "  python -c \"import core.skills as s, pathlib; "
        "pathlib.Path('SKILL.md').write_text(s.render_full_skill_doc())\""
    )


def test_every_skill_appears_in_doc():
    doc = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for s in sk.PRIMITIVE_SKILLS:
        assert s["name"] in doc and s["function"] in doc, f"{s['name']} not documented"
    for s in sk.COMPOSITE_SKILLS:
        assert s["name"] in doc, f"composite {s['name']} not documented"


# ---------- prompt-facing renderers ----------

def test_skill_menu_for_each_role_non_empty_and_known():
    known = sk.all_skill_names() | sk.primitive_functions()
    for role in sk.VALID_ROLES:
        menu = sk.skill_menu_for_role(role)
        assert menu and "本段技能候选" in menu, f"empty menu for {role}"
        # every token that looks like a skill name must be a registered skill/function
        for s in sk.COMPOSITE_SKILLS:
            if role in s["role_fit"]:
                assert s["name"] in menu, f"{s['name']} should appear in {role} menu"


def test_unknown_role_falls_back():
    assert "本段技能候选" in sk.skill_menu_for_role("not-a-role")


def test_role_class_for_segment():
    assert sk.role_class_for_segment("S05") == "climax"
    assert sk.role_class_for_segment("S06") == "closure"
    assert sk.role_class_for_segment("S01") == "opening"
    assert sk.role_class_for_segment("LAND") == "closure"
    assert sk.role_class_for_segment("S03") == "development"
    # plan-role keywords override the canonical default
    assert sk.role_class_for_segment("S03", plan_role="本段是全场高潮爆发") == "climax"
    assert sk.role_class_for_segment("S02", plan_role="安静留白悬停") == "calm"


def test_composite_catalog_lists_all_composites():
    block = sk.composite_catalog_block()
    for s in sk.COMPOSITE_SKILLS:
        assert s["name"] in block, f"{s['name']} missing from planner catalog"


# ---------- prompt integration ----------

def test_segment_prompt_injects_skill_menu():
    _sys, user = build_segment_prompt(
        "S05", 47.0, 59.0, "高潮爆发段", [[100, 100, 120]] * 9, "", drone_count=9,
    )
    assert "本段技能候选" in user
    assert "center-out-climax" in user  # climax composite surfaced for S05

    _s, land = build_segment_prompt(
        "LAND", 67.0, 72.0, "降落", [[100, 100, 120]] * 9, "", drone_count=9,
    )
    assert "本段技能候选" not in land, "LAND must not get a choreography skill menu"


def test_segment_prompt_includes_quality_budget():
    """S03-style long segments must be told the quality-gate minimums up front
    (the fix for the multi-round 'moves too small' grind)."""
    from core.validator import motion_quality_minimums

    _sys, user = build_segment_prompt(
        "S03", 24.1, 35.7, "仙鹤对鸣 能量降低", [[280, 280, 160]] * 9, "", drone_count=9,
    )
    assert "动作质量预算" in user
    mins = motion_quality_minimums(6.0, 9)
    assert f"{mins['min_moving']}/9" in user, "min_moving not surfaced"
    assert f"≥{mins['min_median_path_cm']:.0f}cm" in user, "median path target missing"
    # LAND has no choreography quality demand
    _s, land = build_segment_prompt(
        "LAND", 67.0, 72.0, "降落", [[280, 280, 160]] * 9, "", drone_count=9,
    )
    assert "动作质量预算" not in land


def test_motion_quality_minimums_matches_gate():
    """motion_quality_minimums is the single source of truth for the gate."""
    from core.validator import motion_quality_minimums, _check_motion_quality

    mins = motion_quality_minimums(5.4, 9)
    # a quality dict that is exactly at the floors must produce no errors
    at_floor = {
        "drone_count": 9,
        "moving_drones": mins["min_moving"],
        "median_path_cm": mins["min_median_path_cm"],
        "median_excursion_cm": mins["min_median_excursion_cm"],
        "max_excursion_cm": mins["min_max_excursion_cm"],
    }
    assert _check_motion_quality((24.1, 29.5), at_floor) == []
    # just below the path floor must fail
    below = dict(at_floor, median_path_cm=mins["min_median_path_cm"] - 1)
    errs = _check_motion_quality((24.1, 29.5), below)
    assert any("中位路径" in e for e in errs)


def test_planner_prompt_injects_catalog():
    brief = {
        "music_source": "x.mp3", "duration_s": 70.0, "tempo_bpm": 120.0,
        "beat_interval_s": 0.5, "hard_cues": [4.0, 20.0],
        "sections": [{"time_range": [0, 20], "energy": 0.5, "energy_label": "mid", "onset_per_s": 2}],
    }
    prompt = build_planner_prompt(brief, 9)
    assert "组合技能目录" in prompt
    assert "ending-flash-fade-closure" in prompt


# ---------- Stage 4: user-defined skills ----------

def _valid_user_composite(name="my-test-skill"):
    return {
        "name": name,
        "uses": ["ripple_move", "light_wave"],
        "category": "motion",
        "role_fit": ["expand"],
        "music_fit": "测试",
        "visual_effect": "测试效果",
        "constraints": "测试约束",
        "how_to_choose": "测试",
        "avoid_overuse": "测试",
        "example": "prev = ripple_move(drones, best_assign(prev, geo), 2600, ripple_delays(prev), colors=palette)",
    }


def test_register_valid_user_composite_appears_in_menu():
    try:
        errs = sk.register_user_skills({"composites": [_valid_user_composite()]})
        assert errs == [], errs
        assert "my-test-skill" in sk.all_skill_names()
        assert "my-test-skill" in sk.composite_catalog_block()
        assert "my-test-skill" in sk.skill_menu_for_role("expand")
    finally:
        sk.clear_user_skills()


def test_reject_unknown_primitive_in_user_composite():
    try:
        bad = _valid_user_composite()
        bad["uses"] = ["ripple_move", "not_a_real_function"]
        errs = sk.register_user_skills({"composites": [bad]})
        assert errs and any("未知原语" in e for e in errs)
        assert "my-test-skill" not in sk.all_skill_names(), "atomic: nothing registers on error"
    finally:
        sk.clear_user_skills()


def test_reject_user_primitive_with_unknown_function():
    try:
        bad_prim = {
            "name": "fake-prim", "function": "totally_made_up", "category": "motion",
            "role_fit": ["any"], "purpose": "x", "when_to_use": "x", "when_not": "x",
            "key_params": "x", "safety": "x", "validation_risks": "x", "example": "x",
            "combines_with": [], "music_fit": "x",
        }
        errs = sk.register_user_skills({"primitives": [bad_prim]})
        assert errs and any("不能引入新执行函数" in e or "__all__" in e for e in errs)
    finally:
        sk.clear_user_skills()


def test_reject_bad_category_and_role_and_missing_field():
    try:
        bad = _valid_user_composite()
        bad["category"] = "teleport"
        bad["role_fit"] = ["nonsense"]
        del bad["music_fit"]
        errs = sk.register_user_skills({"composites": [bad]})
        assert any("category" in e for e in errs)
        assert any("role_fit" in e for e in errs)
        assert any("缺字段" in e for e in errs)
    finally:
        sk.clear_user_skills()


def test_reject_duplicate_name():
    try:
        dup = _valid_user_composite(name="center-out-climax")  # collides with built-in
        errs = sk.register_user_skills({"composites": [dup]})
        assert any("重复" in e for e in errs)
    finally:
        sk.clear_user_skills()


def test_load_example_file_validates():
    try:
        errs = sk.load_user_skills(ROOT / "user_skills.example.json")
        assert errs == [], f"shipped example must be valid: {errs}"
        assert "my-spiral-bloom" in sk.all_skill_names()
    finally:
        sk.clear_user_skills()
    # missing file is not an error
    assert sk.load_user_skills(ROOT / "does_not_exist.json") == []


def test_user_skills_do_not_leak_into_default_cards():
    """With no user skills registered, the generated CARD section has no user
    skill (the snapshot test depends on this isolation). Note 'my-spiral-bloom'
    still appears in the footer's documentation example — that's expected."""
    try:
        sk.register_user_skills({"composites": [_valid_user_composite()]})
        assert "my-test-skill" in sk.render_skill_markdown(), "registered → in cards"
    finally:
        sk.clear_user_skills()
    assert "my-test-skill" not in sk.render_skill_markdown(), "cleared → gone from cards"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASSED: {name}")
    print("\nALL SKILL TESTS PASSED")
