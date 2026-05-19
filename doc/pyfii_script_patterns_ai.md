# AI 生成的 pyfii 编码模式

分析高价值 AI 生成脚本（GPT-5.5/Codex）的 pyfii 代码组织方式。这些脚本展示了强模型在充分约束下可以生成的成熟代码结构。

分析对象：
- `gpt55_phrase_vibe_v3_60s.py`：phrase 驱动架构（最有价值）
- `original_crosscut_v9_60s.py`：确定性角色交换 + 验证闭环
- `original_phrase_motion_v4_70s.py`：formations + phrases 双层声明
- `gpt55_template_motion_v2_60s.py`：动作词汇表参考
- `original_kinetic_ribbon_v8_60s.py`：连续 ribbon 场 + 速度求解
- `original_flow_field_v5_70s.py`：flow-field 状态规划

## 一、Phrase 驱动架构（核心模式）

声明与执行分离。设计意图放在数据结构，执行逻辑放在函数。

### 声明式 phrase 定义

```python
PHRASE_DURATIONS = [2, 4, 3, 3, 2, 4, 2, 3, 5, 3, 4, 2, 4, 2, 5, 3, 3, 2]
PHRASE_DESIGNS = [
    ("curtain snap into bloom", ["curtain_sweep", "height_ripple"], "wing_delay", "#4dd7ff"),
    ("long crown hinge",       ["hinge_turn", "radial_bloom", "late_release"], "outer_inner", "#fff06e"),
]
```

每个 phrase 声明：duration、label、primitives、group_mode、color。

```python
def build_phrases():
    phrases = []
    cursor = 4.0
    for idx, duration in enumerate(PHRASE_DURATIONS):
        label, primitives, group_mode, color = PHRASE_DESIGNS[idx]
        phrases.append({
            "phrase_id": f"P{idx + 1:02d}",
            "start": round(cursor, 2),
            "end": round(cursor + duration, 2),
            "label": label, "primitives": primitives,
            "group_mode": group_mode, "color": color,
        })
        cursor += duration
    return phrases
```

### formations + phrases 双层声明（original_phrase_motion_v4）

```python
FORMATIONS = [
    ("asymmetric_launch", [(80, 120, 100), (155, 220, 130), ...]),
    ("wide_star",         [(280, 60, 170), (450, 135, 125), ...]),
]

PHRASE_DURATIONS = [4, 4, 3, 5, 4, 5, 3, 4, 5, 4, 5, 4, 5, 4, 3]
PHRASE_COLORS = ["#48dbfb", "#ffdd59", ...]
```

每个 phrase 关联 `from` formation 和 `to` formation。

## 二、数学工具函数

```python
def smoothstep(t):
    return t * t * (3 - 2 * t)

def mix_point(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))

def clamp(value, low, high):
    return max(low, min(high, value))

def point3(values):
    return (
        int(round(clamp(values[0], 0, 560))),
        int(round(clamp(values[1], 0, 560))),
        int(round(clamp(values[2], 88, 230))),
    )
```

`smoothstep` 缓入缓出，`mix_point` 线性插值，`point3` 坐标钳制。

## 三、程序化灯光

不是硬编码颜色序列，而是函数生成：

```python
def pulse_color(base_color, drone_idx, tick_idx, tick_count):
    base = hex_to_rgb(base_color)
    accent = warm if (tick_idx // 3 + drone_idx) % 2 == 0 else cool
    phase = tick_idx / max(1, tick_count) + drone_idx / DRONE_COUNT
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * phase)
    return rgb_to_hex(scale_rgb(
        blend_rgb(base, accent, 0.20 + 0.35 * pulse), 0.60 + 0.40 * pulse
    ))

def apply_phrase_lights(drone, drone_idx, phrase, duration_ms):
    step_ms = 100
    steps = max(1, int(duration_ms // step_ms))
    for tick_idx in range(steps):
        if (tick_idx + drone_idx) % 17 == 16:
            drone.TurnOffAll()
        else:
            drone.TurnOnAll(pulse_color(phrase["color"], drone_idx, tick_idx, steps))
        drone.delay(step_ms)
```

100ms 步长 + 周期性 TurnOff 制造呼吸节奏。颜色基于 phrase 主题色 + 机号 + 时间自动变化。

## 四、速度求解

基于距离自动决定拆成几步：

```python
def phrase_step_count(phrase):
    duration = phrase["end"] - phrase["start"]
    for step_count in (4, 3, 2, 1):
        step_duration = duration / step_count
        if max_travel_time_for_steps(phrase, step_count) <= step_duration - 0.05:
            return step_count
    return 1
```

优先 4 步（最平滑），逐步降到 1 步。

## 五、生成前安全验证

在调用 pyfii API 之前先检查目标点：

```python
def validate_planned_keypoints():
    for phrase in PHRASES:
        for sample_idx in range(samples + 1):
            points = [phrase_point(phrase, idx, t) for idx in range(DRONE_COUNT)]
            dist, pair = min_horizontal_distance(points)
            if dist < SAFE_DISTANCE_CM:
                raise RuntimeError(f"planned keypoint distance failed: {dist:.1f}cm")
```

安全常量显式声明：

```python
F400_SAFE_DISTANCE_CM = 70
MAX_2S_SEGMENT_DISTANCE_CM = 285
```

## 六、四步验证闭环

```python
# 1. 预验证
validate_planned_keypoints()

# 2. 生成并保存
build_drones()
F = pf.Fii(PROJECT_NAME, ds, music=str(music_path))
F.save(True, field=6)

# 3. 读回验证
data, t0, _, _, _ = pf.read_fii(PROJECT_PATH, fps=60, ignore_acc=False)

# 4. 视频验收
pf.show(data, t0, [music_path], field=6, save=PROJECT_NAME, FPS=25)
```

预验证 → 生成 → 读回 → 视频。

## 七、推荐的 AI 生成代码结构

```
1. 常量声明
   DRONE_COUNT, LAND_TIME_SEC, SAFE_DISTANCE_CM

2. 设计声明（声明层，AI 生成的主要内容）
   PHRASE_DURATIONS, FORMATIONS, PHRASE_DESIGNS

3. 工具函数（可复用）
   clamp, point3, smoothstep, mix_point, hex/rgb

4. phrase 构建
   build_phrases() → 结构化 phrase 列表

5. 动作生成函数（数学轨迹）
   phrase_point(phrase, drone_idx, t)

6. 灯光函数
   pulse_color, apply_phrase_lights

7. 验证函数
   validate_planned_keypoints, min_horizontal_distance

8. build_drones() 主函数
   创建 Drone → takeoff → 遍历 phrases → land

9. 保存与验收
   Fii.save() → read_fii() → show()
```

## 八、编码原则

1. **声明与执行分离**：设计意图在数据，执行逻辑在函数
2. **数学优于枚举**：函数表达轨迹，不逐点硬编码
3. **灯光程序化**：基于时间/机号/颜色的函数生成
4. **先验证再生成**：生成 pyfii 代码前预检查距离和时间
5. **四步验收闭环**：预验证 → 生成 → 读回 → 视频
6. **安全常量显式**：不埋在逻辑中

## 九、应避免

- 逐点硬编码全部坐标
- 固定角色分配
- 灯光事后添加
- 跳过读回验证
- 用 random 决定最终动作
