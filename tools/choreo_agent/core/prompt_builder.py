"""Pyfii choreo agent — prompt builder."""

from typing import Sequence


def build_segment_prompt(
    segment_id: str,
    start_time: float,
    end_time: float,
    guide: dict,
    intent: str,
    prev_state: Sequence[Sequence[float]] | None,
    system: str,
    feedback: str,
) -> tuple[str, str]:
    """Build system + user prompt for the current segment."""

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

    # API 参考
    api_ref = """## 可用API（from function import *）
```python
move2(d, (x,y,z), t_ms, T=100)  # 反算速度→VelXY+VelZ→move2→delay(t_ms)。内部已含delay！
apply_light(d, "#RRGGBB", ticks) # ticks×100ms灯光
best_assign(prev, geo)           # 最优排列 → targets 列表
clamp_xy(v)  # [0,560]; clamp_z(v)  # [80,250]
```"""

    user = f"""## {segment_id} ({start_time}-{end_time}s, 时长{end_time - start_time}s)
意图：{intent or segment_id}

{prev_text}

{api_ref}

## 要求
- 2个 keyframe，非对称几何（XY间距≥200cm）
- best_assign排列（不用恒等映射）
- move2(d,(x,y,z),t_ms)移动（已含delay，不额外drone.delay()）
- 每keyframe设灯光 apply_light(d,"#RRGGBB",3-5)，不同keyframe不同色
- Z轴渐进（100→150→200→150）
- 段尾更新 prev = [(t[0],t[1],t[2]) for t in targets]
- t_ms之和 ≤ {(end_time - start_time - 1) * 1000:.0f}ms
- 禁止inittime/VelXY/drone.x=tx
- 只输出代码片段（4空格缩进），不输出marker/import"""

    if feedback:
        user += f"\n\n## 上一轮反馈\n{feedback}\n根据反馈修正。"

    return system, user
