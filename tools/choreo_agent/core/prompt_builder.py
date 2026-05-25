"""Prompt Builder — 组装 LLM prompt"""
from pathlib import Path

CONTEXT_DIR = Path(__file__).resolve().parent.parent / "context_packs"

ALL_PACKS = [
    "pyfii_api_minimal.md",
    "pyfii_coding_rules.md",
    "pyfii_segment_protocol.md",
    "pyfii_anti_patterns.md",
    "pyfii_best_assign.md",
    "pyfii_light_patterns.md",
    "pyfii_validation_rules.md",
    "agent_coding_style.md",
]


def load_context_pack(name: str) -> str:
    return (CONTEXT_DIR / name).read_text(encoding="utf-8")


def build_system_prompt() -> str:
    return "\n\n".join(load_context_pack(p) for p in ALL_PACKS)


def _requires_continuity_gate(segment_id: str, intent: str) -> bool:
    text = f"{segment_id} {intent}".lower()
    excluded = ("takeoff", "landing", "land", "起飞", "降落")
    return not any(word in text for word in excluded)


def build_segment_prompt(
    segment_id: str,
    start_time: float,
    end_time: float,
    music_cue: dict,
    intent: str,
    prev_state: list,
    design_py: str = "",
    feedback: str = "",
) -> tuple[str, str]:
    system = build_system_prompt()

    user = f"""生成 Pyfii 编舞段 {segment_id}。

## 音乐
- 时间: {start_time}s - {end_time}s ({end_time - start_time:.0f}s)
- 能量: {music_cue.get('energy', 'unknown')}
- 情绪: {music_cue.get('emotion', 'unknown')}

## 设计意图
{intent}

## 上一段出口
```python
prev = {prev_state}
```

"""

    if design_py:
        user += f"""## 当前 design.py（locked 段参考，不可修改）
```python
{design_py}
```

"""

    user += """## 要求
- 不要输出 marker 行（START/END），只输出段内部的 Python 代码
- 如果使用 Markdown，只能放一个 python 代码块；不要解释设计过程
- 段代码必须在 marker 之间（见 segment_protocol）
"""

    if _requires_continuity_gate(segment_id, intent):
        user += f"""- 运动包络：本段 {start_time:.2f}-{end_time:.2f}s，明显运动必须在 {start_time + 1:.2f}s 前开始，并在 {end_time - 1:.2f}s 后、{end_time:.2f}s 前完成收束
- 动作必须连贯：当前段任意整体悬停不得超过 1 秒；不能用连续 delay/light 空转填满段落
- 如果需要停顿呼吸，压到 0.8 秒以内，并让分组错峰或高度轻微变化承接下一动作
"""
    else:
        user += "- 起飞和降落段不计入编舞连贯性硬门；仍必须安全、平滑、执行完成\n"

    user += """- 几何内部点间距 > 51cm
- 安全优先于视觉复杂度；如果复杂换位有碰撞风险，使用扇区保持、排队错峰和更少几何
- best_assign 结果硬编码为 perm = (...)
- 生成前先算飞行时间，确保 light + delay 够
- 不要只做一个 move2 —— 可以多几何、条件分支、相对移动、排队错峰
- VelXY 和 VelZ 值必须一致
"""

    if feedback:
        user += f"\n\n## 人类反馈\n{feedback}"



    return system, user
