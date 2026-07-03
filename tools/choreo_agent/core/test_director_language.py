"""导演方位/灯光语言 grounding 的离线验证。"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.director_language import (
    format_directive_checklist,
    ground_directive,
    mentioned_drones,
    needs_grounding,
    needs_light_grounding,
    needs_spatial_grounding,
)

POSITIONS = [[100 + 60 * i, 100, 150] for i in range(7)]


def test_grounding_triggers_on_relative_direction_words():
    assert needs_spatial_grounding("3 号机再往左一点")
    assert needs_spatial_grounding("把 5 号机移到场地中间")
    assert needs_spatial_grounding("2 号机高一点")
    # auto 测试台的段反馈术语不能误触发
    assert not needs_grounding("保持高度层，动作贴满整个段窗口，不要原地硬等")
    assert not needs_grounding("继续修复 validator 反馈，目标是本段 passed=True")
    print("PASSED: spatial grounding trigger rules")


def test_grounding_triggers_on_complex_lighting_words():
    assert needs_light_grounding("从左到右依次呈现彩虹色并明暗渐变")
    assert needs_light_grounding("五彩斑斓的黑")
    assert needs_light_grounding("全体同步爆闪两次再渐暗")
    assert not needs_light_grounding("换一种颜色")
    print("PASSED: lighting grounding trigger rules")


def test_ground_directive_appends_legends_and_positions():
    text = ground_directive("3 号机往左一点", POSITIONS)
    assert "方位词换算" in text and "左/右 = x 减/增" in text
    assert "d3=(280,100,150)" in text
    assert "灯光描述换算" not in text  # 纯方位不带灯光图例

    text = ground_directive("从左到右依次呈现彩虹色并明暗渐变", POSITIONS)
    assert "灯光描述换算" in text and "依次" in text
    assert "方位词换算" not in text  # "从左到右"是灯光空间顺序，不含相对方位短语? 若含则两图例都可

    text = ground_directive("把 3 号机往左一点，然后做彩虹渐变", POSITIONS)
    assert "方位词换算" in text and "灯光描述换算" in text

    plain = "第二个 keyframe 放慢，收在暖白"
    assert ground_directive(plain, POSITIONS) == plain
    print("PASSED: ground_directive legends and passthrough")


def test_session_entry_grounds_spatial_feedback():
    """REPL/TUI/pipeline 共用的 session 入口应自动 grounding。"""
    import json
    import shutil
    import tempfile

    from core import Session
    from core.llm_client import LlmResponse

    template = Path(__file__).resolve().parent.parent / "project_template"
    tmp = Path(tempfile.mkdtemp(prefix="ground_test_"))
    project = tmp / "proj"
    shutil.copytree(template, project)
    captured = []

    def fake_chat(system, user, **_kwargs):
        captured.append(user)
        return LlmResponse(text="不是代码", model="mock")

    try:
        with patch("core.session.chat", side_effect=fake_chat):
            session = Session(project, gate_profile="safety")
            session.generate_until_safe_with_llm(
                provider="mock", feedback="3 号机往左一点", max_attempts=1,
            )
        assert captured and any("方位词换算" in p for p in captured), (
            "spatial feedback was not grounded at session entry"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASSED: session entry grounds spatial feedback")


def test_directive_checklist_formatting():
    single = format_directive_checklist(["只有一条"])
    assert single == "只有一条"
    multi = format_directive_checklist(["位置指令内容", "灯光指令内容"])
    assert "共 2 条" in multi and "1. 位置指令内容" in multi and "2. 灯光指令内容" in multi
    assert "逐条对照自查" in multi
    print("PASSED: directive checklist formatting")


def test_mentioned_drones():
    assert mentioned_drones("让 drones[3] 和 5 号机靠近") == [3, 5]
    assert mentioned_drones("全体向左") == []
    print("PASSED: mentioned drones extraction")


if __name__ == "__main__":
    test_grounding_triggers_on_relative_direction_words()
    test_grounding_triggers_on_complex_lighting_words()
    test_ground_directive_appends_legends_and_positions()
    test_session_entry_grounds_spatial_feedback()
    test_directive_checklist_formatting()
    test_mentioned_drones()
    print("\nALL DIRECTOR LANGUAGE TESTS PASSED")
