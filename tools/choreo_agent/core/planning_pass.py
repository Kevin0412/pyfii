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
    music_brief: Mapping[str, Any] | None = None,
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
    music_text = ""
    if music_brief:
        from .music_brief import format_segment_music_hint

        music_text = format_segment_music_hint(music_brief, start_time, end_time)

    return f"""## 规划 {segment_id} ({start_time}-{end_time}s, 时长{end_time-start_time}s)
意图: {intent}

{composition_text}

{music_text}

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
      "light_ticks": 4,
      "assign": "best"
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
约束: targets总数={drone_count}, shape=[{target_example}], XY 0-560cm, Z 80-250cm, target 点表 XY 间距硬下限 51cm（pyfii core 碰撞线，检查器精确验证）；密度是构图自由，不要为了凑大间距放弃造型。速度20-200, 加速度50-400, 推荐速度150-200、加速度260-400；light_ticks 两种语体：3-5（运动驱动型短提示）或 duration_s*10（灯光时钟型，灯光占满飞行窗口）。
章法约束: JSON 里的 feel/targets/light_color 必须服务全局章法；不要随机换题，不要连续重复同一种退化队形。
assign 字段（可选，默认 best）: "best"收束 / "far"大交换 / "rotate"漩涡(可加 "rotate_steps") / "mirror"对穿(检查器会提醒错峰) / "swap"半场互换 / "keep"身份保持——转场即编舞，按意图声明，检查器按声明的映射验算。
输出纪律: 直接给 JSON；不要写距离证明、不要手算两两间距、不要自问自答。规划检查器会回报精确间距/路径/时长数字，如有违规你会收到报告再修正。

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
    # 短/长对比的 phrase 权重：人类作品的大动作按 phrase 走，accent 短促、phrase 延展，
    # 不是均匀切片（见 doc/human_choreography_distillation.md）。
    weights = {
        2: [0.40, 0.60],
        3: [0.25, 0.43, 0.32],
        4: [0.22, 0.30, 0.22, 0.26],
        5: [0.18, 0.24, 0.16, 0.24, 0.18],
    }.get(count) or [1.0 / count] * count
    durations = [active * w for w in weights]
    lines = [
        "Keyframe 合同:",
        f"- 必须输出 exactly {count} 个 keyframes；不要多也不要少。",
        f"- {note}",
        "- start_s 必须递增；不要所有 keyframe 等长——按推荐时间表保持明显短长对比，"
        "短的是 accent（利落推进/交换），长的是 phrase（大幅展开/换位）。",
        "- 图形到位后留 0.8-2s 亮灯定格让观众读图（移动→定格→移动的节奏）；duration_s 里包含定格时间。",
        "- 灯光节奏与 feel 匹配：accent 用 2-3 ticks 强色，延展 phrase 用 5-8 ticks；"
        "final 代码可在同一 keyframe 内连续两次 apply_light 换色做渐变。",
        "- 推荐时间表（可 ±0.4s 微调，但保持短长对比）:",
    ]
    cursor = float(start_time)
    for i, dur in enumerate(durations, start=1):
        lines.append(f"  - k{i}: start_s={cursor:.1f}, duration_s={dur:.1f}")
        cursor += dur
    return "\n".join(lines)


def _format_safe_coordinate_seeds(drone_count: int) -> str:
    return f"""坐标纪律（{int(drone_count)} 机点表）:
