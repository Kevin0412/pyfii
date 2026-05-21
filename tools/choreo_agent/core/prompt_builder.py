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
]


def load_context_pack(name: str) -> str:
    return (CONTEXT_DIR / name).read_text(encoding="utf-8")


def build_system_prompt() -> str:
    return "\n\n".join(load_context_pack(p) for p in ALL_PACKS)


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
- 段代码必须在 marker 之间（见 segment_protocol）
- 几何内部点间距 > 51cm
- best_assign 结果硬编码为 perm = (...)
- 生成前先算飞行时间，确保 light + delay 够
- 不要只做一个 move2 —— 可以多几何、条件分支、相对移动、排队错峰
- VelXY 和 VelZ 值必须一致
"""

    if feedback:
        user += f"\n\n## 人类反馈\n{feedback}"

    return system, user
    segment_id: str,
    start_time: float,
    end_time: float,
    music_cue: dict,
    intent: str,
    prev_state: list,
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

## 要求
- 段代码必须在 marker 之间（见 segment_protocol）
- 几何内部点间距 > 51cm
- best_assign 结果硬编码为 perm = (...)
- 生成前先算飞行时间，确保 light + delay 够
- 不要只做一个 move2 —— 可以多几何、条件分支、相对移动、排队错峰
- VelXY 和 VelZ 值必须一致
"""

    if feedback:
        user += f"\n\n## 人类反馈\n{feedback}"

    return system, user
