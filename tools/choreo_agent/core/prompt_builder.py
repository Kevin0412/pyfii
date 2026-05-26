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
    seg_id = segment_id.lower()
    text = intent.strip().lower()
    if seg_id in {"takeoff", "landing", "land"}:
        return False
    lifecycle_prefixes = ("起飞段", "降落段", "takeoff segment", "landing segment")
    if text.startswith(lifecycle_prefixes):
        return False
    return True


def _requires_takeoff_setup(segment_id: str, prev_state: list) -> bool:
    return segment_id.strip().lower() in {"s01", "seg01", "segment01", "1"} and not prev_state


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

## 当前段入口 / 上一段出口
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

    if _requires_takeoff_setup(segment_id, prev_state):
        user += f"""- 当前是首段：你必须在本段代码开头自己设计 7 架无人机的起飞布局 `start_positions`，设置 `drone.X/drone.x/drone.Y/drone.y`，并调用 `drone.takeoff(...)`
- 起飞布局和 S01 正式动作必须一起设计；不要假设 template 或 state.json 已经给定起飞点
- 起飞/起飞后等待不计入正式质量门，但正式编舞动作仍必须在 {start_time:.1f}s 后的质量窗口内满足本段运动包络、连续性和有效动作质量
- 起飞点必须安全分散、点间距充足，并服务于后续 S01 的大动作路线；不要把所有机堆在中心或窄车道
"""

    if _requires_continuity_gate(segment_id, intent):
        user += f"""- 运动包络：本段 {start_time:.2f}-{end_time:.2f}s，明显运动必须在 {start_time + 1:.2f}s 前开始，并在 {end_time - 1:.2f}s 后、{end_time:.2f}s 前完成收束
- 动作必须连贯：当前段任意整体悬停不得超过 1 秒；不能用连续 delay/light 空转填满段落
- 如果需要停顿呼吸，压到 0.8 秒以内，并让分组错峰或仍在执行的高度/弧线 keyframe 承接下一动作
- 时间线必须覆盖全段：PyFii 是每架机各自累计时间，不是 Python 循环全局时间；段内通常用一次 inittime(start)，然后按 move2 -> 短灯光/执行等待 -> move2 链式推进
- 每个 move2 后都要按 3D 距离和 VelXY/VelZ 计算飞行时间；后续 light+delay 是这次移动的执行预算，不是段尾填空
- 段尾收束必须是实际移动在最后 1 秒内仍在执行并完成，不能只用纯灯光/静止等待填满
- 禁止结构：全体同一 inittime -> 多个短 move2 很快完成 -> apply_light(ticks>=10)/长 delay 填尾
- 推荐结构：把 A/B/C 分组动作重叠排布；灯光脉冲默认 ticks<=6；如果某个 interval 过长，降低速度、增加中间 keyframe 或增加路径弧度，而不是补长 delay
- 对任何可能形成全局等待的区间，在 1 秒到达前安排真实路线移动；只改颜色不算运动
- 连贯不等于小抖动：多数无人机必须离开入口位置形成有效位移，正式段要有跨区域展开/收缩/交换；小幅 Z/XY 呼吸只能用作衔接，不能作为主体动作
"""
    else:
        user += "- 起飞和降落段不计入编舞连贯性硬门；仍必须安全、平滑、执行完成\n"

    user += """- 几何内部点间距 > 51cm
- 安全优先于视觉复杂度；如果复杂换位有碰撞风险，使用扇区保持、排队错峰和更少几何
- best_assign 结果硬编码为 perm = (...)
- 生成前先算每个 move2 的飞行时间，确保该移动后的 light + delay 执行预算够
- 不要只做一个 move2 —— 可以多几何、条件分支、相对移动、排队错峰
- VelXY 和 VelZ 值必须一致
"""

    if feedback:
        user += f"\n\n## 人类反馈\n{feedback}"



    return system, user
