"""指令预检与冲突解释的离线验证（C11a）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.directive_advisor import (
    explain_conflict,
    extract_coordinates,
    precheck_directive,
)
from core.validator import ValidationResult

PREV = [[100 + 60 * i, 100, 150] for i in range(7)]


def test_precheck_bounds_and_spacing():
    # 越界
    warnings = precheck_directive("让 3 号机停到 (600, 100, 180)", PREV, 7)
    assert any("越界" in w for w in warnings), warnings
    warnings = precheck_directive("让 3 号机停到 (140, 140, 60)", PREV, 7)
    assert any("Z 越界" in w for w in warnings), warnings

    # 与他机入口位置过近（d0 在 (100,100)；目标 (110,110) XY 距离 ~14cm）
    warnings = precheck_directive("让 3 号机停到 (110, 110, 180)", PREV, 7)
    assert any("d0" in w and "必撞" in w for w in warnings), warnings

    # 点名机自己不算冲突（d3 在 (280,100)，目标就在它附近）
    warnings = precheck_directive("让 3 号机停到 (280, 110, 180)", PREV, 7)
    assert not any("d3" in w for w in warnings), warnings

    # 干净指令无预警
    assert precheck_directive("让 3 号机停到 (450, 400, 180)", PREV, 7) == []
    # 无坐标的指令直接跳过
    assert precheck_directive("灯光改成蓝色", PREV, 7) == []
    print("PASSED: precheck bounds and spacing")


def test_precheck_reachability():
    warnings = precheck_directive(
        "让 0 号机停到 (540, 520, 240)", PREV, 7, window_s=4.0
    )
    assert any("不可达" in w or "勉强" in w for w in warnings), warnings
    print("PASSED: precheck reachability budget")


def _base_result(**overrides) -> ValidationResult:
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


def test_explain_collision_names_directed_drone_and_tradeoffs():
    failing = _base_result(
        distance_warnings=1,
        dense_min_distance_cm=32.0,
        collision_intervals=[{
            "start_s": 21.0, "end_s": 21.4, "min_time_s": 21.2,
            "min_distance_cm": 32.0, "pair": (3, 5),
        }],
    )
    text = explain_conflict(failing, "让 drones[3] 停到 (140,140,180)")
    assert "d3 与 d5" in text and "32.0cm" in text
    assert "指令点名的 [3] 号机" in text
    assert "取舍选项" in text and "让位" in text
    print("PASSED: collision explanation with trade-offs")


def test_explain_action_and_integrity_paths():
    slow = _base_result(action_warnings=2, action_details=["d2 未完成", "d4 未完成"])
    text = explain_conflict(slow, "把动作放大")
    assert "时间预算" in text and "飞不到" in text

    hovering = _base_result(hover_segments=[(6.0, 11.0)])
    text = explain_conflict(hovering, "全队定住呼吸")
    assert "演出完整性" in text and "拍板" in text

    passed = _base_result()
    assert explain_conflict(passed, "任何指令") == ""
    assert "格式/协议" in explain_conflict(None, "任何指令")
    print("PASSED: action and integrity explanations")


def test_extract_coordinates():
    coords = extract_coordinates("停到 (140, 140, 180)，然后 (300,200,150)")
    assert coords == [(140.0, 140.0, 180.0), (300.0, 200.0, 150.0)]
    print("PASSED: coordinate extraction")


if __name__ == "__main__":
    test_precheck_bounds_and_spacing()
    test_precheck_reachability()
    test_explain_collision_names_directed_drone_and_tradeoffs()
    test_explain_action_and_integrity_paths()
    test_extract_coordinates()
    print("\nALL DIRECTIVE ADVISOR TESTS PASSED")
