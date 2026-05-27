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
    "pyfii_tutorial.md",
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
## 代码格式（必须包含以下两行代码，否则验证失败）

每个几何过渡必须包含这一行：
```python
targets = best_assign(prev, geo[gi])
```
**best_assign 在 function.py 中已定义，不需要 import**。

完整写法：
```python
for gi in range(len(geos)):
    targets = geo[gi] if gi == 0 else best_assign(prev, geo[gi])
    for i, d in enumerate(drones):
        dd = math.hypot(prev[i][0]-targets[i][0], prev[i][1]-targets[i][1])
        spd = min(200, max(120, int(dd/2.0)))
        d.VelXY(spd, spd*2); d.VelZ(spd, spd*2)
        d.move2(clamp_xy(targets[i][0]), clamp_xy(targets[i][1]), clamp_z(targets[i][2]))
        apply_light(d, color, 12); d.delay(1200)
    prev = targets
```

## 要求
- 复制教程中的固定模板，只替换几何坐标
- 每个几何过渡必须包含 targets = geos[gi] if gi == 0 else best_assign(prev, geos[gi])
- 禁止同心圆几何

    if feedback:
        user += f"\n\n## 人类反馈\n{feedback}"



    return system, user
