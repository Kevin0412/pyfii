"""Prompt Builder — loads context packs for system prompt, builds user prompt."""

from pathlib import Path
from typing import Sequence

CONTEXT_DIR = Path(__file__).resolve().parent.parent / "context_packs"

# 加载顺序：API 基础 → 规则 → 模式 → 验证
PACK_ORDER = [
    "pyfii_api_minimal.md",
    "pyfii_guide.md",
    "pyfii_coding_rules.md",
    "pyfii_anti_patterns.md",
    "pyfii_validation_rules.md",
]


def _load_context_pack(name: str) -> str:
    path = CONTEXT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _motion_math_summary() -> str:
    """motion_math 模块的 agent-facing 摘要"""
    return """## 运动数学（motion_math）
```python
flight_time_ms(distance_cm, speed_cm_s, accel_cm_s2) -> int  # 飞行时间(ms)
dist3(p1, p2) -> float  # 3D距离(cm)
motion_budget(prev, targets, v, a) -> list  # 每架机的预算
```"""


def _planning_tools_summary() -> str:
    """planning_tools 模块的 agent-facing 摘要"""
    return """## 规划工具（planning_tools）
```python
generate_safe_geo(prev, mode, n=7, min_spacing_cm=120) -> list
# mode: expand/rotate/breathe/contract

check_min_spacing(points) -> (min_d_cm, (i,j))
predict_crossings(prev, targets) -> [(i, j, closest_cm), ...]
budget_layer(prev, targets, cue, feel='balanced') -> MovePlan
```"""


def build_system_prompt() -> str:
    """组装完整 system prompt：全部 context packs + 动态工具摘要。"""
    parts = []
    for name in PACK_ORDER:
        content = _load_context_pack(name)
        if content:
            parts.append(content)
    parts.append(_motion_math_summary())
    parts.append(_planning_tools_summary())
    parts.append("""
## 输出格式
只输出当前段的 Python 代码片段（4空格缩进），不输出 marker、import、或 function 定义。
代码从 `prev = [(d.x, d.y, d.z) for d in drones]` 开始，以 `prev = [...]` 或 `return duration` 结束。
""")
    return "\n\n".join(parts)


def build_segment_prompt(
    segment_id: str,
    start_time: float,
    end_time: float,
    intent: str,
    prev_state: Sequence[Sequence[float]] | None,
    feedback: str,
) -> tuple[str, str]:
    """Build system + user prompt for the current segment."""

    system = build_system_prompt()

    # 描述 prev 分布
    prev_lines = []
    if prev_state and len(prev_state) == 7 and any(float(p[2]) > 0 for p in prev_state):
        prev_lines.append(f"上一段出口7机坐标（{segment_id}起始）：")
        for i, p in enumerate(prev_state):
            prev_lines.append(f"  d{i}: ({float(p[0]):.0f}, {float(p[1]):.0f}, {float(p[2]):.0f})")
        xs = [float(p[0]) for p in prev_state]
        ys = [float(p[1]) for p in prev_state]
        zs = [float(p[2]) for p in prev_state]
        prev_lines.append(
            f"  XY: ({min(xs):.0f}-{max(xs):.0f}, {min(ys):.0f}-{max(ys):.0f})  "
            f"Z: {min(zs):.0f}-{max(zs):.0f}"
        )
        prev_text = "\n".join(prev_lines)
    else:
        prev_text = "无上一段坐标（首段）"

    user = f"""## {segment_id} ({start_time}-{end_time}s, 时长{end_time - start_time}s)
意图：{intent or segment_id}

{prev_text}

## 要求
- 2个 keyframe，非对称几何（XY间距≥200cm）
- best_assign排列（返回targets列表，不要拆perm/min_d）
- 每次移动：move2 → apply_light → drone.delay(flying_ms-ticks*100)
- Z轴渐进（100→150→200→150）
- 段尾更新 prev = [(t[0],t[1],t[2]) for t in targets]
- t_ms之和 ≤ {(end_time - start_time - 1) * 1000:.0f}ms
- 禁止inittime/VelXY/drone.x=tx/import
- 只输出代码片段（4空格缩进）"""

    if feedback:
        user += f"\n\n## 上一轮反馈\n{feedback}\n根据反馈修正。"

    return system, user
