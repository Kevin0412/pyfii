"""Prompt 字节恒等快照 — 纯重构的验证基石（P1 协议）。

固定输入下，全部 prompt 构建函数的输出必须与提交在库里的 fixture 字节相等。
作用：
1. 证明"字面量→常量/f-string 插值"类重构没有改变模型看到的任何字节
   （同时证明前缀缓存未被破坏）；
2. 判定规则：本测试变红 = 不是纯重构 → 按 STABILITY_TEST_PLAN 跑双模型矩阵。

fixture 重生成（仅在**有意的** prompt 变更后、跑完矩阵才允许）：
    conda run -n pyfii python core/test_prompt_snapshot.py --regen
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "prompt_snapshot.json"

PREV7 = [[100 + 60 * i, 100 + 10 * i, 150] for i in range(7)]


def _template_plan() -> dict:
    state = json.loads(
        (Path(__file__).resolve().parent.parent / "project_template" / "state.json")
        .read_text(encoding="utf-8")
    )
    return state["composition_plan"]


def build_all_prompts() -> dict[str, str]:
    """固定输入的全套 prompt（新增 prompt 面时在此登记）。"""
    from core.planning_pass import (
        build_coding_prompt,
        build_coding_system_prompt,
        build_planning_prompt,
        build_planning_system_prompt,
    )
    from core.prompt_builder import build_segment_prompt, build_system_prompt

    plan = _template_plan()
    prompts: dict[str, str] = {}

    prompts["system_direct"] = build_system_prompt(7)
    prompts["planning_system"] = build_planning_system_prompt(7)
    prompts["coding_system"] = build_coding_system_prompt(7)

    sys_s01, user_s01 = build_segment_prompt(
        "S01", 4.0, 13.0, "开场", None, "", drone_count=7,
        composition_plan=plan, human_preferences="",
    )
    prompts["segment_S01_system"] = sys_s01
    prompts["segment_S01_user"] = user_s01

    _sys, user_s02 = build_segment_prompt(
        "S02", 13.0, 23.0, "第一次展开", PREV7, "导演反馈：更开阔一点", drone_count=7,
        composition_plan=plan, human_preferences="偏好：暖色收尾",
    )
    prompts["segment_S02_user"] = user_s02

    _sys, user_land = build_segment_prompt(
        "LAND", 63.0, 68.0, "", PREV7, "", drone_count=7,
        composition_plan=plan, human_preferences="",
    )
    prompts["segment_LAND_user"] = user_land

    prompts["planning_S02_user"] = build_planning_prompt(
        "S02", 13.0, 23.0, "第一次展开", PREV7, drone_count=7,
        composition_plan=plan, music_brief=None,
        feedback="导演反馈：更开阔一点", human_preferences="偏好：暖色收尾",
    )
    prompts["coding_S02_user"] = build_coding_prompt(
        "预算表占位（固定文本）", "S02", 13.0, 23.0, drone_count=7,
        composition_plan=plan, feedback="", human_preferences="",
    )
    return prompts


def test_prompt_bytes_identical_to_fixture():
    assert FIXTURE.exists(), (
        "缺少 prompt 快照 fixture — 运行 `python core/test_prompt_snapshot.py --regen` 生成"
    )
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    current = build_all_prompts()
    assert set(current) == set(fixture["prompts"]), (
        f"prompt 面变化: {sorted(set(current) ^ set(fixture['prompts']))}"
    )
    for name, text in current.items():
        expected = fixture["prompts"][name]
        if text != expected:
            got = hashlib.sha256(text.encode()).hexdigest()[:12]
            want = hashlib.sha256(expected.encode()).hexdigest()[:12]
            # 找第一个差异位置帮助定位
            pos = next(
                (i for i, (a, b) in enumerate(zip(expected, text)) if a != b),
                min(len(expected), len(text)),
            )
            raise AssertionError(
                f"prompt '{name}' 字节漂移 (sha {want} -> {got})，首个差异 @{pos}:\n"
                f"  期望: …{expected[max(0, pos-40):pos+40]!r}…\n"
                f"  实际: …{text[max(0, pos-40):pos+40]!r}…\n"
                "纯重构不允许任何字节变化；有意变更请先跑双模型矩阵再 --regen。"
            )
    print("PASSED: prompt bytes identical to fixture")


def _regen() -> None:
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    prompts = build_all_prompts()
    FIXTURE.write_text(
        json.dumps({"prompts": prompts}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    total = sum(len(v) for v in prompts.values())
    print(f"fixture regenerated: {len(prompts)} prompts, {total} chars -> {FIXTURE}")


if __name__ == "__main__":
    if "--regen" in sys.argv:
        _regen()
    else:
        test_prompt_bytes_identical_to_fixture()
        print("\nALL PROMPT SNAPSHOT TESTS PASSED")
