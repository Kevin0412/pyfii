# AI 生成的 pyfii 编码模式

分析高价值 AI 生成脚本（GPT-5.5/Codex）的 pyfii 代码组织方式，对照产物蒸馏结果标注验证状态。

> **验证标记**：✅ 蒸馏验证有效 | ⚠️ 源码存在但效果待确认 | ❌ 蒸馏发现反例

分析对象：
- `gpt55_phrase_vibe_v3_60s.py`：phrase 驱动架构，蒸馏效果最佳
- `original_crosscut_v9_60s.py`：确定性角色交换，d6 有轻度车道
- `original_phrase_motion_v4_70s.py`：formations + phrases 双层声明（无产物）
- `gpt55_template_motion_v2_60s.py`：模板衔接不连贯（jerk 最高）
- `original_kinetic_ribbon_v8_60s.py`：空间利用最好，无车道
- `original_flow_field_v5_70s.py`：部分车道退化
- `codex_mirror_bloom_60s.py`：严重车道退化（见第十章）

完整蒸馏数据见 [ai_generated_distillation.md](ai_generated_distillation.md)。

---

## 一、Phrase 驱动架构 ✅

声明与执行分离。设计意图放在数据结构，执行逻辑放在函数。gpt55_phrase_vibe_v3 蒸馏效果最佳（uf=0, minD=57cm, 无车道），验证了此架构的有效性。

```python
PHRASE_DURATIONS = [2, 4, 3, 3, 2, 4, 2, 3, 5, 3, 4, 2, 4, 2, 5, 3, 3, 2]
PHRASE_DESIGNS = [
    ("curtain snap into bloom", ["curtain_sweep", "height_ripple"], "wing_delay", "#4dd7ff"),
    ("long crown hinge",       ["hinge_turn", "radial_bloom", "late_release"], "outer_inner", "#fff06e"),
]
```

每个 phrase 声明：duration、label、primitives、group_mode、color。用 `build_phrases()` 从声明生成结构化对象，`build_drones()` 负责翻译成 pyfii 调用。

### formations + phrases 双层声明（original_phrase_motion_v4）⚠️

```python
FORMATIONS = [
    ("asymmetric_launch", [(80, 120, 100), (155, 220, 130), ...]),
    ("wide_star",         [(280, 60, 170), (450, 135, 125), ...]),
]
```

每个 phrase 关联 `from` formation 和 `to` formation。此脚本无产物文件，无法蒸馏验证。

---

## 二、数学工具函数 ✅

```python
def smoothstep(t):      return t * t * (3 - 2 * t)
def mix_point(a, b, t): return tuple(a[i]*(1-t) + b[i]*t for i in range(3))
def clamp(value, low, high): return max(low, min(high, value))
def point3(values):     # 坐标钳制到场地范围
```

smoothstep 缓入缓出，mix_point 线性插值。蒸馏产物中 gpt55 系列和 crosscut_v9 的运动较为平滑（jerk 2.3-3.8），验证了这些工具的有效性。但 template_motion_v2 的 jerk 高达 4.2——**模板间硬切换会导致动作不连贯，即使有 smoothstep**。

---

## 三、程序化灯光 ⚠️

AI 脚本中的灯光函数：

```python
def pulse_color(base_color, drone_idx, tick_idx, tick_count):
    # 基于 phrase 主题色 + 机号 + 时间的正弦脉冲
    ...

def apply_phrase_lights(drone, drone_idx, phrase, duration_ms):
    step_ms = 100  # 100ms 步长
    for tick_idx in range(steps):
        if (tick_idx + drone_idx) % 17 == 16:
            drone.TurnOffAll()  # 周期性灭灯制造呼吸
        else:
            drone.TurnOnAll(pulse_color(...))
        drone.delay(step_ms)
```

**蒸馏验证**：所有 AI 产物无音乐输入，灯光效果无法做音乐-动作对齐验收。pulse_color 的代码模式本身合理，但缺乏音乐 cue 意味着灯光节奏是机械生成的而非响应音乐的。

---

## 四、速度求解 ⚠️

基于距离自动决定拆成几步：

