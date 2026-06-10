"""Prompt Builder — loads context packs for system prompt, builds user prompt."""

from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any

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


def build_system_prompt(drone_count: int = 7) -> str:
    """组装完整 system prompt：全部 context packs + 动态工具摘要。"""
    parts = []
    for name in PACK_ORDER:
        content = _load_context_pack(name)
        if content:
            parts.append(content)
    parts.append(f"""
## 项目无人机数量
本项目 `len(drones) == {int(drone_count)}`。所有几何表、start_positions、targets、prev/exit_state 都必须使用 {int(drone_count)} 个 `(x,y,z)`。
如果示例或旧文档里写“7机/7个/7架”，按本项目数量 {int(drone_count)} 覆盖。
""")
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
    drone_count: int = 7,
    composition_plan: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """Build system + user prompt for the current segment."""

    drone_count = int(drone_count)
    system = build_system_prompt(drone_count=drone_count)

    # 描述 prev 分布
    prev_lines = []
    if prev_state and len(prev_state) == drone_count and any(float(p[2]) > 0 for p in prev_state):
        prev_lines.append(f"上一段出口{drone_count}机坐标（{segment_id}起始）：")
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

    segment_upper = segment_id.upper()
    composition_text = _format_composition_plan(composition_plan, segment_upper)
    is_s01 = segment_upper == "S01"
    is_land = segment_upper in {"LAND", "LANDING"}
    if is_land:
        segment_start_rule = """- LAND 是降落段，不是正式编舞连续性段
- 段首调用 `auto_init(drones)`，再对每架机执行短灯光提示和 `d.land()`
- 不要写 keyframe，不要 move2，不要用 LAND 继续凑正式动作"""
    elif is_s01:
        segment_start_rule = f"""- 首段必须先设计 `start_positions`，设置 `drone.X = drone.x` 与 `drone.Y = drone.y`，再 `drone.takeoff(1, z)`（z 可各机不同——如中心锚点机更高、外围低一些，建立视觉层次）
- `start_positions` 自身必须安全分散：{drone_count}个XY点最小间距≥180cm，不要中心聚团，不要把多数点放在 200-360cm 的中心小区域
- 起飞布局可用“六边形+中心/宽V/双层扇形”等分散结构；首个正式 keyframe 路径通常控制在 180-360cm，不要从中心直接硬飞到全场边界
- 起飞后调用 `wait_until(drones, {start_time})` 对齐正式编舞窗口；不要直接写 `inittime()`
- 然后写 `prev = [(d.x, d.y, d.z) for d in drones]` 并开始正式 move2 动作"""
    else:
        segment_start_rule = """- 段首调用 `auto_init(drones)`，再写 `prev = [(d.x, d.y, d.z) for d in drones]`
- 不要直接写 `inittime()`；跨段对齐由 `auto_init` 处理"""

    if segment_upper in {"S04", "S05"}:
        assign_rule = "- S04/S05 需要大动作或反馈出现路径太短时，用 `targets = far_assign(prev, geo, min_path_cm=active_min_path_cm(flying_ms))`；其他承接/收束可用 `best_assign(prev, geo)`。返回值都是 targets 列表，不要拆 `perm/min_d`"
    else:
        assign_rule = "- `targets = best_assign(prev, geo)`；若反馈说路径太短/小范围抖动，可改用 `far_assign(prev, geo, min_path_cm=active_min_path_cm(flying_ms))`。prev/geo 用完整 `(x,y,z)`，返回值就是重排后的 targets 列表，不要拆 `perm/min_d`"

    segment_duration = float(end_time - start_time)
    if segment_upper == "S06":
        keyframe_rule = (
            "S06 尾声必须写 2 个明确 keyframe：先到中继/呼应姿态，再到最终署名位置；"
            "每个 keyframe 用 2300-2600ms，展开 per-drone loop，不要用单个 move_group 小挪动收尾"
        )
        prev_update_rule = "每个 keyframe 后更新 prev；段尾更新 prev = [(t[0],t[1],t[2]) for t in targets]"
    elif segment_upper == "S04":
        keyframe_rule = (
            "S04 是抒情展开段：写 4-5 个短 keyframe，每个 2800-3200ms，"
            "至少 3 种颜色/灯光变化；使用手写非同构几何和 per-drone loop，避免同步大块移动"
        )
        prev_update_rule = "每个 keyframe 后更新 prev；段尾更新 prev = [(t[0],t[1],t[2]) for t in targets]"
    elif segment_upper == "S05":
        keyframe_rule = (
            "S05 是高潮段：写 3 个强 keyframe，边界爆发→分组交换/回卷→有高度层的收束；"
            "至少 3 种颜色或明显爆闪变化，主体使用 far_assign 和 per-drone loop"
        )
        prev_update_rule = "每个 keyframe 后更新 prev；段尾更新 prev = [(t[0],t[1],t[2]) for t in targets]"
    elif segment_duration <= 5.0:
        keyframe_rule = (
            "本段很短：只写 1 个强 keyframe，move2 用 2800-3600ms；"
            "目标几何必须靠近场地边界/角点并明显远离 prev，让多数无人机路径约 240cm 或更长，"
            "用 `targets = far_assign(prev, geo, min_path_cm=220)`，不要把点挤在中心，也不要只做 70-120cm 小挪动"
        )
        prev_update_rule = "段尾更新 prev = [(t[0],t[1],t[2]) for t in targets]"
    elif segment_duration <= 8.5:
        keyframe_rule = (
            "本段是 6-8s 中短窗口：只写 2 个强 keyframe，不要写第三个 keyframe；"
            "每个 keyframe 用 3300-3500ms，若卡农/错峰则 stagger_ms=60-90，避免段尾动作未完成；"
            "两个 keyframe 都优先 `far_assign(prev, geo, min_path_cm=active_min_path_cm(flying_ms))`，不要第二拍改回 best_assign 导致交叉"
        )
        prev_update_rule = "段尾更新 prev = [(t[0],t[1],t[2]) for t in targets]"
    else:
        keyframe_rule = "2-4个利落 keyframe，非对称几何（点表 XY 间距默认 ≥90cm，开阔段优先 120-260cm；刻意密集造型可降到 55-75cm，硬下限 51cm），用短促推进/交换/高度切层制造节奏"
        prev_update_rule = "段尾更新 prev = [(t[0],t[1],t[2]) for t in targets]"

    coordinate_hint = _format_coordinate_hint(drone_count, segment_upper)

    if is_land:
        user = f"""## {segment_id} ({start_time}-{end_time}s, 时长{end_time - start_time}s)
意图：{intent or segment_id}

{composition_text}

{prev_text}

## 要求
{segment_start_rule}
- 代码开头写设计卡注释：`# role: ...`, `# motifs: ...`, `# beat: ...`, `# formation: ...`, `# lighting: ...`
- 对 {drone_count} 架无人机全部执行；可以统一白光/暖光闪烁 2-5 ticks 后 `d.land()`
- 不要只给单架 `drones[i]` 操作；使用 `for d in drones:` 或等价 per-drone loop。差异化可以接受（焦点机特写、交错启动），但不能跳过任何一架
- 禁止 inittime/VelXY/import
- 只输出代码片段（4空格缩进）"""
    else:
        user = f"""## {segment_id} ({start_time}-{end_time}s, 时长{end_time - start_time}s)
意图：{intent or segment_id}

{composition_text}

{prev_text}

## 要求
{segment_start_rule}
- 代码开头必须写 5 行设计卡注释，且必须承接“全局章法计划”的当前段角色：
  `# role: ...`
  `# motifs: ...`
  `# beat: ...`
  `# formation: ...`
  `# lighting: ...`
- {keyframe_rule}
- {coordinate_hint}
- {assign_rule}
- 几何主路径：整数坐标表 `geo = custom_points([...], n=len(drones), min_xy_cm=90)` 或 math 表达式 `[(cx+R*cos(2πi/N), cy+R*sin(2πi/N), z+dz*sin(i)) for i in range(N)]`，再 `best_assign/far_assign`；S02-S05 必须至少一个主体 keyframe 使用手写坐标表或 math 几何，禁止调用 `geo_wide_v/geo_arrow/geo_box/geo_diagonal/geo_wave/geo_grid`
- 正式段默认展开 per-drone loop，不要用 `move_group` 作为整段主结构：`move2(drone, target, flying_ms)` → `apply_light(drone, color, ticks)` → `drone.delay(flying_ms-ticks*100+100)`
- 不要重新质疑 `move2/apply_light/delay` 的语义，也不要在回答中推导 API；按上述顺序写代码即可，验证器会负责轨迹检查
- `move_group/move_group_staggered` 只作为 smoke/兜底工具；S01-S06 纯 helper 执行会被打回。卡农/错峰请在 per-drone loop 内按 `i % group_mod` 写小 delay，并保留每架机自己的灯光/等待
- 禁止只给单架 `drones[i]` 操作；使用 `for d in drones:` 或等价 per-drone loop。但可以在 loop 内做差异化：如 `d.delay(i * stagger_ms)` 交错启动, `if i == 0: apply_light(d, special_color, t)` 焦点机, `move2(d, (tx, ty, tz + dz*sin(i)), t)` Z 个性——区别对待不等于跳过
- 主体 move2 通常用 2600-3600ms；不要用 4500ms+ 超慢移动凑时长，段尾由 auto_init 压缩
- 快节奏必须可完成：单个 2600-3200ms keyframe 的 3D 路径通常控制在约 180-360cm；不要用 2000-2400ms 硬飞 500cm 跨场路径
- 如果段长需要覆盖，不要拉长单个 move2；用多个可完成的快 keyframe、分组错峰或高度切层承接，保持每 1 秒窗口都有群体运动
- 3s 以上 keyframe 不要写 `min_path_cm=90/100`；用 `flying_ms = 3000` 后 `targets = far_assign(prev, geo, min_path_cm=active_min_path_cm(flying_ms))`
- 安全距离按 XY 看：不要把同一 XY 的不同 Z 当成安全分离；开阔段每个 keyframe 的 XY 点间距尽量 ≥100cm，刻意密集造型可压到 55-75cm（硬下限 51cm，需配合短路径慢速），复杂交换交给 `far_assign`
- 高度层必须真实混合：每个主体 keyframe 至少 3 个 Z 层，整段 Z range ≥90cm；不要全队同一高度平面
- 编舞词汇（每段至少用一种，并在 #beat/#formation 标明）：交错启动 (delay(i*ms)), Z 个性 (move2 内 +dz*sin(i)), 分组对比 (两组不同几何/灯光), 焦点机 (1-2 架独立轨迹), 中心迁移, 密度呼吸, 灯光渐变 (同 keyframe 内多次 apply_light 或 range()+TurnOnAll((r,g,b)) 呼吸)；全段匀速单色无差异会被节奏门打回
- `TurnOnAll((r,g,b))` 直接接受 RGB 三元组 (0-255)：`d.TurnOnAll((255,255,255))`=白色。可在 per-drone loop 内做灯光渐变呼吸: `for a in range(30): d.TurnOnAll((int(128+127*sin(a*π/16)), ...)); d.delay(100)` — 30 ticks = 3秒渐变
- LAND 前如果整体真实动作还没超过 60s，系统会追加 S07/S08 等正式段继续编舞；不要靠当前段硬等待
- {prev_update_rule}
- ## 时间预算
段长: {end_time - start_time}s。所有 move2 的 flying_ms 之和必须≥ {(end_time - start_time - 1) * 1000:.0f}ms（留1s灯光余量）
示例: 3个move2，各3000ms → 总9000ms，覆盖9s → 快节奏且不会过早收束 ✓
反例: 1个move2，8000ms → 虽覆盖时间但视觉拖沓 ✗；2个move2，各2500ms → 总5000ms，动作在 {start_time + 5}s 结束 ✗（收束过早）
- 禁止 inittime/VelXY/import
- 只输出代码片段（4空格缩进）"""

    if feedback:
        user += f"\n\n## 上一轮反馈\n{feedback}\n根据反馈修正。"

    return system, user


