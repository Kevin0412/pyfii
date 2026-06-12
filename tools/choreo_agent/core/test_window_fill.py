"""窗口填充硬门测试：欠填段不得锁定（欠填会把后续段推离音乐 cue）。

背景案例：motif 首航 S01 在 4.0-12.5s 窗口里只编排到 9.0s 就锁定，
S02 实际播放在 9.0-14.7s 却按 12.5-19.0s 评审，15 轮全部死于
"有效群体运动过短"——错误归因到无辜段。
"""

import shutil
import tempfile
from pathlib import Path

from core.validator import (
    SEGMENT_FILL_TOLERANCE_S,
    SEGMENT_OVERFLOW_TOLERANCE_S,
    ValidationResult,
    _check_window_fill,
    _parse_segment_cursors,
)

TEMPLATE = Path(__file__).resolve().parents[1] / "project_template"


def test_parse_segment_cursors():
    output = """
7d F400 14.7s XY(475,415) minD=51.2cm
SEGCURSOR S01 9000
  SEGCURSOR S02 14720
SEGCURSOR LAND 73000
dist:0 act:0
junk SEGCURSOR S03 not-a-number
"""
    cursors = _parse_segment_cursors(output)
    assert cursors == {"S01": 9.0, "S02": 14.72, "LAND": 73.0}


def test_check_window_fill_underfill_and_overflow():
    window = (4.0, 12.5)
    errors = _check_window_fill(window, "S01", 9.0)
    assert len(errors) == 1
    assert "段未填满窗口" in errors[0] and "9.00s" in errors[0] and "12.50s" in errors[0]
    assert "3.5s" in errors[0], errors[0]

    over = _check_window_fill(window, "S01", 12.5 + SEGMENT_OVERFLOW_TOLERANCE_S + 0.6)
    assert len(over) == 1 and "段溢出窗口" in over[0]

    # 容差内通过；旧模板无标记不阻塞
    assert _check_window_fill(window, "S01", 12.5 - SEGMENT_FILL_TOLERANCE_S + 0.1) == []
    assert _check_window_fill(window, "S01", 12.7) == []
    assert _check_window_fill(window, "S01", None) == []


def test_window_fill_gates_passed():
    result = ValidationResult()
    result.compile_ok = result.run_ok = result.read_fii_ok = True
    result.distance_warnings = 0
    result.action_warnings = 0
    result.dense_min_distance_cm = 90.0
    result.code_quality_ok = True
    result.hover_check_ok = True
    result.continuity_required = True
    result.expected_drone_count = 2
    result.exit_state = [[100, 100, 120], [300, 300, 120]]
    assert result.passed, "基线应通过"

    result.window_fill_ok = False
    result.window_fill_errors = ["段未填满窗口：S01 ..."]
    assert not result.passed, "欠填段必须挡住锁定"
    feedback = result.repair_feedback()
    assert "窗口填充失败" in feedback and "ripple_move=max(delays)+flying_ms" in feedback


def test_template_main_flow_prints_cursors():
    content = (TEMPLATE / "scripts" / "design.py").read_text(encoding="utf-8")
    assert "def _segcursor(" in content
    for seg in ("S01", "S02", "S03", "S04", "S05", "S06", "LAND"):
        assert f'_segcursor("{seg}")' in content, f"模板缺 {seg} 游标标记"


def test_appended_segment_gets_cursor_marker():
    from core.session import Session
    from core.state import SegmentState

    tmp = Path(tempfile.mkdtemp(prefix="fill_test_"))
    project = tmp / "proj"
    shutil.copytree(TEMPLATE, project)
    try:
        session = Session(project)
        segment = SegmentState(id="S07", start_time=58.0, end_time=64.0, locked=False)
        assert session._insert_design_segment_before_land(segment)
        content = (project / "scripts" / "design.py").read_text(encoding="utf-8")
        assert 's07(drones); _segcursor("S07")' in content
        assert content.index('_segcursor("S07")') < content.index("\nland(drones)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASSED: {name}")
    print("\nALL WINDOW FILL TESTS PASSED")
