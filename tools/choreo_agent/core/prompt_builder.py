"""Prompt Builder — 组装 LLM prompt"""
from pathlib import Path

try:
    from .motion_math import prompt_budget_table
    from .planning_tools import prompt_planning_tool_reference
except ImportError:  # allow running this module from tools/choreo_agent/core
    from motion_math import prompt_budget_table
    from planning_tools import prompt_planning_tool_reference

CONTEXT_DIR = Path(__file__).resolve().parent.parent / "context_packs"

ALL_PACKS = [
    "pyfii_api_minimal.md",
    "pyfii_coding_rules.md",
    "pyfii_segment_protocol.md",
    "pyfii_anti_patterns.md",
    "pyfii_best_assign.md",
    "pyfii_light_patterns.md",
    "pyfii_validation_rules.md",
    "pyfii_design_patterns.md",
    "agent_coding_style.md",
]


def load_context_pack(name: str) -> str:
    return (CONTEXT_DIR / name).read_text(encoding="utf-8")


def build_system_prompt() -> str:
    packs = [load_context_pack(p) for p in ALL_PACKS]
    packs.append(prompt_budget_table())
    packs.append(prompt_planning_tool_reference())
    return "\n\n".join(packs)


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


def _timing_budget_hint(start_time: float, end_time: float) -> str:
    move_start = start_time + 0.15
    finish_target = end_time - 0.35
    active_s = max(1.0, finish_target - move_start)
    weights = [0.22, 0.24, 0.26, 0.28]
    cue = move_start
    lines = [
        "## 本段时间预算参考",
        f"- 正式动作建议从 {move_start:.2f}s 左右开始，不要晚于 {start_time + 1:.2f}s。",
        f"- 主体移动链必须持续到 {end_time - 1:.2f}s 之后，建议在 {finish_target:.2f}s 左右完成最终收束。",
        "- 建议至少 4 个有意义 keyframe，不要用 3 个短 move 很快跑完再等。",
        "- 每个 keyframe 的 interval 是当前 cue 到下一 cue 的差值，不是从 segment_start 累计到目标 cue；不要用 `t_target - start_s` 给后续 keyframe 反复算预算。",
        "- 合法速度范围是 20-200cm/s，加速度范围是 50-400cm/s^2；边界值可以按需要使用，但必须和飞行时间预算匹配。",
        "- 每架机的命令游标应大致经过这些 cue；若估算飞行时间总和更短，就降低速度、增加弧线路径或加入有构图意义的中间 keyframe：",
    ]
    for index, weight in enumerate(weights, start=1):
        duration = active_s * weight
        cue += duration
        lines.append(f"  - keyframe {index}: interval ~= {duration:.2f}s, finish ~= {cue:.2f}s")
    lines.append(
        "- 任何方案生成前先检查：所有 move2 后的 light+delay 累计执行预算，"
        f"必须让有效群体运动结束时间落在 {end_time - 1:.2f}-{end_time:.2f}s。"
    )
    return "\n".join(lines)


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

    user = f"""生成 Pyfii 编舞段 
## 代码格式要求（必须严格遵循）

每个 move2 必须按以下模式编写：

v, a = 150, 300
d = ((tx-prev_x)**2 + (ty-prev_y)**2 + (tz-prev_z)**2) ** 0.5
ft = flight_time_ms(d, v, a)
drone.move2(tx, ty, tz)
apply_light(drone, "#FFD700", 8)
drone.delay(max(0, ft - 800 + 200))

不允许 delay(1500) 或任何固定数字。
不允许省略 flight_time_ms 计算。
{segment_id}。

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

    user += """
## 计算沙箱
在生成代码前，先用以下函数验证你的设计，结果硬编码到最终代码：
- `best_assign(starts, targets)` → 返回 `{"perm": (0,1,2,...), "min_d_cm": 89.0}`
- `flight_time_ms(distance_cm, speed, acc)` → 返回 ms 整数
- `distance_3d(p1, p2)` → 返回 cm 浮点数
- `vel_for_distance_time(distance_cm, time_s)` → 返回最小速度

