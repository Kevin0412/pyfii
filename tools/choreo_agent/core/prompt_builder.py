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

    # 设计意图 → 模板建议
    intent_templates = {
        "展开": "breathe+expand: geo1从prev偏移30-40cm，geo2大幅展开(间距≥200cm)",
        "分组": "role mapping: 不同机走不同路径(if role=='wing':...elif role=='core':...)",
        "旋转": "math trajectory: 用复数旋转或sin/cos生成geo，营造旋转感",
        "呼吸": "density breathing: 多kf循环，半径在150-300cm间脉动",
        "收束": "收缩: geo从大到小，灯光暖色→冷色，准备收尾",
        "降落": "land: 半径缩小到120cm，Z降到100cm，速度降低",
    }
    template_hint = intent_templates.get(intent, "breathe+expand")
    
    user = f"""续写 {segment_id} ({start_time}-{end_time}s)。当前7机坐标：
{prev_state}

要求：
- 设计 {1 if (end_time-start_time)<10 else 2} 组关键帧几何(geo)，每组7个(x,y,z)坐标
- geo间距≥100cm，不做同心圆
- 用 best_assign(prev, geo) 分配目标
- 用 move2(d, (x,y,z), t) 移动，t根据距离计算(2000-4000ms)
- 段尾更新 prev = [(d.x,d.y,d.z) for d in drones]
- 设计意图: {intent}  ({template_hint})
"""

    if feedback:
        user += f"\n\n## 人类反馈\n{feedback}"



    return system, user

def _extract_last_locked_segment(design_py: str, locked_segment_ids=None) -> str:
    """提取最后一个 locked=true 的段的代码"""
    lines = design_py.splitlines()
    seg_lines = []
    in_target = False
    for line in lines:
        if "PYFII_AGENT_SEGMENT_START" in line and "locked=true" in line:
            in_target = True
            seg_lines = []
            continue
        if "PYFII_AGENT_SEGMENT_END" in line and in_target:
            in_target = False
            break
        if in_target and line.strip() and not line.strip().startswith("#"):
            seg_lines.append(line)
    return "\n".join(seg_lines[-30:])  # 只取最后30行，避免过长
