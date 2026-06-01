"""Prompt Builder — loads context packs for system prompt, builds user prompt."""

from pathlib import Path
from typing import Sequence

CONTEXT_DIR = Path(__file__).resolve().parent.parent / "context_packs"

# 加载顺序：API 基础 → 规则 → 模式 → 验证
PACK_ORDER = [
    "pyfii_guide.md",
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
    pass  # motion_math summary removed
    pass  # planning_tools summary removed
    parts.append("""
## 输出格式
只输出当前段的 Python 代码片段（4空格缩进），不输出 marker、import、或 function 定义。
S01 可先写 `start_positions`、`takeoff()` 和 `wait_until(drones, start_time)`，然后再写 `prev = [(d.x, d.y, d.z) for d in drones]`。
S02+ 从 `auto_init(drones)` 和 `prev = [(d.x, d.y, d.z) for d in drones]` 开始。
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

    is_s01 = segment_id.upper() == "S01"
    if is_s01:
        segment_start_rule = f"""- 首段必须先设计 `start_positions`，设置 `drone.X = drone.x` 与 `drone.Y = drone.y`，再 `drone.takeoff(1, 110)`
- 起飞后调用 `wait_until(drones, {start_time})` 对齐正式编舞窗口；不要直接写 `inittime()`
- 然后写 `prev = [(d.x, d.y, d.z) for d in drones]` 并开始正式 move2 动作"""
    else:
        segment_start_rule = """- 段首调用 `auto_init(drones)`，再写 `prev = [(d.x, d.y, d.z) for d in drones]`
- 不要直接写 `inittime()`；跨段对齐由 `auto_init` 处理"""

    if segment_id.upper() in {"S04", "S05"}:
        assign_rule = "- S04/S05 需要大动作或反馈出现路径太短时，用 `targets = far_assign(prev, geo, min_path_cm=90)`；其他承接/收束可用 `best_assign(prev, geo)`。返回值都是 targets 列表，不要拆 `perm/min_d`"
    else:
        assign_rule = "- `targets = best_assign(prev, geo)`；若反馈说路径太短/小范围抖动，可改用 `far_assign(prev, geo, min_path_cm=90)`。prev/geo 用完整 `(x,y,z)`，返回值就是重排后的 targets 列表，不要拆 `perm/min_d`"

    user = f"""## {segment_id} ({start_time}-{end_time}s, 时长{end_time - start_time}s)
意图：{intent or segment_id}

{prev_text}

## 要求
{segment_start_rule}
- 2个 keyframe，非对称几何（XY间距≥200cm）
- {assign_rule}
- 每次移动必须在同一个 per-drone loop 内完成：move2 → apply_light → drone.delay(flying_ms-ticks*100+100)
- 禁止只给 `drones[0]` 或单架无人机 delay/light；每架机都要给本次 move2 留执行时间
- 主体 move2 通常用 3000-5000ms；不要用 7000ms+ 超慢移动凑时长，段尾由 auto_init 压缩
- 高度层必须真实混合：每个主体 keyframe 至少 3 个 Z 层，整段 Z range ≥90cm；不要全队同一高度平面
- LAND 前如果整体真实动作还没超过 60s，系统会追加 S07/S08 等正式段继续编舞；不要靠当前段硬等待
- 段尾更新 prev = [(t[0],t[1],t[2]) for t in targets]
- ## 时间预算
段长: {end_time - start_time}s。所有 move2 的 flying_ms 之和必须≥ {(end_time - start_time - 1) * 1000:.0f}ms（留1s灯光余量）
示例: 3个move2，各3000ms → 总9000ms，覆盖9s → 最后动作在 {start_time + 9}s 结束 ✓
反例: 2个move2，各2500ms → 总5000ms，覆盖5s → 动作在 {start_time + 5}s 结束 ✗（收束过早）
- 禁止inittime/VelXY/drone.x=tx/import
- 只输出代码片段（4空格缩进）"""

    if feedback:
        user += f"\n\n## 上一轮反馈\n{feedback}\n根据反馈修正。"

    return system, user