def _format_coordinate_hint(drone_count: int, segment_id: str) -> str:
    if int(drone_count) != 9:
        return "坐标写数字三元组或 math 表达式（如 [(cx+R*cos(2πi/N), cy+R*sin(2πi/N), z) for i in range(N)]）；不要写省略号(...)"

    start_hint = ""
    if segment_id == "S01":
        start_hint = (
            "S01 的 start_positions 推荐直接用安全 3x3 起飞格："
            "`[(80,80),(280,80),(480,80),(80,280),(280,280),(480,280),(80,480),(280,480),(480,480)]`；"
            "不要把起飞点挤成中心团"
        )

    discipline = (
        "9机手写坐标表：用粗网格整数坐标（建议 20/50 的倍数），XY 0-560，Z 在 80-250 内至少 3 层；"
        "不要手算两两距离——间距/路径安全由规划检查器和 validator 用精确数字回报；"
        "禁止 jitter_points；custom_points 默认 min_xy_cm=90，刻意密集造型可用 51-90 的字面量"
    )
    if start_hint:
        return f"{start_hint}；{discipline}"
    return discipline


def _format_composition_plan(
    plan: Mapping[str, Any] | None,
    segment_id: str,
) -> str:
    """Keep global dramaturgy in the user prompt without bloating system cache."""
    if not isinstance(plan, Mapping) or not plan:
        return ""

    lines = ["## 全局章法计划（必须服从，减少随机续写）"]
    theme = _stringish(plan.get("theme"))
    if theme:
        lines.append(f"- 作品主题：{theme}")

    arc = _stringish(plan.get("dramaturgy") or plan.get("arc"))
    if arc:
        lines.append(f"- 段落推进：{arc}")

    motifs = _listish(plan.get("movement_motifs") or plan.get("motifs"))
    if motifs:
        lines.append(f"- 动作母题：{'; '.join(motifs[:8])}")

    light_arc = _stringish(plan.get("light_arc"))
    if light_arc:
        lines.append(f"- 灯光弧线：{light_arc}")

    continuity = _listish(plan.get("continuity_rules"))
    if continuity:
        lines.append(f"- 跨段规则：{'; '.join(continuity[:6])}")

    roles = plan.get("segment_roles")
    role = roles.get(segment_id) if isinstance(roles, Mapping) else None
    if isinstance(role, Mapping):
        role_text = _stringish(role.get("role") or role.get("intent"))
        if role_text:
            lines.append(f"- 当前段角色：{role_text}")
        role_motifs = _listish(role.get("motifs"))
        if role_motifs:
            lines.append(f"- 当前段要使用/变奏的母题：{'; '.join(role_motifs[:6])}")
        relationship = _stringish(role.get("relationship"))
        if relationship:
            lines.append(f"- 与前后段关系：{relationship}")
        avoid = _listish(role.get("avoid"))
        if avoid:
            lines.append(f"- 当前段避免：{'; '.join(avoid[:6])}")
    elif isinstance(role, str) and role.strip():
        lines.append(f"- 当前段角色：{role.strip()}")

    lines.append("- 执行方式：先满足本段安全/连续性硬门，再让队形、速度、灯光服务上述主题；复现母题时必须做方向、高度或节奏变奏，不要随机换题。")
    return "\n".join(lines)


def _stringish(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _listish(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_stringish(item) for item in value if _stringish(item)]
    return []
