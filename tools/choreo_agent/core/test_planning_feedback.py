"""planning pass 两级 prompt 必须携带导演反馈/人类偏好（曾被静默丢弃的产品 bug）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.planning_pass import build_coding_prompt, build_planning_prompt

PREV = [[100 + 60 * i, 100, 150] for i in range(7)]


def test_planning_prompts_carry_feedback_and_preferences():
    kwargs = dict(
        feedback="导演要求：第二个 keyframe 放慢",
        human_preferences="偏好：暖色系收尾",
    )
    plan_prompt = build_planning_prompt(
        "S03", 23.0, 31.0, "卡农变奏", PREV, drone_count=7, **kwargs
    )
    assert "第二个 keyframe 放慢" in plan_prompt
    assert "导演/上轮反馈" in plan_prompt
    assert "暖色系收尾" in plan_prompt and "人类偏好记忆" in plan_prompt
    # 输出纪律仍是最后一行（mimo 纪律）
    assert plan_prompt.rstrip().endswith("只输出 JSON，不解释。")

    code_prompt = build_coding_prompt("预算表占位", "S03", 23.0, 31.0, drone_count=7, **kwargs)
    assert "第二个 keyframe 放慢" in code_prompt
    assert "暖色系收尾" in code_prompt
    assert code_prompt.rstrip().endswith("不要 marker/import/def/解释。")
    print("PASSED: planning prompts carry feedback and preferences")


def test_planning_prompts_clean_when_no_feedback():
    plan_prompt = build_planning_prompt("S03", 23.0, 31.0, "卡农变奏", PREV, drone_count=7)
    assert "导演/上轮反馈" not in plan_prompt
    assert "人类偏好记忆" not in plan_prompt
    code_prompt = build_coding_prompt("预算表占位", "S03", 23.0, 31.0, drone_count=7)
    assert "导演/上轮反馈" not in code_prompt
    print("PASSED: planning prompts unchanged when no feedback")


if __name__ == "__main__":
    test_planning_prompts_carry_feedback_and_preferences()
    test_planning_prompts_clean_when_no_feedback()
    print("\nALL PLANNING FEEDBACK TESTS PASSED")
