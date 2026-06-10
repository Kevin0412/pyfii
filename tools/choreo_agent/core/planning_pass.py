"""Planning pass — two-stage: JSON plan → budget table → code."""

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


def build_planning_prompt(
    segment_id: str,
    start_time: float,
    end_time: float,
    intent: str,
    prev_state: Sequence[Sequence[float]] | None,
    drone_count: int = 7,
    composition_plan: Mapping[str, Any] | None = None,
) -> str:
    """Prompt for first pass: output structured JSON plan."""
    prev_lines = []
    drone_count = int(drone_count)
    if prev_state and len(prev_state) == drone_count:
        for i, p in enumerate(prev_state):
            prev_lines.append(f"  d{i}: [{float(p[0]):.0f}, {float(p[1]):.0f}, {float(p[2]):.0f}]")
    prev_text = "\n".join(prev_lines) if prev_lines else "无"
    target_example = ", ".join(f"[x{i},y{i},z{i}]" for i in range(drone_count))
    composition_text = _format_planning_composition_plan(composition_plan, segment_id)

    return f"""## 规划 {segment_id} ({start_time}-{end_time}s, 时长{end_time-start_time}s)
意图: {intent}

{composition_text}

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
        {target_example}
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
约束: XY间距≥200cm, Z 100-250cm, targets总数={drone_count}, 速度20-200, 加速度50-400, 推荐速度150-200、加速度260-400，灯光ticks 3-5, 段长{end_time-start_time}s。
章法约束: JSON 里的 feel/targets/light_color 必须服务全局章法；不要随机换题，不要连续重复同一种退化队形。

只输出 JSON，不解释。"""


def _format_planning_composition_plan(
    plan: Mapping[str, Any] | None,
    segment_id: str,
) -> str:
    if not isinstance(plan, Mapping) or not plan:
        return ""

    lines = ["全局章法:"]
    theme = _text(plan.get("theme"))
    if theme:
        lines.append(f"- theme: {theme}")
    motifs = _items(plan.get("movement_motifs") or plan.get("motifs"))
    if motifs:
        lines.append(f"- motifs: {'; '.join(motifs[:8])}")
    roles = plan.get("segment_roles")
    role = roles.get(str(segment_id).upper()) if isinstance(roles, Mapping) else None
    if isinstance(role, Mapping):
        role_text = _text(role.get("role") or role.get("intent"))
        if role_text:
            lines.append(f"- current role: {role_text}")
        role_motifs = _items(role.get("motifs"))
        if role_motifs:
            lines.append(f"- current motifs: {'; '.join(role_motifs[:6])}")
        avoid = _items(role.get("avoid"))
        if avoid:
            lines.append(f"- avoid: {'; '.join(avoid[:6])}")
    return "\n".join(lines)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _items(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_text(item) for item in value if _text(item)]
    return []


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


def plan_to_budget_table(plan: dict, prev_state: list, drone_count: int = 7) -> str:
    """Convert JSON plan to a code-friendly budget table using planning_tools."""
    try:
        from .planning_tools import budget_layer, to_xyz
        from .motion_math import dist3, flight_time_ms
    except ImportError:
        return "⚠️ planning tools unavailable"

    lines = ["## 预算表 (agent 侧计算，直接使用)"]
    lines.append("```")
    drone_count = int(drone_count)
    current_prev = [(float(p[0]), float(p[1]), float(p[2])) for p in prev_state]

    for kf_i, kf in enumerate(plan.get("keyframes", [])):
        targets = kf.get("targets", [])
        v = kf.get("speed_cm_s", 170)
        a = kf.get("accel_cm_s2", 320)
        feel = kf.get("feel", "balanced")
        light_ticks = kf.get("light_ticks", 4)
        light_color = kf.get("light_color", "#4488ff")

        lines.append(f"\n--- Keyframe {kf_i+1} ({feel}) ---")
        if len(targets) != drone_count:
            lines.append(f"skip: targets count {len(targets)} != drone_count {drone_count}")
            continue
        lines.append(
            f"planning_speed={v} planning_accel={a} light={light_color} ticks={light_ticks} "
            "(speed/accel are already absorbed into fly_ms; final code must not set speed/accel)"
        )
        lines.append(f"drone  target(x,y,z)  dist3(cm)  fly_ms  delay_ms")
        for i in range(drone_count):
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


def build_coding_prompt(
    budget_table: str,
    segment_id: str,
    start_time: float,
    end_time: float,
    drone_count: int = 7,
    composition_plan: Mapping[str, Any] | None = None,
) -> str:
    """Second pass: budget table → Python code."""
    composition_text = _format_planning_composition_plan(composition_plan, segment_id)
    return f"""## 编码 {segment_id} ({start_time}-{end_time}s)

{budget_table}

{composition_text}

## 规则
- `drones` 是 {int(drone_count)} 架无人机对象列表；循环写 `for i, drone in enumerate(drones):`
- 代码开头必须写 5 行设计卡注释：`# role: ...`, `# motifs: ...`, `# beat: ...`, `# formation: ...`, `# lighting: ...`
- 设计卡必须承接全局章法，尤其是 current role/current motifs；不要写随机队形说明
- 几何主路径是手写目标点表：`geo = custom_points([...], n=len(drones), min_xy_cm=90)`，再 `best_assign` 或 `far_assign`；S02-S05 禁止调用 `geo_wide_v/geo_arrow/geo_box/geo_diagonal/geo_wave/geo_grid`
- 首选每个 keyframe 直接写：`prev = move_group(drones, targets, flying_ms, color, ticks)`
- 卡农/错峰 keyframe 写：`prev = move_group_staggered(drones, targets, flying_ms, color, ticks, group_mod=3, stagger_ms=120)`
- 3s 以上 keyframe 若用 `far_assign`，写 `min_path_cm=active_min_path_cm(flying_ms)`；不要写 90/100cm 导致真实运动过早结束
- 安全距离按 XY 看，不要把同一 XY 不同 Z 当成安全分离
- 6-8s 中短窗口只写 2 个强 keyframe；若错峰，stagger_ms=60-90，避免第三个 keyframe 把段尾动作拖成未完成
- 只有需要非常细的 per-drone 控制时，才展开：`move2(drone, (x,y,z), flying_ms)` → `apply_light(drone, color, ticks)` → `drone.delay(delay_ms)`
- `planning_speed/planning_accel` 只用于预算 fly_ms；final 代码不要写 set_speed/set_accel/VelXY/VelZ，也不要写 `drone[d]`
- 如需错峰，只能在同一个 per-drone loop 里对当前 `drone.delay(i * 60)`，但不要改变表格里的 fly_ms/delay_ms
- 段尾：prev = [(t[0],t[1],t[2]) for t in targets_last]
- 禁止 import/def/markdown/inittime/VelXY

只输出 fenced Python：
```python
# 你的代码
```
不要 marker/import/def/解释。"""
