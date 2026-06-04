"""Planning pass — two-stage: JSON plan → budget table → code."""

import json
import re
from typing import Sequence


def build_planning_prompt(
    segment_id: str,
    start_time: float,
    end_time: float,
    intent: str,
    prev_state: Sequence[Sequence[float]] | None,
) -> str:
    """Prompt for first pass: output structured JSON plan."""
    prev_lines = []
    if prev_state and len(prev_state) == 7:
        for i, p in enumerate(prev_state):
            prev_lines.append(f"  d{i}: [{float(p[0]):.0f}, {float(p[1]):.0f}, {float(p[2]):.0f}]")
    prev_text = "\n".join(prev_lines) if prev_lines else "无"

    return f"""## 规划 {segment_id} ({start_time}-{end_time}s, 时长{end_time-start_time}s)
意图: {intent}

上一段出口:
{prev_text}

输出 JSON 计划：
```json
{{
  "keyframes": [
    {{
      "start_s": {start_time},
      "duration_s": 3.2,
      "feel": "crisp_expand",
      "targets": [
        [x0,y0,z0], [x1,y1,z1], [x2,y2,z2], [x3,y3,z3], [x4,y4,z4], [x5,y5,z5], [x6,y6,z6]
      ],
      "speed_cm_s": 170,
      "accel_cm_s2": 320,
      "light_color": "#44aaff",
      "light_ticks": 4
    }},
    {{
      "start_s": {start_time+3.2},
      "duration_s": 3.2,
      "feel": "snap_rotate",
      "targets": [...],
      "speed_cm_s": 160,
      "accel_cm_s2": 300,
      "light_color": "#ff6644",
      "light_ticks": 4
    }}
  ]
}}
```

节奏目标: 动作更利落，不要用单个慢 move 拖满段落；优先用 2-4 个 2.6-3.6s 的可完成强 keyframe 或分组错峰承接。
可完成性: 单个 2.6-3.2s keyframe 的 3D 路径通常控制在约 180-360cm；不要规划 500cm 级跨场短飞。
约束: XY间距≥200cm, Z 100-250cm, targets总数=7, 速度20-200, 加速度50-400, 推荐速度150-200、加速度260-400，灯光ticks 3-5, 段长{end_time-start_time}s。

只输出 JSON，不解释。"""


def parse_plan_json(text: str) -> dict | None:
    """Extract JSON plan from LLM response."""
    # Try fenced
    m = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try raw
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def plan_to_budget_table(plan: dict, prev_state: list) -> str:
    """Convert JSON plan to a code-friendly budget table using planning_tools."""
    try:
        from .planning_tools import budget_layer, to_xyz
        from .motion_math import dist3, flight_time_ms
    except ImportError:
        return "⚠️ planning tools unavailable"

    lines = ["## 预算表 (agent 侧计算，直接使用)"]
    lines.append("```")
    current_prev = [(float(p[0]), float(p[1]), float(p[2])) for p in prev_state]

    for kf_i, kf in enumerate(plan.get("keyframes", [])):
        targets = kf.get("targets", [])
        if len(targets) != 7:
            continue
        v = kf.get("speed_cm_s", 170)
        a = kf.get("accel_cm_s2", 320)
        feel = kf.get("feel", "balanced")
        light_ticks = kf.get("light_ticks", 4)
        light_color = kf.get("light_color", "#4488ff")

        lines.append(f"\n--- Keyframe {kf_i+1} ({feel}) ---")
        lines.append(
            f"planning_speed={v} planning_accel={a} light={light_color} ticks={light_ticks} "
            "(speed/accel are already absorbed into fly_ms; final code must not set speed/accel)"
        )
        lines.append(f"drone  target(x,y,z)  dist3(cm)  fly_ms  delay_ms")
        for i in range(7):
            t = targets[i]
            dist = dist3(current_prev[i], t)
            ft = flight_time_ms(dist, v, a)
            delay_ms = max(0, ft - light_ticks * 100)
            lines.append(
                f"d{i}     ({t[0]:.0f},{t[1]:.0f},{t[2]:.0f})  {dist:.0f}  {ft}  {delay_ms}"
            )
        current_prev = [(float(t[0]), float(t[1]), float(t[2])) for t in targets]

    lines.append("```")
    lines.append("\n把上表直接翻译为 Python 代码，只使用 target/fly_ms/delay_ms/light/ticks，不要写 speed/accel API。")
    return "\n".join(lines)


def build_coding_prompt(budget_table: str, segment_id: str, start_time: float, end_time: float) -> str:
    """Second pass: budget table → Python code."""
    return f"""## 编码 {segment_id} ({start_time}-{end_time}s)

{budget_table}

## 规则
- `drones` 是 7 架无人机对象列表；循环写 `for i, drone in enumerate(drones):`
- 每 keyframe：`move2(drone, (x,y,z), flying_ms)` → `apply_light(drone, color, ticks)` → `drone.delay(delay_ms)`
- `planning_speed/planning_accel` 只用于预算 fly_ms；final 代码不要写 set_speed/set_accel/VelXY/VelZ，也不要写 `drone[d]`
- 如需错峰，只能在同一个 per-drone loop 里对当前 `drone.delay(i * 60)`，但不要改变表格里的 fly_ms/delay_ms
- 段尾：prev = [(t[0],t[1],t[2]) for t in targets_last]
- 禁止 import/def/markdown/inittime/VelXY

只输出 fenced Python：
```python
# 你的代码
```
不要 marker/import/def/解释。"""
