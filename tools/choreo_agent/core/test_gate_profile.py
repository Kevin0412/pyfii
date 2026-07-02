"""gate_profile 行为：审美门仅在 full 下阻断；物理安全/演出完整性门两种 profile 都硬。"""

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.preflight import preflight_check
from core.validator import ValidationResult

TEMPLATE = Path(__file__).resolve().parent.parent / "project_template"


def _passing_result(**overrides) -> ValidationResult:
    """构造一个全门通过的 continuity 结果，再按需拨坏个别门。"""
    result = ValidationResult(
        compile_ok=True,
        run_ok=True,
        read_fii_ok=True,
        distance_warnings=0,
        action_warnings=0,
        dense_min_distance_cm=63.0,
        continuity_required=True,
        hover_check_ok=True,
        expected_drone_count=7,
    )
    result.exit_state = [[100 + 60 * i, 100, 150] for i in range(7)]
    for key, value in overrides.items():
        setattr(result, key, value)
    return result


def test_aesthetic_gates_blocked_only_under_full_profile():
    for field in ("composition_ok", "motion_quality_ok"):
        full = _passing_result(**{field: False, "gate_profile": "full"})
        safety = _passing_result(**{field: False, "gate_profile": "safety"})
        assert not full.passed, f"{field}=False 应在 full 下阻断"
        assert safety.passed, f"{field}=False 不应在 safety 下阻断"
        assert full.passed_safety and safety.passed_safety
    print("PASSED: aesthetic gates block only under full profile")


def test_tier0_safety_gates_hard_in_both_profiles():
    for profile in ("full", "safety"):
        collision = _passing_result(dense_min_distance_cm=45.0, gate_profile=profile)
        assert not collision.passed, f"{profile}: 碰撞距离必须阻断"
        assert not collision.passed_safety
    print("PASSED: tier-0 collision gate hard in both profiles")


def test_tier1_integrity_gates_hard_in_both_profiles():
    for profile in ("full", "safety"):
        hover = _passing_result(hover_segments=[(10.0, 14.0)], gate_profile=profile)
        assert not hover.passed, f"{profile}: 整体悬停必须阻断"
        window = _passing_result(window_fill_ok=False, gate_profile=profile)
        assert not window.passed, f"{profile}: 窗口填充必须阻断"
    print("PASSED: tier-1 integrity gates hard in both profiles")


GEO_TEMPLATE_CODE = """\
prev = [(d.x, d.y, d.z) for d in drones]
geo = geo_arrow(prev)
flying_ms = 3000
for i, drone in enumerate(drones):
    move2(drone, (100 + 60 * i, 120, 150), flying_ms)
    apply_light(drone, "#ffaa00", 4)
    drone.delay(2700)
prev = [(d.x, d.y, d.z) for d in drones]
"""


def test_preflight_geo_template_ban_is_style_under_safety():
    full = preflight_check(GEO_TEMPLATE_CODE, segment_id="S03", drone_count=7)
    assert not full, "full profile 下 geo 模板必须阻断"
    assert any("geo_arrow" in e for e in full.errors)

    safety = preflight_check(
        GEO_TEMPLATE_CODE, segment_id="S03", drone_count=7, gate_profile="safety"
    )
    assert safety, f"safety profile 下 geo 模板不应阻断: {safety.errors}"
    assert any("geo_arrow" in e for e in safety.style_errors)
    print("PASSED: geo template ban is style-only under safety profile")


def test_preflight_jitter_points_hard_in_both_profiles():
    code = GEO_TEMPLATE_CODE.replace("geo_arrow(prev)", "jitter_points(prev)")
    for profile in ("full", "safety"):
        pf = preflight_check(code, segment_id="S03", drone_count=7, gate_profile=profile)
        assert not pf, f"{profile}: jitter_points 绕过安全校验，必须阻断"
    print("PASSED: jitter_points ban hard in both profiles")


def test_session_profile_normalization():
    from core import Session

    tmp = Path(tempfile.mkdtemp(prefix="gate_profile_"))
    project = tmp / "proj"
    try:
        shutil.copytree(TEMPLATE, project)
        assert Session(project).gate_profile == "full"
        assert Session(project, gate_profile="safety").gate_profile == "safety"
        assert Session(project, gate_profile="weird").gate_profile == "full"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASSED: session normalizes gate_profile")


if __name__ == "__main__":
    test_aesthetic_gates_blocked_only_under_full_profile()
    test_tier0_safety_gates_hard_in_both_profiles()
    test_tier1_integrity_gates_hard_in_both_profiles()
    test_preflight_geo_template_ban_is_style_under_safety()
    test_preflight_jitter_points_hard_in_both_profiles()
    test_session_profile_normalization()
    print("\nALL GATE PROFILE TESTS PASSED")