- JSON 里的每个 targets 必须是 {int(drone_count)} 个算好的数字三元组；JSON 不能包含公式/变量/省略号。
- 队形可以按数学概念设计（圆形/弧线/斜线/波浪——半径、相位、Z 起伏自定），取整后填入数字即可；公式写法留到编码阶段（final 代码里 sin/cos/pi 可直接用）。
- 不要手算两两间距——系统会用确定性检查器回报每个 keyframe 的精确间距/路径数字，按数字修正即可。
- 帧内可读构图：每个 keyframe 的 targets 本身要是可读图形——镜像对（点两两穿过构图中心配对）、点对称、或可辨轮廓（线/V/弧/环/双排/点阵）；随机散点读作噪声。变奏放在 keyframe 之间。
- 把注意力放在编舞：中心偏移、稀疏/密集呼吸、Z 层关系、左右/前后交换、灯光渐变；不要连续 keyframe 复制同一队形。"""


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


# 安全阈值：51cm 是 pyfii core 碰撞警告硬下限，点表与转场路径同一条线。
PLAN_MIN_XY_FLOOR_CM = 51.0
PLAN_PATH_SPACING_FLOOR_CM = 51.0


def evaluate_plan_safety(
    plan: Mapping[str, Any],
    prev_state: Sequence[Sequence[float]],
    drone_count: int = 7,
) -> tuple[bool, str]:
    """Deterministic calculator: numeric safety report for a JSON plan.

    模型不做距离数学；这里逐 keyframe 计算并回报：
    - targets 数量 / 数字三元组 / XY 0-560、Z 80-250 边界
    - keyframe 内最小 XY 间距及最差点对（<51cm 违规，51-90 标记为刻意密集）
    - 经 best_assign 最优分配后的路径最小间距（连最优分配都 <55cm 则几何本身不可救）
    - 按 speed/accel 估算最长飞行时间 vs keyframe 时长（完不成则违规）
    Returns (ok, report); report 同时用作修正反馈和编码阶段参考。
    """
    from .motion_math import clamp_accel, clamp_speed, dist3, flight_time_ms

    drone_count = int(drone_count)
    violations: list[str] = []
    lines = ["## 规划检查报告 (确定性计算结果，不要自己重算)"]
    current_prev = [(float(p[0]), float(p[1]), float(p[2])) for p in prev_state]
    keyframes = plan.get("keyframes") or []
    if not isinstance(keyframes, Sequence) or not keyframes:
        return False, "## 规划检查报告\n- 违规: 计划里没有 keyframes"

    for kf_i, kf in enumerate(keyframes, start=1):
        if not isinstance(kf, Mapping):
            violations.append(f"k{kf_i}: keyframe 必须是对象")
            continue
        lines.append(f"--- k{kf_i} ---")
        targets = kf.get("targets") or []
        if len(targets) != drone_count:
            msg = f"k{kf_i}: targets 数量 {len(targets)} != {drone_count}"
            violations.append(msg)
            lines.append(f"- 违规: {msg}")
            continue
        try:
            pts = [(float(t[0]), float(t[1]), float(t[2])) for t in targets]
        except (TypeError, ValueError, IndexError):
            msg = f"k{kf_i}: targets 必须全部是数字三元组"
            violations.append(msg)
            lines.append(f"- 违规: {msg}")
            continue

        oob = []
        for i, (x, y, z) in enumerate(pts):
            parts = []
            if not 0 <= x <= 560:
                parts.append(f"x={x:g}")
            if not 0 <= y <= 560:
                parts.append(f"y={y:g}")
            if not 80 <= z <= 250:
                parts.append(f"z={z:g}")
            if parts:
                oob.append(f"d{i}({', '.join(parts)})")
        if oob:
            msg = f"k{kf_i}: 坐标越界 {'; '.join(oob)} — XY 0-560, Z 80-250"
            violations.append(msg)
            lines.append(f"- 违规: {msg}")

        min_xy, pair = _min_xy_pair(pts)
        if min_xy < PLAN_MIN_XY_FLOOR_CM:
            msg = (
                f"k{kf_i}: 点表内最小 XY 间距 {min_xy:.0f}cm (d{pair[0]}-d{pair[1]}) "
                f"< 硬下限 {PLAN_MIN_XY_FLOOR_CM:.0f}cm — 拉开这两个点"
            )
            violations.append(msg)
            lines.append(f"- 违规: {msg}")
        else:
            lines.append(f"- 点表最小 XY 间距 {min_xy:.0f}cm (d{pair[0]}-d{pair[1]}) ≥ 51cm OK")

        assign_kind = str(kf.get("assign", "best") or "best").lower()
        assigned, path_md, kind_note = _intent_assignment(
            assign_kind, current_prev, pts, kf
        )
        path_lengths = sorted(
            dist3(current_prev[i], assigned[i]) for i in range(drone_count)
        )
        median_path = path_lengths[drone_count // 2]
        max_path = path_lengths[-1]
        synced_flagged = False
        if path_md is None:
            lines.append(f"- {kind_note}")
        elif path_md < PLAN_PATH_SPACING_FLOOR_CM:
            # opt_md = best_assign（最大化间距）能达到的最优转场间距上限。
            # best/far/swap 的 path_md 本身已是该最优值（_intent_assignment 走 best_assign）；
            # keep/rotate 的声明映射可能比最优差，单独探一次最优才能区分两种处方：
            #   opt_md ≥ 51 → 存在无碰撞排列，换 far_assign 即可救（点表不动）。
            #   opt_md < 51 → 连最优排列都不过硬下限，点本身太近，far/换排列都无效，
            #                 只能 mirror+错峰（对穿，免同步路径门）或显著拉开点表。
            from .best_assign import best_assign as _best
            if assign_kind in ("best", "far", "swap"):
                opt_md = path_md
            else:
                prev_xy = [(p[0], p[1]) for p in current_prev]
                pts_xy = [(t[0], t[1]) for t in pts]
                opt_md = _best(prev_xy, pts_xy)[1]
            if opt_md >= PLAN_PATH_SPACING_FLOOR_CM:
                hint = (
                    f"最优排列可达 {opt_md:.0f}cm≥51（当前 {assign_kind} 映射只有 {path_md:.0f}cm，"
                    "不是最优）——把本次转场改成 "
                    "`far_assign(prev, geo, min_path_cm=active_min_path_cm(flying_ms))` "
                    "并在 JSON 声明 assign:\"far\"（取最大间距的无碰撞排列，大动作首选）；点表不动"
                )
            else:
                hint = (
                    f"连最优排列也只有 {opt_md:.0f}cm<51——这些点本身太近，换排列/far_assign 都无效。"
                    "若是左右对答/对穿，改用 `mirror_assign(prev, geo)`+错峰"
                    "（免同步路径门，validator 逐帧保安全）；"
                    "否则显著拉开本 keyframe 点表间距，或用 by_index 错峰让各机不同时刻过交叉点"
                )
            msg = (
                f"k{kf_i}: {kind_note}转场路径最小间距只有 {path_md:.0f}cm "
                f"< {PLAN_PATH_SPACING_FLOOR_CM:.0f}cm — " + hint
            )
            violations.append(msg)
            lines.append(f"- 违规: {msg}")
            synced_flagged = True
        else:
            lines.append(
                f"- {kind_note}路径最小间距 {path_md:.0f}cm OK；路径长度 中位 {median_path:.0f}cm / 最长 {max_path:.0f}cm"
            )

        # 物理上限 20-200 / 50-400：计划里超限的 speed/accel 按真实能力收紧后再算可行性
        speed = float(clamp_speed(_positive_float(kf.get("speed_cm_s"), 170.0)))
        accel = float(clamp_accel(_positive_float(kf.get("accel_cm_s2"), 320.0)))
        duration_ms = _positive_float(kf.get("duration_s"), 3.0) * 1000.0
        max_ft = max(
            flight_time_ms(dist3(current_prev[i], assigned[i]), speed, accel)
            for i in range(drone_count)
        )
        if max_ft > duration_ms * 1.02:
            msg = (
                f"k{kf_i}: 最长飞行 {max_ft:.0f}ms > 时长 {duration_ms:.0f}ms "
                f"(speed={speed:g}, accel={accel:g}) — 缩短最长路径或提高 speed/duration"
            )
            violations.append(msg)
            lines.append(f"- 违规: {msg}")
        else:
            lines.append(f"- 最长飞行 {max_ft:.0f}ms ≤ 时长 {duration_ms:.0f}ms OK")

        # 分时碰撞门：按标准 by_index 错峰回放真实轨迹的两两最小 XY，与逐帧 validator 同模型。
        # 同步检查(path_md)对 mirror 对穿被跳过、对错峰段偏乐观——"同步算安全、实跑相撞"正是密集段
        # 反复返工的根因（碰撞在 validator 阶段才暴露）。这一步在规划阶段就用 validator 的分时模型挡下。
        timed_md = _timed_path_min(
            [(p[0], p[1]) for p in current_prev],
            [(t[0], t[1]) for t in assigned],
            duration_ms,
        )
        if timed_md >= PLAN_PATH_SPACING_FLOOR_CM:
            lines.append(f"- {kind_note}分时间距 {timed_md:.0f}cm OK")
        elif synced_flagged:
            # 同步门已就同一处问题报违规；分时门只补充信息，不重复计违规。
            lines.append(f"- (同步门已报违规) 分时间距同样只有 {timed_md:.0f}cm")
        else:
            # 分时门的独有价值：同步门跳过(mirror 对穿)或判安全、但真实错峰回放仍相撞的情形——
            # "同步算安全、实跑相撞"正是密集段反复返工的根因，在规划阶段就用 validator 的分时模型挡下。
            msg = (
                f"k{kf_i}: 分时轨迹(标准错峰回放)最小间距只有 {timed_md:.0f}cm "
                f"< {PLAN_PATH_SPACING_FLOOR_CM:.0f}cm — 默认/by_index 错峰下实跑会撞(validator 逐帧同此模型)。"
                "要么改用 `safe_assign(prev, geo, delays=delays, flying_ms=...)`（按真实错峰挑无碰撞排列）；"
                "要么让交叉的机体顺序错开（group_relay 或加大 step_ms，使每架在其镜像/对手到达交叉点前已离开）。"
                "不要削门。"
            )
            violations.append(msg)
            lines.append(f"- 违规: {msg}")

        # 可行路径带（只读提示，不是新门）：消除高潮段"动作太大→飞不完/碰撞 ↔ 太小→动作质量门"
        # 的来回震荡。下限=动作质量门的最大展开下限；上限=本 speed/accel 在本时长内能完成的最长路径
        # （反解既有 flight_time_ms≤duration*1.02 的可行性检查，同一夹紧速度/加速度，不改任何门）。
        from .validator import motion_quality_minimums
        band_lo = float(motion_quality_minimums(duration_ms / 1000.0, drone_count)["min_max_excursion_cm"])
        lo_d, hi_d = 0.0, 850.0
        for _ in range(22):
            mid = (lo_d + hi_d) / 2.0
            if flight_time_ms(mid, speed, accel) <= duration_ms * 1.02:
                lo_d = mid
            else:
                hi_d = mid
        band_hi = lo_d
        if band_lo > band_hi:
            lines.append(
                f"- k{kf_i} 可行路径带: 窗口太短/速度太低，装不下最低动作量"
                f"（下限 {band_lo:.0f} > 上限 {band_hi:.0f}cm）——提高 duration_s 或 speed"
            )
        else:
            lines.append(
                f"- k{kf_i} 可行路径带: 把最长路径放在 [{band_lo:.0f},{band_hi:.0f}]cm"
                f"（≤{band_hi:.0f} 才能在 {duration_ms:.0f}ms@speed={speed:g} 完成，≥{band_lo:.0f} 满足动作质量门）"
            )

        current_prev = assigned

    ok = not violations
    if ok:
        lines.append("结论: PASS — 所有 keyframe 间距/路径/时长可行")
    else:
        lines.append(f"结论: {len(violations)} 项违规 — 只修正违规项，其余保持不变")
    return ok, "\n".join(lines)


def build_plan_revision_prompt(plan: Mapping[str, Any], report: str, segment_id: str) -> str:
    """Compact revision round: prior plan + checker numbers → corrected JSON."""
    plan_json = json.dumps(plan, ensure_ascii=False)
    return f"""## 修正 {segment_id} 规划 JSON

