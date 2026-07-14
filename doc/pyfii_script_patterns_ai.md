> **编舞与 Agent 研究资料。** 2026-07-14 已区分可执行示例与伪代码，并校正当前安全验证口径。本文分析的早期 GPT-5.5/Codex 产物仍是当前 Agent 的模式来源和退化反例，不等同于当前生成器实现；文档索引见 [INDEX.md](INDEX.md)。

# AI 生成的 pyfii 编码模式

分析 GPT-5.5/Codex 生成脚本的 pyfii 代码组织方式。分析对象：

| 脚本 | 蒸馏结果 |
|---|---|
| `gpt55_phrase_vibe_v3_60s.py` | 效果最佳：uf=0, minD=57cm, 全场覆盖, 无车道 |
| `original_crosscut_v9_60s.py` | d6 有轻度车道（X=180cm），整体可接受 |
| `original_phrase_motion_v4_70s.py` | 无 `.fii` 产物，无法验证 |
| `gpt55_template_motion_v2_60s.py` | 模板切换导致 jerk 最高（4.2），动作不连贯 |
| `original_kinetic_ribbon_v8_60s.py` | 空间利用最好，全场均匀，minD=87cm |
| `original_flow_field_v5_70s.py` | 部分车道（d2 X=119cm, d4 Y=108cm） |
| `codex_mirror_bloom_60s.py` | 严重车道退化（X 锁在 60-80cm 窄道） |

完整蒸馏数据见 [ai_generated_distillation.md](ai_generated_distillation.md)。

---

## 一、Phrase 驱动架构

声明与执行分离，是当前最有效的 AI 生成范式。gpt55_phrase_vibe_v3 蒸馏效果最佳。

```python
PHRASE_DURATIONS = [2, 4, 3, 3, 2, 4, 2, 3, 5, 3, 4, 2, 4, 2, 5, 3, 3, 2]
PHRASE_DESIGNS = [
    ("curtain snap into bloom", ["curtain_sweep", "height_ripple"], "wing_delay", "#4dd7ff"),
    ("long crown hinge",       ["hinge_turn", "radial_bloom", "late_release"], "outer_inner", "#fff06e"),
]
```

每个 phrase 声明 duration、label、primitives、group_mode、color。`build_phrases()` 生成结构化 phrase 列表，`build_drones()` 翻译成 pyfii 调用。

original_phrase_motion_v4 使用了 formations + phrases 双层声明：`FORMATIONS` 定义队形词汇表，phrase 声明从哪个队形到哪个队形。但此脚本无 `.fii` 产物，实际效果未知。

---

## 二、数学工具函数

```text
def smoothstep(t):      return t * t * (3 - 2 * t)
def mix_point(a, b, t): return tuple(a[i]*(1-t) + b[i]*t for i in range(3))
def clamp(value, low, high): return max(low, min(high, value))
def point3(values):     # 坐标钳制到场地范围
```

smoothstep 缓入缓出，mix_point 线性插值。gpt55 系列和 crosscut_v9 的 jerk 在 2.3-3.8 之间，说明轨迹相对平滑。

但 template_motion_v2 的 jerk 高达 4.2——**模板间硬切换即使有 smoothstep 也无法保证连贯**。phrase 之间需要过渡段而非直接跳变。

---

## 三、程序化灯光

AI 脚本中的灯光是机械生成的，基于 phrase 主题色 + 机号 + 时间步的正弦脉冲：

```python
def pulse_color(base_color, drone_idx, tick_idx, tick_count):
    # 正弦脉冲驱动颜色变化
    ...

def apply_phrase_lights(drone, drone_idx, phrase, duration_ms):
    step_ms = 100
    for tick_idx in range(steps):
        if (tick_idx + drone_idx) % 17 == 16:
            drone.TurnOffAll()
        else:
            drone.TurnOnAll(pulse_color(...))
        drone.delay(step_ms)
```

灯光节奏是机械的 100ms 步长 + 周期性 TurnOff，**没有音乐 cue 驱动**。当前所有 AI 产物都没有音乐输入，无法验证灯光是否与音乐对齐。这是 AI 与人类设计的最大差距——人类作品（如 dntg20220730_v3、大闹天宫）的灯光直接参与音乐表达。

---

## 四、速度求解

基于距离自动决定拆成几步，优先尝试 4 步：

```python
def phrase_step_count(phrase):
    for step_count in (4, 3, 2, 1):
        if max_travel_time_for_steps(phrase, step_count) <= step_duration - 0.05:
            return step_count
    return 1
```

