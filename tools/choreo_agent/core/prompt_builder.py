"""Prompt Builder — loads context packs for system prompt, builds user prompt."""

from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any

from .skills import role_class_for_segment, skill_menu_for_role
from .validator import motion_quality_minimums
from .limits import (
    COLLISION_FLOOR_CM,
    FIELD_XY_MAX,
    FIELD_XY_MIN,
    Z_MAX_CM,
    Z_MIN_CM,
)

_FLOOR = int(COLLISION_FLOOR_CM)
_XY = f"{int(FIELD_XY_MIN)}-{int(FIELD_XY_MAX)}"
_Z = f"{int(Z_MIN_CM)}-{int(Z_MAX_CM)}"

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


def format_prev_design_card(card: Mapping[str, Any] | None) -> str:
    """上一段设计卡 → 承接提示块；空卡返回空串（prompt 字节不变）。

    没有它，"呼应上一段/为下段铺垫"类指令物理上无从呼应——
    此前只有出口坐标前传，母题/队形/灯光语义全部丢失。
    """
    if not card:
        return ""
    fields = [(k, str(card.get(k, "")).strip()) for k in ("role", "motifs", "formation", "lighting")]
    fields = [(k, v) for k, v in fields if v]
    if not fields:
        return ""
    inner = "；".join(f"#{k}: {v}" for k, v in fields)
    return (
        f"上一段设计卡（{inner}）——本段编舞要与之构成有意识的关系："
        "承接/变奏其母题，或做明确对比；不要无视它随机换题。"
    )


