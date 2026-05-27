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
    "pyfii_guide.md",
    "pyfii_segment_protocol.md",
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

    user = f"""生成 {segment_id} ({start_time}-{end_time}s) Pyfii 编舞代码。

要求：
- 1 个 keyframe，非对称几何（间距>=200cm）
- 只用 move2(d, (x,y,z), t) 移动（内部已含 delay，不要额外 d.delay）
- best_assign 排列
- 段代码是片段，不写 marker/import/创建 drone/重定义 prev
- 总 move2 时间不超过段长（{end_time - start_time}s）
"""

    if feedback:
        user += f"\n\n## 人类反馈\n{feedback}"



    return system, user
