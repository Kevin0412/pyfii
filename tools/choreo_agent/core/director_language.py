"""导演方位语言 → 几何 grounding。

人类导演不说坐标，说相对方位："3 号机往左一点""移到中间""再高一点"。
本模块把这类反馈落到可执行几何：检测到方位词时，在反馈后追加换算图例
（轴向与 show.py 三视图渲染一致）和各机当前参考坐标，让模型自行换算。

轴向约定（观众正视 front 视图，源自 show.py 的投影式 620+x / 270-z，
深度亮度按 280-y）：
- 左/右 = x 减/增；前/后 = y 减/增（前=靠观众）；上/下(高/低) = z 增/减
- 方位词是**相对方位**：相对该机当前位置（上一段出口/上一版段尾）的位移
"""

from __future__ import annotations

import re
from collections.abc import Sequence

# 只匹配明确的相对方位/位置短语；刻意不收 "高度层""保持高度" 这类
# 编舞术语——auto 测试台的段反馈里全是它们，不能误触发 grounding。
_SPATIAL_PATTERNS = (
    "往左", "往右", "往前", "往后", "往上", "往下",
    "向左", "向右", "向前", "向后", "向上", "向下",
    "靠左", "靠右", "偏左", "偏右", "偏前", "偏后",
    "左一点", "右一点", "前一点", "后一点", "高一点", "低一点",
    "左边", "右边", "前面", "后面", "左侧", "右侧",
    "再高", "再低", "升高", "降低", "抬高", "压低",
    "中间", "中央", "正中", "居中",
    "靠近", "远离", "靠边", "角落",
)

STAGE_LEGEND = (
    "## 方位词换算（相对方位；轴向与三视图渲染一致，观众正视）\n"
    "- 左/右 = x 减/增；前/后 = y 减/增（前=靠观众）；上/下(高/低) = z 增/减\n"
    "- 方位是相对该机当前位置的位移：'一点/稍微' ≈ 40-80cm；'明显/多一点' ≈ 100-160cm；"
    "没说程度 ≈ 80-120cm\n"
    "- '中间/中央' ≈ 场地中心 (280, 280)，Z 中层 ≈ 165\n"
    "- 场地 XY 0-560，Z 80-250；换算后仍要保证任意两机 XY ≥51cm\n"
    "- 指定某机到某处必须身份保持：该 keyframe 后单独 "
    '`move2(drones[k], (x, y, z), ...)`，或分配声明 assign="keep"'
)

# 复杂灯光描述词（渐变/呼吸/依次/彩虹/同步异步…）→ 触发灯光写法图例
_LIGHT_PATTERNS = (
    "渐变", "呼吸", "明暗", "闪烁", "爆闪", "频闪",
    "彩虹", "七彩", "五彩", "多彩", "彩色",
    "依次", "逐个", "逐架", "轮流", "波浪灯", "流动", "扫过", "追光",
    "同步", "异步", "错开点亮",
    "变亮", "变暗", "渐亮", "渐暗", "淡入", "淡出",
)

LIGHT_LEGEND = (
    "## 灯光描述换算（映射到现有执行器/写法）\n"
    "- 渐变/淡入淡出 → `fade_group(drones, c1, c2, duration_ms)` 或动作母题的 gradient_to=；"
    "呼吸/明暗起伏 → `breathe_group(drones, color, cycles, period_ms)`\n"
    "- '依次/逐架/流动/扫过' = 异步点灯：按指定空间顺序排序后逐机延迟切灯"
    "（如 '从左到右' = 按当前 x 从小到大排序，依次 delay 后 apply_light/TurnOnAll）；"
    "`light_wave(drones, delays, palette)` 就是这个语义\n"
    "- '同步' = 全体同一时刻切换；'异步/错开' = 每机错开 100-300ms\n"
    "- 彩虹/七彩 = 每机独立色相：按空间顺序把色相 0-300° 均分给各机"
    "（红→黄→绿→青→蓝→紫，palette[i] 写具体 hex）\n"
    "- '五彩斑斓的黑/暗色多彩' = 低亮度多色相：各机不同色相但亮度压低"
    "（每通道 ≤120），暗底上微光闪动\n"
    "- 复杂灯效也必须塞进时间预算：飞行窗口内 ticks*100+delay≈fly_ms，"
    "或动作后用 light_wave/breathe_group 铺到窗口尾，不要黑灯静止"
)


