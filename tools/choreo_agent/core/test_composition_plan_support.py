"""Composition-plan prompt contract tests for choreo_agent."""

from pathlib import Path

from core.planning_pass import build_planning_prompt
from core.prompt_builder import build_segment_prompt
from core.state import ProjectState, SegmentState


def _sample_plan():
    return {
        "theme": "庄严推进到明亮高潮",
        "dramaturgy": "S01 引入，S02 展开，S03 变奏，S04 蓄力，S05 高潮，S06 收束",
        "movement_motifs": ["斜线推进", "分组卡农", "高低三层"],
        "light_arc": "蓝白到暖金",
        "continuity_rules": ["每段复现一个母题并变奏", "不要连续重复退化队形"],
        "segment_roles": {
            "S03": {
                "role": "卡农变奏：分组先后启动，形成交错呼应。",
                "motifs": ["分组卡农", "交叉换位"],
                "relationship": "承接 S02，为 S04 铺垫。",
                "avoid": ["全队同步单调平移", "无高度差"],
            }
        },
    }


def test_state_persists_composition_plan(tmp_path: Path):
    state = ProjectState(
        name="composition",
        composition_plan=_sample_plan(),
        segments=[SegmentState(id="S01", start_time=4, end_time=13)],
    )

    state.save(tmp_path)
    loaded = ProjectState.load(tmp_path)

    assert loaded.composition_plan["theme"] == "庄严推进到明亮高潮"
    assert loaded.composition_plan["segment_roles"]["S03"]["role"].startswith("卡农变奏")


def test_segment_prompt_includes_composition_plan_in_user_not_system():
    _system, user = build_segment_prompt(
        "S03",
        23,
        31,
        "test intent",
        [[100 + i * 30, 120 + i * 20, 140 + i * 5] for i in range(7)],
        "",
        drone_count=7,
        composition_plan=_sample_plan(),
    )

    assert "## 全局章法计划" in user
    assert "当前段角色：卡农变奏" in user
    assert "当前段要使用/变奏的母题：分组卡农; 交叉换位" in user
    assert "当前段避免：全队同步单调平移; 无高度差" in user


def test_composition_plan_does_not_change_system_prompt_cache_block():
    system_without, _ = build_segment_prompt("S03", 23, 31, "x", None, "", drone_count=7)
    system_with, _ = build_segment_prompt(
        "S03",
        23,
        31,
        "x",
        None,
        "",
        drone_count=7,
        composition_plan=_sample_plan(),
    )

    assert system_with == system_without


def test_planning_prompt_includes_current_segment_role():
    prompt = build_planning_prompt(
        "S03",
        23,
        31,
        "test intent",
        [[100 + i * 30, 120 + i * 20, 140 + i * 5] for i in range(7)],
        drone_count=7,
        composition_plan=_sample_plan(),
    )

    from core.planning_pass import build_planning_system_prompt
    prompt = build_planning_system_prompt(7) + "\n" + prompt  # C14: 静态规则在 system
    assert "全局章法:" in prompt
    assert "current role: 卡农变奏" in prompt
    assert "current motifs: 分组卡农; 交叉换位" in prompt
    assert "章法约束" in prompt