你上一版计划:
```json
{plan_json}
```

{report}

只修正报告标记为“违规”的 keyframe（targets/speed/duration），其他 keyframe 和字段保持不变。
不要自己验算距离 — 报告里的数字就是精确结果。
只输出完整修正后的 JSON，不解释。"""


def _intent_assignment(kind, current_prev, pts, kf):
    """按声明的 assign 意图计算映射并给出可检查的路径间距。

    与 project_template/scripts/function.py 的同名分配函数保持同一映射逻辑
    （keep/rotate/mirror）；best/far/swap 用最优分配检查（far/swap 为保守近似）。
    mirror 的同步直线间距天然趋零（设计就是对穿），跳过该检查，
    由错峰 + validator 逐帧负责真实安全。
    Returns (assigned, path_md | None, note)。
    """
    from .best_assign import best_assign as _assign

    prev_xy = [(p[0], p[1]) for p in current_prev]
    pts_xy = [(t[0], t[1]) for t in pts]
    n = len(pts)

    if kind == "keep":
        assigned = list(pts)
        md = _synced_path_min(prev_xy, pts_xy)
        return assigned, md, "keep_assign(身份保持) "
    if kind == "rotate":
        steps = int(_positive_float(kf.get("rotate_steps"), 1.0))
        prev_order = _angle_rank(prev_xy)
        target_order = _angle_rank(pts_xy)
        assigned = [None] * n
        for rank, drone_i in enumerate(prev_order):
            assigned[drone_i] = pts[target_order[(rank + steps) % n]]
        # 时间同步间距：刚体旋转里相邻弦共享端点但从不同时到达——
        # 几何线段距离会误判为 0，必须按同一 t 采样。
        md = _synced_path_min(prev_xy, [(t[0], t[1]) for t in assigned])
        return assigned, md, f"rotate_assign(steps={steps}) "
    if kind == "mirror":
        cx = sum(t[0] for t in pts) / n
        cy = sum(t[1] for t in pts) / n
        used: set[int] = set()
        assigned = []
        for px, py in prev_xy:
            rx, ry = 2 * cx - px, 2 * cy - py
            best_j = min(
                (j for j in range(n) if j not in used),
                key=lambda j: (pts[j][0] - rx) ** 2 + (pts[j][1] - ry) ** 2,
            )
            used.add(best_j)
            assigned.append(pts[best_j])
        return assigned, None, (
            "mirror_assign(镜像对穿)：同步直线间距不适用——必须错峰 "
            "`drone.delay(i * 150)`，validator 会逐帧验证真实间距"
        )
    # best / far / swap：最优分配检查（far/swap 保守近似）
    perm, md = _assign(prev_xy, pts_xy)
    assigned = [pts[i] for i in perm]
    note = "" if kind == "best" else f"{kind}_assign(按最优分配近似检查) "
    return assigned, md, note


def _synced_path_min(prev_xy, target_xy, steps: int = 50) -> float:
    """时间同步的转场最小 XY 间距：所有机同一 t 沿直线推进时的两两最小距离。"""
    n = len(prev_xy)
    md = 1e9
    for s in range(steps + 1):
        t = s / steps
        positions = [
            (
                prev_xy[i][0] * (1 - t) + target_xy[i][0] * t,
                prev_xy[i][1] * (1 - t) + target_xy[i][1] * t,
            )
            for i in range(n)
        ]
        for i in range(n):
            for j in range(i + 1, n):
                d = (
                    (positions[i][0] - positions[j][0]) ** 2
                    + (positions[i][1] - positions[j][1]) ** 2
                ) ** 0.5
                if d < md:
                    md = d
    return md


def _timed_path_min(prev_xy, target_xy, duration_ms, fps: int = 60) -> float:
    """分时转场最小 XY 间距：假设标准 by_index 错峰(每机 delay=i*step)，各机在自己的飞行窗口内
    沿直线推进，按 60fps 采样取两两最小——与 project_template/scripts/function.py._timed_min_xy
    及 validator 的逐帧 XY 模型一致。用于规划阶段挡下"同步算安全、实跑相撞"的设计（尤其 mirror 对穿，
    同步直线必撞、只靠错峰救——这里就按错峰回放验真）。"""
    n = len(prev_xy)
    if n < 2 or duration_ms <= 0:
        return 1e9
    # 标准错峰：总错峰跨度约占窗口 25%(上限 1200ms)，单机飞行占剩余窗口。
    span = min(duration_ms * 0.25, 1200.0)
    step = span / max(1, n - 1)
    delays = [i * step for i in range(n)]
    flying = max(1.0, duration_ms - span)
    spans = [delays[i] + flying for i in range(n)]
    tmax = max(spans)
    steps = max(8, min(300, int(tmax / 1000.0 * float(fps))))
    md = 1e9
    for s in range(steps + 1):
        t = tmax * s / steps
        pos = []
        for i in range(n):
            if t <= delays[i] or flying <= 0:
                r = 0.0
            elif t >= spans[i]:
                r = 1.0
            else:
                r = (t - delays[i]) / flying
            pos.append((
                prev_xy[i][0] + (target_xy[i][0] - prev_xy[i][0]) * r,
                prev_xy[i][1] + (target_xy[i][1] - prev_xy[i][1]) * r,
            ))
        for i in range(n):
            for j in range(i + 1, n):
                d = ((pos[i][0] - pos[j][0]) ** 2 + (pos[i][1] - pos[j][1]) ** 2) ** 0.5
                if d < md:
                    md = d
    return md


def _angle_rank(points_xy):
    import math as _math

    cx = sum(p[0] for p in points_xy) / len(points_xy)
    cy = sum(p[1] for p in points_xy) / len(points_xy)
    return [
        i
        for i, _ in sorted(
            enumerate(points_xy),
            key=lambda item: _math.atan2(item[1][1] - cy, item[1][0] - cx),
        )
    ]


def _min_xy_pair(points: Sequence[tuple[float, float, float]]) -> tuple[float, tuple[int, int]]:
    md = 1e9
    pair = (0, 0)
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            d = (
                (points[i][0] - points[j][0]) ** 2
                + (points[i][1] - points[j][1]) ** 2
            ) ** 0.5
            if d < md:
                md = d
                pair = (i, j)
    return md, pair


def _positive_float(value: Any, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if result > 0 else default


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

        lines.append(
            f"\n--- Keyframe {kf_i+1} ({feel}) assign={kf.get('assign', 'best')} ---"
        )
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
- 几何主路径：整数坐标表或 math 表达式都必须包进 custom_points：`geo = custom_points([(280+170*cos(2*pi*i/len(drones)), 280+170*sin(2*pi*i/len(drones)), 160+25*sin(i)) for i in range(len(drones))], n=len(drones), min_xy_cm=90)`（sin/cos/pi 已导出，不要写 π；comprehension 直接传给 best_assign/move2 会被打回；9 机圆形 R≥150 弦距≈116cm），再 `best_assign` 或 `far_assign`；S02-S05 禁止调用 `geo_wide_v/geo_arrow/geo_box/geo_diagonal/geo_wave/geo_grid`
- 正式段默认展开 per-drone loop：`move2(drone, target, flying_ms)` → `apply_light(drone, color, ticks)` → `drone.delay(delay_ms)`，让每架机保留自己的灯光/等待细节
- S02-S05 每段至少一个 keyframe 必须打破时间同步（同起同停会被节奏门打回）：起飞波次 `drone.delay(i * 120)`（move2 前）或到达波次 `move2(drone, t, fly_ms + (i % 3) * 250)`
- 灯光时钟型写法可免时间算术：`apply_light(drone, color, fly_ms // 100)` 占满飞行窗口不写尾部 delay；错峰时 `(fly_ms - i*120) // 100` 自然回正
- 个体色彩身份：群舞/交换 keyframe 每架机自己的色相（palette[i]），观众才能跟踪换位；统一色留给宣言时刻
- 镜像换位/对穿必须错峰：`drone.delay(i * 150)` 各机不同时刻过中心——同步对穿必撞，错峰本身就是对穿的安全机制
- 分配函数家族（按转场意图选）：`best_assign` 收束 / `far_assign` 大交换 / `rotate_assign(prev, geo, steps)` 漩涡 / `mirror_assign` 对穿（配错峰）/ `swap_assign(prev, geo, axis)` 半场互换 / `keep_assign` 身份保持
- 定格 pose 合法（静止展示造型可超 1s），但定格期间必须灯亮；黑灯静止会被判低活动
- `move_group/move_group_staggered` 只作为 smoke/兜底工具；S01-S06 纯 helper 执行会被 composition gate 打回。卡农/错峰请在 per-drone loop 内按 `i % group_mod` 写小 delay
- 3s 以上 keyframe 若用 `far_assign`，写 `min_path_cm=active_min_path_cm(flying_ms)`；不要写 90/100cm 导致真实运动过早结束
- 安全距离按 XY 看，不要把同一 XY 不同 Z 当成安全分离
- 6-8s 中短窗口只写 2 个强 keyframe；若错峰，stagger_ms=60-90，避免第三个 keyframe 把段尾动作拖成未完成
- S04 抒情展开段要写 4-5 个短 keyframe，至少 3 种颜色/灯光变化；S06 尾声要写两段式收尾（中继点 + 最终署名），不能单 keyframe 小挪动
- 编舞词汇（每段至少用一种）：交错启动 (delay(i*ms)), Z 个性 (move2 内 +dz*sin(i)), 分组对比, 焦点机, 中心迁移, 密度呼吸, 灯光渐变 (range()+TurnOnAll((r,g,b)))；S01-S05 全段匀速单色无差异会被节奏门打回
- 渐变灯光必须塞进飞行窗口：keyframe 内 `ticks*100 + delay_ms ≈ fly_ms`；动作完成后原地亮灯 >1s 会被判低活动打回
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