# 速度/节奏词 → 触发速度换算图例（flash 靠散文做不好 flying_ms 的除法）
_SPEED_PATTERNS = (
    "放慢", "慢一点", "慢下来", "别太快", "不要快", "优雅一点",
    "加快", "快一点", "更快", "提速", "速度不超过", "cm/s",
)

SPEED_LEGEND = (
    "## 速度换算（用数学保证，不要凭感觉）\n"
    "- move2 的实际速度 = 3D 路径长度 ÷ (flying_ms/1000)。要满足速度上限 V，"
    "必须 flying_ms ≥ ceil(路径cm ÷ V × 1000)\n"
    "- 例：路径 200cm、上限 120cm/s → flying_ms ≥ 1667；路径 300cm → ≥ 2500\n"
    "- 对每个 keyframe 的最长路径按上式算 flying_ms（宁可取整到更大值）；"
    "路径长的机决定全组 flying_ms\n"
    "- 加速段同理反算；'放慢'没给数字时按 ≤120cm/s 处理"
)


def needs_speed_grounding(text: str) -> bool:
    text = text or ""
    return any(pattern in text for pattern in _SPEED_PATTERNS)


def needs_grounding(text: str) -> bool:
    return (
        needs_spatial_grounding(text)
        or needs_light_grounding(text)
        or needs_speed_grounding(text)
    )


def needs_spatial_grounding(text: str) -> bool:
    text = text or ""
    return any(pattern in text for pattern in _SPATIAL_PATTERNS)


def needs_light_grounding(text: str) -> bool:
    text = text or ""
    return any(pattern in text for pattern in _LIGHT_PATTERNS)


def ground_directive(
    feedback: str,
    drone_positions: Sequence[Sequence[float]] | None = None,
) -> str:
    """含方位/灯光描述词的导演反馈 → 追加对应换算图例与各机当前坐标。

    普通反馈原样返回（auto 测试台的段反馈不含这些短语，prompt 字节不变）。
    """
    if not feedback:
        return feedback
    spatial = needs_spatial_grounding(feedback)
    light = needs_light_grounding(feedback)
    speed = needs_speed_grounding(feedback)
    if not spatial and not light and not speed:
        return feedback
    parts = [feedback.rstrip(), ""]
    if spatial:
        parts.append(STAGE_LEGEND)
    if light:
        parts.append(LIGHT_LEGEND)
    if speed:
        parts.append(SPEED_LEGEND)
    if drone_positions and (spatial or light):
        # 灯光的空间顺序（从左到右依次…）同样需要当前坐标做排序基准
        pos = ", ".join(
            f"d{i}=({float(p[0]):.0f},{float(p[1]):.0f},{float(p[2]):.0f})"
            for i, p in enumerate(drone_positions)
        )
        parts.append(f"各机当前参考位置（相对位移/空间排序以此为基准）: {pos}")
    return "\n".join(parts)


def format_directive_checklist(directives: Sequence[str]) -> str:
    """多条导演指令 → 编号清单 + 逐条自查（防小模型顾此失彼丢指令）。"""
    items = [str(d).strip() for d in directives if str(d).strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    numbered = "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1))
    return (
        f"## 导演指令清单（共 {len(items)} 条，每一条都必须满足，缺一不可）\n"
        f"{numbered}\n"
        "写完代码后逐条对照自查（1 ✓/✗ 2 ✓/✗ …）；漏掉任何一条都算失败，"
        "不要为了满足一条而放弃另一条。"
    )


_INDEXED_DRONE = re.compile(r"(?:drones\[(\d+)\]|(\d+)\s*号机)")


def mentioned_drones(text: str) -> list[int]:
    """提取反馈里点名的机号（drones[k] / k 号机），供针对性反馈用。"""
    found: list[int] = []
    for match in _INDEXED_DRONE.finditer(text or ""):
        value = match.group(1) or match.group(2)
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        if index not in found:
            found.append(index)
    return found