**每个 move2 后 delay 必须 >= flight_time_ms(d, v, a) - light_ticks*100 + margin(100-200ms)**
**不要用固定 delay 混过去，必须根据实际距离计算。**
## 要求
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
        user += _timing_budget_hint(start_time, end_time) + "\n\n"
        user += f"""- 运动包络：本段 {start_time:.2f}-{end_time:.2f}s，明显运动必须在 {start_time + 1:.2f}s 前开始，并在 {end_time - 1:.2f}s 后、{end_time:.2f}s 前完成收束
- 动作必须连贯：当前段任意整体悬停不得超过 1 秒；不能用连续 delay/light 空转填满段落
- 连贯必须是有效群体运动：任意 1 秒内不能只剩一两架慢挪、微小 Z 波动或错峰 delay；至少一组无人机要共同产生可见位移
- 如果需要停顿呼吸，压到 0.8 秒以内，并让分组错峰或仍在执行的高度/弧线 keyframe 承接下一动作
- 时间线必须覆盖全段：PyFii 是每架机各自累计时间，不是 Python 循环全局时间；段内通常用一次 inittime(start)，然后按 move2 -> 短灯光/执行等待 -> move2 链式推进
- 每个 move2 后都要按 3D 距离和 VelXY/VelZ 计算飞行时间；后续 light+delay 是这次移动的执行预算，不是段尾填空
- 运动学计算属于 agent 侧小工具：不要在本段代码里定义 dist3/flight_time_ms/speed_for_interval/move_interval；应先估算，再写入具体 speed/accel/delay 数值
- 不要在段代码里 import、定义 best_assign 或做 itertools/permutation 搜索；排列必须在生成前完成并硬编码为 perm/target_idx
- 段尾收束必须是实际移动在最后 1 秒内仍在执行并完成，不能只用纯灯光/静止等待填满
- 段尾最后 1 秒必须是有效群体收束动作，不允许主体提前结束后用单机慢挪、小幅 Z/XY 抖动把 motion_end 拖到段尾
- 禁止结构：全体同一 inittime -> 多个短 move2 很快完成 -> apply_light(ticks>=10)/长 delay 填尾
- 推荐结构：把 A/B/C 分组动作重叠排布；灯光脉冲默认 ticks<=6；如果某个 interval 过长，降低速度、增加中间 keyframe 或增加路径弧度，而不是补长 delay
- 对任何可能形成全局等待的区间，在 1 秒到达前安排真实路线移动；只改颜色不算运动
- 连贯不等于小抖动：多数无人机必须离开入口位置形成有效位移，正式段要有跨区域展开/收缩/交换；小幅 Z/XY 呼吸只能用作衔接，不能作为主体动作
- 3D 舞台：不能全程固定高度；必须设计 low/mid/high 高度层，至少一半无人机有明显 Z 变化，并用 3D 距离做时间预算
- 几何叙事：不能整段圆形/同心圆/固定角度排序；至少包含两种非同构几何或路线趋势，必要时打破圆形排序
- 节奏建模：不能整段只用固定 VelXY/VelZ；每个 keyframe 要按 distance 和 interval_s 重新选择 speed/acceleration
- 禁止凑时长尾巴：不要用最后几下小幅 Z 波动、10cm 左右挪动或纯灯光把 motion_end 拖到段尾；段尾必须是有构图意义的新姿态
"""
    else:
        user += "- 起飞和降落段不计入编舞连贯性硬门；仍必须安全、平滑、执行完成\n"

    user += """- 几何内部点间距 > 51cm
- 安全优先于视觉复杂度；如果复杂换位有碰撞风险，使用扇区保持、排队错峰和更少几何
- best_assign 结果硬编码为 perm = (...)
- 生成前先算每个 move2 的飞行时间，确保该移动后的 light + delay 执行预算够
- acceleration 是独立节奏参数；a=2v 只能作为经验候选，不能写成固定规律
- 不要只做一个 move2 —— 可以多几何、条件分支、相对移动、排队错峰
- VelXY 和 VelZ 最好成对设置，并使用同一组 speed/accel；这是为了兼容原始 XML/回放语义，不是 PyFii API 本身的物理限制
- 目标几何必须体现高度层，不能所有 target 共用同一个 z
- 速度/加速度必须按每段 keyframe 动态计算，不能整段复用同一个 VelXY/VelZ
"""

    if feedback:
        user += f"\n\n## 人类反馈\n{feedback}"



    return system, user