所有 AI 产物 uf=0，说明速度求解产出了可执行的时间安排。但 gpt55_template_motion 的高 jerk 暗示：步数分解保证了"飞得到"，但不保证"飞得好"——安全达标不等于动作平滑。

---

## 五、安全验证

PyFii 的 `drone_config` 定义单机合法范围，但不负责证明多机路径和时间安全。早期 AI 脚本把 `validate_planned_keypoints()` 和固定 `F400_SAFE_DISTANCE_CM` 复制进最终交付代码，既不完整又容易限制动作范围。

更严重的是，gpt55 系列四产物的 XY 跨度完全一致（477×492），始终小于场地极限（560×560）。这说明额外的安全钳制可能过早截断了动作野心，安全边界变成了动作上限。

**当前做法**：规划层可以使用路径分配、时间预算和密采样预检，但最终脚本只保留具体 PyFii 动作。交付验收使用 `pf.from_fii()`、结构化 warning、密采样距离检查和 2D/3D 预览；有冲突风险时调整时间、速度、中间点和错峰，而不是只缩小动作范围。

---

## 六、验证闭环

部分脚本实现了完整链：预验证 → `build_drones()` → `Fii.save()` → `read_fii()` → `show()`。蒸馏产物中有 `.fii` 文件可读回，至少 `save()` 被执行。但部分脚本仅有 `print("project: ...")` 提示路径。

---

## 七、代码结构

```
1. 常量声明（DRONE_COUNT, LAND_TIME_SEC）
2. 设计声明（PHRASE_DURATIONS, FORMATIONS）
3. 工具函数（clamp, point3, smoothstep, mix_point）
4. phrase 构建（build_phrases()）
5. 动作生成函数（phrase_point）
6. 灯光函数（pulse_color, apply_phrase_lights）
7. build_drones() 主函数
8. 保存与验收（Fii.save() → read_fii() → show()）
```

---

## 八、编码原则

1. **声明与执行分离**：设计意图在数据，执行逻辑在函数
2. **数学优于枚举**：函数表达轨迹，不逐点硬编码
3. **速度求解保证可执行**：步数分解确保飞得到，但需关注连贯度
4. **验证分层**：PyFii 范围检查、读回 warning、密采样碰撞和观感检查分别负责不同问题
5. **phrase 间留过渡**：模板/队形切换需要过渡段，避免硬跳

---

## 九、应避免

- 逐点硬编码全部坐标
- 固定角色分配（同一架机全程同一位置）
- 跳过 read_fii 验证
- 用 random 决定最终动作
- 模板间硬切换（见 template_motion_v2 的 jerk 问题）
- 额外定义安全距离常量

---

## 十、已知退化模式

对 AI 生成 `.fii` 产物的轨迹蒸馏发现以下退化：

### 车道退化

每架机的 X 或 Y 活动范围锁在极窄区间。codex_mirror_bloom 为典型：七架机等距排在 X 轴（40→100→176→241→308→381→458），每架只在 60-80cm 窄道做 Y 向运动。安全但单调，一眼看穿。

original_flow_field_v5 有部分车道（d2 X=119cm, d4 Y=108cm），crosscut_v9 的 d6 X=180cm 偏窄。

**检测**：若单轴范围 < 150cm 且另一轴 > 200cm，标记。

**修复**：允许跨道穿插，扩大窄道轴范围。

### 绕圈退化（角度顺序冻结）

6 架机绕中心旋转，但顺时针排列顺序永远不变——各机相对中心的方位角关系始终固定，没有交叉换位。original_flow_field_v5 检测到此模式（71 次采样中 68 次顺序相同）。

**检测**：每秒采样各机相对中心的角度排序，若 >80% 采样点顺序不变，标记。

**修复**：引入角色交换，打破固定角度顺序，允许两架机交换方位或中心偏移。

### 随机点切换

随机选 7 个点作为目标队形，过段时间换 7 个新点。缺乏主题和几何叙事。

**修复**：用 phrase 声明替代随机采样，每个 phrase 有明确几何意图。

### 安全钳制过保守

gpt55 系列四产物 XY 跨度完全一致（477×492），场地边界 560×560 未充分利用。

**修复**：在 `drone_config` 范围内设计，不额外限制。

### 无音乐

所有 AI 产物都没有音乐输入，灯光是机械生成的非音乐响应。