```python
def phrase_step_count(phrase):
    for step_count in (4, 3, 2, 1):
        if max_travel_time_for_steps(phrase, step_count) <= step_duration - 0.05:
            return step_count
    return 1
```

优先 4 步（最平滑），逐步降到 1 步。

**蒸馏验证**：所有 AI 产物 uf=0，说明速度求解确实产出了可执行的时间安排。但不能确定是否"最优"——gpt55_template_motion 的 jerk 高可能说明步数分解虽"安全"但不够"平滑"。

---

## 五、生成前安全验证 ⚠️

源码中存在 `validate_planned_keypoints()` 函数，在生成 pyfii 代码前检查目标点。但蒸馏发现：

- 所有 AI 产物 uf=0，没有触发任何"动作未完成"——说明 **pyfii 自身的 `drone_config` 约束已足够保证可执行性，额外的预验证可能不是必需的**
- gpt55 系列 XY 跨度完全一致（477×492），小于场地极限 560×560——说明安全钳制可能**过早截断了动作野心**

**结论**：预验证可以作为调试工具，但不应替代 pyfii 的 read_fii warning 作为安全标准。不要额外定义安全距离常量。

---

## 六、四步验证闭环 ✅

部分脚本实现了完整验收链：

```python
validate_planned_keypoints()  # 预验证
build_drones()                # 生成
F.save(True, field=6)         # 保存 .fii
data, t0, _, _, _ = pf.read_fii(PROJECT_PATH, fps=60, ignore_acc=False)  # 读回
pf.show(data, t0, [music_path], field=6, save=PROJECT_NAME, FPS=25)      # 视频
```

蒸馏产物中有 .fii 文件可读回，说明至少 `save()` 被执行。但部分脚本只有 `print("project: ...")` 提示路径，是否实际执行了 show 不确定。

---

## 七、推荐的 AI 生成代码结构

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

1. **声明与执行分离** ✅：gpt55_phrase_vibe_v3 蒸馏验证有效
2. **数学优于枚举** ✅：smoothstep/mix_point 轨迹蒸馏数据平滑
3. **灯光程序化** ⚠️：代码模式合理，但无音乐 cue 验证
4. **速度求解自动步数** ⚠️：确保可执行但未必最优
5. **预验证不替代 pyfii 约束** ✅：pyfii 的 read_fii warning 是最终标准
6. **信任 pyfii 边界** ✅：不额外加安全常量

---

## 九、应避免（编码层面）

- 逐点硬编码全部坐标
- 固定角色分配
- 跳过 read_fii 验证
- 用 random 决定最终动作
- 模板间硬切换（导致 jerk 飙升，见 template_motion_v2）

---

## 十、已知退化模式（来自产物蒸馏）

对 AI 生成 `.fii` 产物的轨迹蒸馏发现以下退化模式：

### 车道退化

每架机的 X 或 Y 活动范围被限制在极窄区间（<100cm）。codex_mirror_bloom 为典型：七架机等距排在 X 轴（40→100→176→241→308→381→458），每架只在 60-80cm 的窄 X 道内做 Y 向运动。安全但单调。

original_flow_field_v5 有部分车道（d2 X=119cm, d4 Y=108cm），original_crosscut_v9 的 d6 X=180cm 偏窄。

**检测**：遍历每架机，若 `max(X_range, Y_range) < 150cm`，标记为车道风险。

**修复**：允许跨道穿插，扩大窄道轴范围。

### 随机点切换

随机选 7 个点作为目标队形，过段时间换 7 个新点。比车道高级但缺乏主题和几何叙事。

**修复**：用 phrase 声明替代随机采样，每个 phrase 有明确几何意图（对称、同心、交叉等）。

### 安全钳制过保守

gpt55 系列四产物 XY 跨度完全一致（477×492），场地边界 560×560 未被充分利用。安全边界不应成为动作野心的上限。

**修复**：在 `drone_config` 合法范围内设计，不额外加安全距离常量限制。

### 无音乐

当前所有 AI 产物都没有音乐输入，灯光节奏是机械生成的而非响应音乐的。这是 AI 与人类设计的最大差距。