def build_segment_prompt(
    segment_id: str,
    start_time: float,
    end_time: float,
    intent: str,
    prev_state: Sequence[Sequence[float]] | None,
    feedback: str,
    drone_count: int = 7,
    composition_plan: Mapping[str, Any] | None = None,
    human_preferences: str = "",
    prev_design_card: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """Build system + user prompt for the current segment."""

    drone_count = int(drone_count)
    system = build_system_prompt(drone_count=drone_count)
    preferences_text = ""
    if human_preferences.strip():
        from .design_memory import format_preferences_block

        preferences_text = format_preferences_block(human_preferences)

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
    prev_card_text = format_prev_design_card(prev_design_card)
    if prev_card_text:
        prev_text = prev_text + "\n" + prev_card_text

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
- `start_positions`：{drone_count}个XY点，最小间距 ≥{_FLOOR}cm（pyfii core 碰撞底线，检查器会精确验证）；密集或分散是你的构图决定
- 首个正式 keyframe 路径通常控制在 180-360cm，不要从中心直接硬飞到全场边界
- 起飞后调用 `wait_until(drones, {start_time})` 对齐正式编舞窗口；不要直接写 `inittime()`
- 然后写 `prev = [(d.x, d.y, d.z) for d in drones]` 并开始正式 move2 动作"""
    else:
        segment_start_rule = """- 段首调用 `auto_init(drones)`，再写 `prev = [(d.x, d.y, d.z) for d in drones]`
- 不要直接写 `inittime()`；跨段对齐由 `auto_init` 处理"""

    if segment_upper in {"S04", "S05"}:
        assign_rule = "- S04/S05 错峰/分组大动作、密集承接：默认 **route-around + `prev = safe_move(drones, prev, geo, flying_ms, mode=\"wave\")`**——两组走不同 XY 带，安全分配+错峰+执行绑成一次调用，验证时序=飞行时序，清不开会自己抛错让你铺开点表。真对穿/大交叉不是默认选项；只有 motif 明确 mirror-cross 且点表足够稀疏时才试 `mode=\"relay\"`，relay 若抛错就改 route-around，不要继续硬凑。**切勿手搓 `move2`+`drone.delay` 凑错峰、也别照抄预算表 delay_ms 做对穿**。就近承接（无交叉）用 `targets = best_assign(prev, geo)` 后展开 per-drone loop；不错峰的同步大交换才用 `far_assign(prev, geo, min_path_cm=active_min_path_cm(flying_ms))`。每个 keyframe 最长路径有确定性上限（speed×时长内能飞完），规划报告会给精确 `[下限,上限]` 带——别设计飞不完的大动作。assign 类函数返回 targets 列表，不要拆 `perm/min_d`"
    else:
        assign_rule = "- 就近承接（无交叉）：`targets = best_assign(prev, geo)` 后展开 per-drone loop。**错峰/分组大动作、密集：优先 route-around + `prev = safe_move(drones, prev, geo, flying_ms, mode=\"wave\")`**——安全分配+错峰+执行绑成一次调用，验证时序=飞行时序，清不开会自己抛错。真对穿/大交叉只在 motif 明确 mirror-cross 且点表稀疏时试 `mode=\"relay\"`；relay 抛错就改两条 XY 带绕行。**切勿手搓 `move2`+`drone.delay` 凑错峰、别照抄预算表 delay_ms 做对穿**（mirror 小错峰照撞）。prev/geo 用完整 `(x,y,z)`；assign 类函数返回 targets 列表，不要拆 `perm/min_d`"

    segment_duration = float(end_time - start_time)
    if segment_upper == "S06":
        keyframe_rule = (
            "S06 尾声必须写 2 个明确 keyframe：先到中继/呼应姿态，再到最终署名位置；"
            "至少一个主体移动 keyframe 用 3000-3400ms 且多数无人机路径 90-140cm，"
            "第二个 keyframe 用 2600-3200ms 到最终署名；不要用短 move + fade/flash 冒充尾声，"
            "有效群体运动必须持续 ≥2.5s，段尾再用亮灯定格/渐隐铺满"
        )
        prev_update_rule = "每个 keyframe 后更新 prev；段尾更新 prev = [(t[0],t[1],t[2]) for t in targets]"
    elif segment_upper == "S04":
        keyframe_rule = (
            "S04 是抒情展开段：写 4-5 个短 keyframe，每个 2800-3200ms，"
            "至少 3 种颜色/灯光变化；每个 keyframe 用帧内可读构图和 per-drone loop，避免同步大块移动"
        )
        prev_update_rule = "每个 keyframe 后更新 prev；段尾更新 prev = [(t[0],t[1],t[2]) for t in targets]"
    elif segment_upper == "S05":
        keyframe_rule = (
            "S05 是高潮段：写 3 个强 keyframe，边界爆发→分组交换/回卷→有高度层的收束；"
            "至少 3 种颜色或明显爆闪变化，主体使用 far_assign 和 per-drone loop"
        )
        prev_update_rule = "每个 keyframe 后更新 prev；段尾更新 prev = [(t[0],t[1],t[2]) for t in targets]"
    elif segment_duration <= 5.0:
        budget_ms = int((segment_duration - 0.4) * 1000)
        keyframe_rule = (
            f"本段很短（{segment_duration:g}s）：时间预算 — 所有动作（move2 飞行 + 灯光）总时长 ≈{budget_ms - 400}-{budget_ms}ms，"
            "keyframe 数量自定（1 个长 move 或 2 个短 move 都行），关键是不留 >1s 的静止空窗；"
            "`min_path_cm=active_min_path_cm(flying_ms)` 让路径长度匹配飞行时长，不要只做 70-120cm 小挪动"
        )
        prev_update_rule = "段尾更新 prev = [(t[0],t[1],t[2]) for t in targets]"
    elif segment_duration <= 8.5:
        budget_ms = int((segment_duration - 0.6) * 1000)
        keyframe_rule = (
            f"本段是 {segment_duration:g}s 中短窗口：时间预算 — 动作总时长 ≈{budget_ms}ms，keyframe 数量自定，"
            "每个 keyframe 的 flying_ms 必须能装进预算（含灯光/错峰），避免段尾动作未完成；"
            "`far_assign(prev, geo, min_path_cm=active_min_path_cm(flying_ms))` 让真实运动贴满飞行时长"
        )
        prev_update_rule = "段尾更新 prev = [(t[0],t[1],t[2]) for t in targets]"
    else:
        keyframe_rule = f"2-4个利落 keyframe（点表 XY 间距硬下限 {_FLOOR}cm，密度是构图自由），用短促推进/交换/高度切层制造节奏"
        prev_update_rule = "段尾更新 prev = [(t[0],t[1],t[2]) for t in targets]"

    coordinate_hint = _format_coordinate_hint(drone_count, segment_upper)
    # 技能候选菜单（从 core/skills.py 注册表生成，按段落角色选用）。只进 user
    # prompt，不动冻结的 system prompt（§11.3 缓存约束）。
    skill_menu = skill_menu_for_role(role_class_for_segment(segment_upper, plan_role=intent or ""))
    # 动作质量预算：把 validator 质量门的确定性下限提前告诉模型，避免靠失败反馈
    # 反复试错（S03 这类长段曾磨 15+ 轮才发现"动作太小"）。用封顶时长取门的下限值，
    # 达到即过；长段建议给余量。与 _check_motion_quality 同源（motion_quality_minimums）。
    _qm = motion_quality_minimums(min(float(end_time - start_time), 6.0), drone_count)
    quality_budget = (
        f"## 动作质量预算（validator 质量门，确定性下限——第一次就设计到位，别靠反馈试错）\n"
        f"- 至少 {_qm['min_moving']}/{drone_count} 架离起始位 >{_qm['excursion_floor_cm']:.0f}cm（小范围抖动/单机慢挪不算）\n"
        f"- 中位路径 ≥{_qm['min_median_path_cm']:.0f}cm，中位位移 ≥{_qm['min_median_excursion_cm']:.0f}cm，"
        f"最大展开 ≥{_qm['min_max_excursion_cm']:.0f}cm（长段更高，建议设计到 110-150cm 留余量）\n"
        f"- 长段(≥10s)主体用大动作母题：`far_assign(prev, geo, min_path_cm=active_min_path_cm(flying_ms))` + ripple_move；"
        f"gentle 技能(breathing-transition/呼吸)只配短过渡或定格点缀，不能当长段主体\n"
        f"- 真实高度层：整段 Z range ≥90cm、每个主体 keyframe ≥3 个 Z 层（避免固定高度/车道退化）\n"
        f"- 大动作安全 = 碰撞门+动作质量门+活动门**一次同时满足**：默认**绕行 route-around**——两组换边但走不同空间带、同时飞、航线不相交（大动作+全员在动+无交叉，一次到位）。照这个范例改：\n"
        f"    `gids = split_groups(prev, mode='left_right')`  # 0=左组 1=右组\n"
        f"    `# 左组去对侧但目标集中在 y 上带、右组去对侧但集中在 y 下带 → 左右互换的张力，两条航线分居上下不相交`\n"
        f"    `geo = custom_points([...9 个点：左组 y 偏大、右组 y 偏小，整体大展开...], n=len(drones))`\n"
        f"    `delays = ripple_delays(prev, mode='by_index', step_ms=130)`\n"
        f"    `targets = safe_assign(prev, geo, delays=delays, flying_ms=2800)`  # 按真实错峰时序选无碰撞排列（与逐帧验证器同模型，错峰大动作首选）\n"
        f"    `prev = ripple_move(drones, targets, 2800, delays, colors=palette)`\n"
        f"  穿过同一中心区的真对穿是**少数刻意情况，仅当 motif 明确是 mirror-cross 时**才做：先把点表铺开，再试 `safe_move(..., mode='relay')` / `call_response_safe`；relay/call_response 若报告清不开，立刻改 route-around（两组不同 XY 带），不要继续加小错峰。其余大动作一律 route-around。单 keyframe 路径 ≤360cm，跨场拆多个 keyframe\n"
        f"  **碰撞门多半来自点表太密**：几何点要铺开占场（圆形 R≥85，两排同行≥70/行距≥120，散点任意两点 x差或y差≥60），far_assign 才有间距可挑出无碰撞排列；硬塞密集点表后指望 far_assign 救是没用的（点本身太近时连最优排列也 <{_FLOOR}cm）。密集造型留给短促/慢速小动作，大迁移用铺开的几何\n"
        f"- 避免刚性圆退化（圆/放射/中心/辐射主题尤其注意，否则 degradation 门反复打回）：不要让多数 keyframe 保持同一圆形且同一角序——"
        f"至少一个主体 keyframe 换非圆轮廓（直线/V/弧/星/双排/十字/署名造型），或用 `swap_assign`/`mirror_assign`/分组重组打乱角序；"
        f"**单纯扩缩半径或整体旋转(`rotate_assign`)仍是同序圆，不算变化**——圆形主题也要在 keyframe 之间真正换形或换序"
    )

    if is_land:
        user = f"""## {segment_id} ({start_time}-{end_time}s, 时长{end_time - start_time}s)
意图：{intent or segment_id}

{composition_text}
{preferences_text}
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
{preferences_text}
{prev_text}

{skill_menu}

{quality_budget}

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
- 几何主路径：整数坐标表或 math 表达式都必须包进 custom_points：`geo = custom_points([...], n=len(drones))`（sin/cos/pi 已导出；custom_points 负责裁剪+间距校验，comprehension 直接传给 best_assign/move2 会被打回），再 `best_assign/far_assign`；间距硬下限 {_FLOOR}cm，写点时直接保证（圆形 R≥85，两排同行≥70/行距≥120，散点任意两点 x差或y差≥60）；不要手动传 `min_xy_cm=90`，preflight 会按你写的高阈值精确拒绝；S02-S05 必须至少一个主体 keyframe 使用手写坐标表或 math 几何，禁止调用 `geo_wide_v/geo_arrow/geo_box/geo_diagonal/geo_wave/geo_grid`
- 正式段默认展开 per-drone loop，不要用 `move_group` 作为整段主结构：`move2(drone, target, flying_ms)` → `apply_light(drone, color, ticks)` → `drone.delay(flying_ms-ticks*100+100)`
- S02-S05 每段至少一个 keyframe 必须打破时间同步（同起同停会被节奏门打回），三选一：
  母题执行器 `prev = ripple_move(drones, targets, flying_ms, ripple_delays(prev), colors=palette)`（最省事，自动对齐）；
  起飞波次 `drone.delay(i * 120)` 写在 move2 之前；或到达波次 `move2(drone, target, flying_ms + (i % 3) * 250)`
- 灯光两种语体，按段落角色选一（也可混用）：
  (a) 运动驱动型：`apply_light(drone, color, 3-5)` 短提示 + `drone.delay(余量)` —— 灯光稀疏、动作主导；
  (b) 定格/呼吸灯光型（dntg 式）：先把移动 keyframe 安全飞完，再用 `light_wave`/`breathe_group`/`fade_group` 在造型上铺灯光时间。**不要在同一个 `move2(..., flying_ms)` 循环里写 `apply_light(..., flying_ms // 100)`**；在本 API 里这会被串行计算成超预算，preflight 会拒绝。
- 个体色彩身份（dntg 视觉语法）：群舞/交换 keyframe 给每架机（或每对镜像机）自己的色相，如 `palette = ["#ff4444","#ffaa00","#ffee44","#44ff88","#44ddff","#4466ff","#aa44ff","#ff44aa","#ffffff"]` 后 `apply_light(drone, palette[i], ...)` —— 观众才能跟踪个体换位；全队统一色只留给宣言时刻（高潮齐爆、署名定格）
- 定格 pose 合法：飞到造型后保持静止展示（如署名/符号阵）可以超过 1s，**但定格期间必须灯亮**（apply_light 或 TurnOnAll 持续覆盖）；黑灯静止才会被判低活动
- 不要重新质疑 `move2/apply_light/delay` 的语义，也不要在回答中推导 API；按上述顺序写代码即可，验证器会负责轨迹检查
- `move_group/move_group_staggered` 只作为 smoke/兜底工具；S01-S06 纯 helper 执行会被打回。卡农/错峰用母题执行器（safe_move/call_response_safe/ripple_move/chain_follow_safe/follow_chain 不算兜底，算正式编舞），或在 per-drone loop 内按 `i % group_mod` 写小 delay，并保留每架机自己的灯光/等待
- 禁止只给单架 `drones[i]` 操作；使用 `for d in drones:` 或等价 per-drone loop。但可以在 loop 内做差异化：如 `d.delay(i * stagger_ms)` 交错启动, `if i == 0: apply_light(d, special_color, t)` 焦点机, `move2(d, (tx, ty, tz + dz*sin(i)), t)` Z 个性——区别对待不等于跳过
- 主体 move2 通常用 2600-3600ms；不要用 4500ms+ 超慢移动凑时长，段尾由 auto_init 压缩
- 快节奏必须可完成：单个 2600-3200ms keyframe 的 3D 路径通常控制在约 180-360cm；不要用 2000-2400ms 硬飞 500cm 跨场路径
- 如果段长需要覆盖，不要拉长单个 move2；用多个可完成的快 keyframe、分组错峰、高度切层，或**亮灯定格**承接——图形到位后保持灯亮定格 0.8-2s 让观众读图（dntg 节奏=移动→定格→移动，dntg 全片 57% 时间是定格展示）；黑灯静止才算低活动
- 3s 以上 keyframe 不要写 `min_path_cm=90/100`；用 `flying_ms = 3000` 后 `targets = far_assign(prev, geo, min_path_cm=active_min_path_cm(flying_ms))`
- 安全距离按 XY 看：不要把同一 XY 的不同 Z 当成安全分离；XY 间距硬下限 {_FLOOR}cm（pyfii core 碰撞线，检查器精确验证），密集造型配合短路径慢速；复杂交换交给 `far_assign`
- 错峰 `delay(i * 150)` 是**波次**工具（各机飞向不重叠目标、先后起步），不是对穿安全工具——对穿/大动作的安全见上方“大动作安全”一条（默认 route-around，刻意 mirror-cross 才试 safe_move(mode='relay') / call_response_safe；失败就绕行）
- **错峰/分组/密集大动作优先用 `prev = safe_move(drones, prev, geo, flying_ms, mode="wave")` + route-around 点表**：融合安全分配+错峰+执行为一次调用，用来验证无碰撞的时序就是真正飞的时序。真对穿/大交叉只在 motif 明确 mirror-cross 且点表稀疏时试 `mode="relay"`；relay/call_response 抛错说明几何装不下，改两条 XY 带绕行，别继续硬凑。**切勿手搓 `move2`+`drone.delay` 凑错峰或照抄预算表 delay_ms 做对穿**（“算着安全、实跑相撞”的直接来源）。
- 分配函数家族（safe_move 内部已用；只有自己手动组合时序时才直接调）：`best_assign(prev, geo)` 就近收束 / `far_assign(prev, geo, min_path_cm=...)` 大幅交换（同步锁步模型）/ `safe_assign(prev, geo, delays=delays, flying_ms=...)` 按真实分时轨迹挑无碰撞排列（best/far 假设全员同步直线，错峰段会“算着安全、实跑相撞”）；组完时序后用 `ok, min_cm, pair = verify_timed_clearance(prev, targets, delays=delays, flying_ms=...)` 自检（直接解包 3 元组）/ `rotate_assign(prev, geo, steps=1)` 整体漩涡旋转（同构环形刚体旋转天然安全，steps 可负；非环形/对齐两列旋转会贴 {_FLOOR}cm 同步路径门）/ `mirror_assign(prev, geo)` 镜像对穿（**无 axis 参数**；同步路径门跳过它，但对穿真的交叉——必须足量顺序错峰让一架先离开交叉点另一架才到，小错峰照撞，分时门与 validator 都逐帧核验，不是免检；拿不准就 safe_assign 验真）/ `swap_assign(prev, geo, axis='x'|'y')` 半场互换（有 axis；同步直线检查，对齐两列会贴硬下限）/ `keep_assign(prev, geo)` 身份保持（drone i 固定走第 i 个目标，palette 叙事用）。左右对答/换位默认 route-around（两组不同带同时飞，见“大动作安全”），只有刻意要中心对穿才 mirror_assign+大错峰
- 波次计算器（从当前队形推导时间编排，动序即光序）：`delays = ripple_delays(prev, mode='center_out'|'sweep_x'|'sweep_y'|'spiral'|'by_index', step_ms=120-250, reverse=False)` 波次延迟表；`spatial_ranks(prev, mode=...)` 波次序号（可按 rank 配色）；`gids = split_groups(prev, mode='left_right'|'front_back'|'inner_outer'|'alternate')` 0/1 分组。注意：环形/等距队形上 center_out 全员同距=同一波（退化为同步起步），想要可见波次改用 spiral/sweep_x/sweep_y/by_index
- 动作母题执行器（内部已做 per-drone 灯光+段尾自动对齐，免回正算术，计入时间错峰门）：
  `prev = ripple_move(drones, targets, flying_ms, delays, colors=palette, hold_ticks=4)` 波次推进，先动先亮，总时长 max(delays)+flying_ms；
  `prev = call_response_safe(drones, prev, geo, flying_ms, gap_ms=700, relay_split='left_right', colors=('#ff6040','#4060ff'))` 安全分组问答——只写稀疏 geo，本地按真实接力时序 safe_assign 后执行；S02 8.7s 推荐 flying_ms=4000/gap_ms=700；
  `prev = chain_follow_safe(drones, control_points, hop_ms=650, lag_hops=1, spacing_cm=65, colors=palette)` 首选链式跟随/蛇形——只写 2-5 个 control_points（起点→中继→终点），本地扩成安全波点再执行 follow_chain；总时长 = ((len(drones)-1)*lag_hops+1+extra_hops)*hop_ms，默认 9 机约 10*hop_ms；
  `prev = follow_chain(drones, waypoints, hop_ms, lag_hops=1, colors=palette)` 底层链式跟随——只有在你已手写足够稀疏的 waypoints 时使用；需要 len(waypoints) ≥ (机数-1)*lag_hops+1，相距 lag 的波点 XY ≥{_FLOOR}cm（preflight/函数校验报数），总时长 = len(waypoints)*hop_ms；
  `group_relay(...)` 是底层接力执行器：只有 targets 已用 matching relay_delays 走过 safe_assign 才直接调；普通问答请用 call_response_safe，别写 group_relay(best_assign(...))
- 飞行中持续变色（dntg 灯光精髓，强烈推荐——纯色保持会让色彩单一）：给上述任一执行器加 `gradient_to=palette2`（与 colors 同形的第二组色），每架机在亮灯窗口内 colors[i]→palette2[i] 逐 tick 渐变，不增加耗时、不破坏对齐；如 `ripple_move(drones, targets, flying_ms, delays, colors=warm, hold_ticks=12, gradient_to=cool)` 让无人机边飞边从暖色渐变到冷色。light_wave 同样支持 gradient_to（定格队形上的流光）
- 灯光母题（灯光绑定编舞意图：扩张配中心光波、问答配双色、收尾配齐闪/渐隐；同一份 delays 喂 ripple_move 和 light_wave 就是"先动的先亮"）：
  `light_wave(drones, delays, palette, hold_ticks=6)` 静止队形上的光波涟漪（定格展示首选，耗时 max(delays)+hold*100）；
  `fade_group(drones, c1, c2, duration_ms)` 全队渐变 / `fade_rgb(drone, c1, c2, steps)` 单机渐变（dntg 式持续变色）；
  `breathe_group(drones, color, cycles, period_ms)` 呼吸明暗（定格持灯）；
  `flash_group(drones, color, times=3, on_ms=250, off_ms=150, alt_color=...)` 同步频闪（强拍/结尾宣言，结束自动回亮）；
  颜色参数 '#hex'/(r,g,b)/列表皆可；这些调用都计入灯光门
- `beat_ms(bpm, beats)` 把时长贴到音乐拍：`flying_ms = beat_ms(bpm, 4)` 即 4 拍一个 keyframe，灯光/频闪用 beat_ms(bpm, 0.5/1) 跟拍
- 高度层必须真实混合：每个主体 keyframe 至少 3 个 Z 层，整段 Z range ≥90cm；不要全队同一高度平面
- 帧内可读构图（dntg 视觉语法）：每个 keyframe 的点表本身应当是观众一眼可读的图形——镜像对（点两两穿过构图中心配对，如 (cx+dx,cy+dy) 配 (cx-dx,cy-dy)）、点对称、或可辨轮廓（直线/V/弧/环/双排/点阵）；随机散点在 7-9 机规模下读作噪声。非对称与变奏放在 **keyframe 之间**（换轮廓、转方向、变密度），不放在帧内
- 编舞词汇（每段至少用一种，并在 #beat/#formation 标明）：波次涟漪 (ripple_move/light_wave), 链式跟随 (chain_follow_safe/follow_chain), 安全分组问答 (call_response_safe), 交错启动 (delay(i*ms)), Z 个性 (move2 内 +dz*sin(i)), 分组对比 (两组不同几何/灯光), 焦点机 (1-2 架独立轨迹), 中心迁移, 密度呼吸, 灯光渐变 (fade_group/breathe_group 或 range()+TurnOnAll((r,g,b)) 呼吸), 同步频闪收尾 (flash_group)；全段匀速单色无差异会被节奏门打回
- `d.TurnOnAll((r,g,b))` 直接接受 RGB 三元组 (0-255)：`d.TurnOnAll((255,255,255))`=白色。可在 per-drone loop 内做灯光渐变呼吸: `for a in range(30): d.TurnOnAll((int(128+127*sin(a*pi/15)), int(60+50*sin(a*pi/10)), 40)); d.delay(100)` — 30 ticks = 3秒渐变（pi 已导出，不要写 π）
- 渐变必须塞进飞行窗口：每个 keyframe 内 `灯光 ticks*100 + delay_ms ≈ flying_ms`；动作完成后不要再原地长亮灯（无人机静止亮灯 >1s 会被判低活动打回）。30-tick 渐变只配 3000ms 以上的 keyframe
- LAND 前如果整体真实动作还没超过 60s，系统会追加 S07/S08 等正式段继续编舞；不要靠当前段硬等待
- {prev_update_rule}
- ## 时间预算（不填满直接打回！）
段长: {end_time - start_time}s（{start_time}-{end_time}s）。`move2 飞行 + 亮灯定格 + delay` 之和必须≈ {(end_time - start_time - 0.5) * 1000:.0f}ms。写完所有 keyframe 后**自己加总时长**，不够就追加亮灯定格或短 keyframe——**不要写完 2-3 个 keyframe 就收手**
**窗口必须填满**（验证器硬校验）：段尾时间游标要落在窗口尾 ±（-1.0s/+1.5s）内；欠填会把后续段推离音乐 cue 直接打回
母题耗时是确定的，直接加总贴满窗口：ripple_move=max(delays)+flying_ms / call_response_safe=2*flying_ms+gap_ms / chain_follow_safe=((len(drones)-1)*lag_hops+1+extra_hops)*hop_ms / follow_chain=len(waypoints)*hop_ms / group_relay=2*flying_ms+gap_ms / light_wave=max(delays)+hold_ticks*100 / fade_group=duration_ms / breathe_group=cycles*period_ms / flash_group=times*(on_ms+off_ms)
示例: 2个move2各2800ms + 每次到位后亮灯定格1700ms → 9000ms，观众有时间读图 ✓；3个move2各3000ms 全程飞不停 → 覆盖但观众读不到任何图形 △
反例: 1个move2 8000ms 超慢飘移 ✗；黑灯静止凑时长 ✗（低活动打回）；keyframe 加完离窗口尾还差 3s 不管 ✗（窗口填充门打回）
- 禁止 inittime/VelXY/import
- 只输出代码片段（4空格缩进）"""

    if feedback:
        user += f"\n\n## 上一轮反馈（若与更早历史反馈矛盾，以本条最新为准）\n{feedback}\n根据反馈修正。"

    return system, user


def _format_coordinate_hint(drone_count: int, segment_id: str) -> str:
    if int(drone_count) != 9:
        return "坐标写数字三元组或 math 表达式（如 [(280+170*cos(2*pi*i/len(drones)), 280+170*sin(2*pi*i/len(drones)), 160) for i in range(len(drones))]）；不要写省略号(...)"

    start_hint = ""
    if segment_id == "S01":
        start_hint = (
            "起飞队形是整场演出的第一个视觉语句，完全由你设计，并播种全局母题（后续段落要承接它）；"
            f"不要套用任何固定网格或模板队形。硬约束只有：XY {_XY}，起飞点最小 XY 间距 ≥{_FLOOR}cm（检查器会精确验证）；"
            "起飞高度可各机不同"
        )

    discipline = (
        f"9机手写坐标表：坐标任意整数即可，不要凑 50 的倍数（场地 560x560，中心是 280——50 网格永远写不出对称构图）；构图锚点自己定：对称构图围绕 (280,280) 写 280±k，偏心/迁移构图把重心放任意位置都可以；XY {_XY}，Z 在 {_Z} 内至少 3 层；"
        f"间距经验法则（custom_points 硬下限 {_FLOOR}cm，写点时直接保证）：圆形 R≥85（弦距≥58cm）；两排/多排 同行间距≥70、行距≥120；散点 任意两点 x差 或 y差 ≥60；"
        "禁止 jitter_points；不需要手动传 min_xy_cm"
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
