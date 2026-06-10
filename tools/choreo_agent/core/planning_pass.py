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
    keyframe_text = _format_keyframe_contract(segment_id, start_time, end_time)
    coordinate_seeds = _format_safe_coordinate_seeds(drone_count)

    return f"""## 规划 {segment_id} ({start_time}-{end_time}s, 时长{end_time-start_time}s)
意图: {intent}

{composition_text}

上一段出口:
{prev_text}

{keyframe_text}

{coordinate_seeds}

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

节奏目标: 动作更利落，不要用单个慢 move 拖满段落；按上面的 keyframe 数量填表，允许段尾保留 0.3-0.8s 收束，不要反复讨论“是否覆盖整段”。
可完成性: 单个 keyframe 的 3D 路径通常控制在约 120-380cm；不要规划 500cm 级跨场短飞。
约束: targets总数={drone_count}, shape=[{target_example}], Z 100-250cm, target 点表内部 min_xy_cm≥90cm，优先 120-260cm；不要追求 200cm 以上导致 9 机场地放不下。速度20-200, 加速度50-400, 推荐速度150-200、加速度260-400，灯光ticks 3-5。
章法约束: JSON 里的 feel/targets/light_color 必须服务全局章法；不要随机换题，不要连续重复同一种退化队形。
输出纪律: 直接给 JSON；不要写距离证明、不要手算两两间距、不要自问自答。安全骨架已经给出，复制后少量变奏即可。

只输出 JSON，不解释。"""


def _format_keyframe_contract(segment_id: str, start_time: float, end_time: float) -> str:
    segment = str(segment_id).upper()
    duration = max(0.0, float(end_time) - float(start_time))
    if segment == "S04":
        count = 4
        note = "S04 是抒情展开/蓄力段，必须 4 个短 keyframes，至少 3 种 light_color。"
    elif segment == "S06":
        count = 2
        note = "S06 是尾声收束，必须 2 个 keyframes：中继 echo pose + 最终 signature pose。"
    elif duration >= 9.0:
        count = 3
        note = "长窗口用 3 个强 keyframes；不要把 10 秒压成两个 5 秒慢动作。"
    elif duration >= 7.0:
        count = 2
        note = "中窗口用 2 个强 keyframes，段尾留少量收束。"
    else:
        count = 2
        note = "短窗口只用 2 个可完成 keyframes。"

    active = max(1.8, duration - 0.7)
    step = active / count
    starts = [float(start_time) + step * i for i in range(count)]
    lines = [
        "Keyframe 合同:",
        f"- 必须输出 exactly {count} 个 keyframes；不要多也不要少。",
        f"- {note}",
        "- start_s 必须递增，duration_s 取 1.8-3.4s；段尾可以留 0.3-0.8s 视觉收束。",
        "- 推荐时间表:",
    ]
    for i, start in enumerate(starts, start=1):
        lines.append(f"  - k{i}: start_s={start:.1f}, duration_s={step:.1f}")
    return "\n".join(lines)


def _format_safe_coordinate_seeds(drone_count: int) -> str:
    if int(drone_count) != 9:
        return "坐标提示: 直接输出 numeric targets；不要写变量、表达式或省略号。"

    return """9机安全坐标骨架（低层点表，不是高层队形模板）:
- 这些 seed 只用来避免现场手算失败；每个 keyframe 选一个 seed 后可做 ±20-35cm 小变奏、换 z 层、换无人机顺序。
- 不要连续 keyframe 原样复制同一 seed；至少改变中心偏移、稀疏/密集、Z 层或左右/前后关系。
- 每个 targets 必须是 9 个 numeric triples，禁止变量/省略号/公式。

seed_box:
[[60,60,120],[280,60,210],[500,60,120],
 [60,280,180],[280,280,240],[500,280,180],
 [60,500,120],[280,500,210],[500,500,120]]

seed_slant:
[[80,80,220],[300,100,140],[520,120,200],
 [40,300,160],[260,300,240],[480,300,130],
 [80,520,190],[300,500,150],[520,480,230]]

seed_asym:
[[40,80,180],[250,50,240],[500,100,130],
 [120,260,120],[350,240,210],[540,310,160],
 [60,500,230],[290,520,150],[510,470,200]]"""


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
- 正式段默认展开 per-drone loop：`move2(drone, target, flying_ms)` → `apply_light(drone, color, ticks)` → `drone.delay(delay_ms)`，让每架机保留自己的灯光/等待细节
- `move_group/move_group_staggered` 只作为 smoke/兜底工具；S01-S06 纯 helper 执行会被 composition gate 打回。卡农/错峰请在 per-drone loop 内按 `i % group_mod` 写小 delay
- 3s 以上 keyframe 若用 `far_assign`，写 `min_path_cm=active_min_path_cm(flying_ms)`；不要写 90/100cm 导致真实运动过早结束
- 安全距离按 XY 看，不要把同一 XY 不同 Z 当成安全分离
- 6-8s 中短窗口只写 2 个强 keyframe；若错峰，stagger_ms=60-90，避免第三个 keyframe 把段尾动作拖成未完成
- S04 抒情展开段要写 4-5 个短 keyframe，至少 3 种颜色/灯光变化；S06 尾声要写两段式收尾（中继点 + 最终署名），不能单 keyframe 小挪动
- 每个 keyframe 完成后更新 `prev = [(t[0], t[1], t[2]) for t in targets]`
- `planning_speed/planning_accel` 只用于预算 fly_ms；final 代码不要写 set_speed/set_accel/VelXY/VelZ，也不要写 `drone[d]`
- 如需错峰，只能在同一个 per-drone loop 里对当前 `drone.delay(i * 60)`，但不要改变表格里的 fly_ms/delay_ms
- 段尾：prev = [(t[0],t[1],t[2]) for t in targets_last]
- 禁止 import/def/markdown/inittime/VelXY

只输出 fenced Python：
```python
# 你的代码
```
不要 marker/import/def/解释。"""
