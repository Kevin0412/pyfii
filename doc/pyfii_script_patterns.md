# pyfii Python 脚本设计模式分析

本文分析高价值 pyfii Python 脚本的代码组织方式、设计模式和可复用的工程方法。分析对象来自 `doc/ai_choreography_exploration.md` 中标注的最高参考基线和高价值 AI 归档脚本。

## 分析对象

| 脚本 | 类型 | 价值定位 |
|---|---|---|
| `tests/dntg20220730_v3.py` | 人类设计 | 最高参考基线，展示成熟编舞的组织方式 |
| `archive/.../gpt55_phrase_vibe_v3_60s.py` | AI 生成 | 最有价值的 phrase 驱动架构 |
| `archive/.../original_crosscut_v9_60s.py` | AI 生成 | 确定性角色交换 + 验证闭环 |
| `archive/.../original_phrase_motion_v4_70s.py` | AI 生成 | 清晰的 spec-to-code 结构 |
| `archive/.../gpt55_template_motion_v2_60s.py` | AI 生成 | 动作词汇表参考 |
| `archive/.../original_kinetic_ribbon_v8_60s.py` | AI 生成 | 连续 ribbon 场 + 速度求解 |
| `archive/.../original_flow_field_v5_70s.py` | AI 生成 | flow-field 状态规划 |

---

## 一、Phrase 驱动架构（核心模式）

最高价值的脚本都采用"先声明 phrase，再生成代码"的架构。这种模式将"设计意图"与"pyfii 代码执行"分离。

### 1.1 声明式 phrase 定义

**gpt55_phrase_vibe_v3_60s.py**：

```python
PHRASE_DURATIONS = [2, 4, 3, 3, 2, 4, 2, 3, 5, 3, 4, 2, 4, 2, 5, 3, 3, 2]
PHRASE_DESIGNS = [
    ("curtain snap into bloom", ["curtain_sweep", "height_ripple"], "wing_delay", "#4dd7ff"),
    ("long crown hinge",       ["hinge_turn", "radial_bloom", "late_release"], "outer_inner", "#fff06e"),
    # ...
]
```

每个 phrase 声明了：
- **duration**：时长（秒）
- **label**：动作意图名称
- **primitives**：动作原语列表（描述"做什么"）
- **group_mode**：分组模式（描述"谁和谁一起"）
- **color**：该段的主题色

然后用 `build_phrases()` 从声明生成结构化对象：

```python
def build_phrases():
    phrases = []
    cursor = 4.0  # 起飞后开始
    for idx, duration in enumerate(PHRASE_DURATIONS):
        label, primitives, group_mode, color = PHRASE_DESIGNS[idx]
        phrases.append({
            "phrase_id": f"P{idx + 1:02d}",
            "start": round(cursor, 2),
            "end": round(cursor + duration, 2),
            "label": label,
            "primitives": primitives,
            "group_mode": group_mode,
            "color": color,
        })
        cursor += duration
    return phrases
```

**设计要点**：声明与执行分离。声明层只描述"什么时候做什么"，执行层（`build_drones()`）负责把声明翻译成 pyfii 调用。

### 1.2 original_phrase_motion_v4 的 formations + phrases 双层声明

```python
FORMATIONS = [
    ("asymmetric_launch", [(80, 120, 100), (155, 220, 130), ...]),
    ("wide_star",         [(280, 60, 170), (450, 135, 125), ...]),
    # ... 15 formations
]

PHRASE_DURATIONS = [4, 4, 3, 5, 4, 5, 3, 4, 5, 4, 5, 4, 5, 4, 3]
PHRASE_COLORS = ["#48dbfb", "#ffdd59", ...]
```

每个 phrase 关联一个"from formation"和一个"to formation"，`build_phrases()` 将两者绑定：

```python
{
    "phrase_id": f"O{idx + 1:02d}",
    "from": idx,      # 起始队形索引
    "to": idx + 1,    # 目标队形索引
    "color": PHRASE_COLORS[idx],
}
```

**设计要点**：formations 作为可复用词汇表，phrase 只声明"从哪个队形到哪个队形"。

---

## 二、数学轨迹表达

人类设计 `dntg20220730_v3.py` 大量使用数学函数表达连续运动，而非逐点写坐标。

### 2.1 复数旋转

```python
import cmath

# 六边形起始位置
d.X = int(280 + (E**(n/3*PI*1j)).real * 70 + 0.5)
d.Y = int(280 + (E**(n/3*PI*1j)).imag * 70 + 0.5)

# 段内旋转
theta = 2/3*PI*gn + PI/6*step + 2.5/3*PI
rotateV = E**(theta*1j)
move2autoz(d, (g1c[0] + R*rotateV.real, g1c[1] + R*rotateV.imag), 6000/10)
```

**设计要点**：用 `E**(angle*1j)` 表达旋转向量，避免硬编码三角函数。

### 2.2 利萨如轨迹

```python
li = []
for a in range(24):
    li.append((
        280 + 320/3**0.5 * np.sin(2*a/24 * 2*np.pi),
        280 + 320/3**0.5 * np.sin(3*a/24 * 2*np.pi),
        165 + 128/3**0.5 * np.sin(4*a/24 * 2*np.pi + np.pi/2)
    ))
```

**设计要点**：预计算轨迹点表，按索引分配。不同频率的正弦波叠加形成复杂但可控的空间曲线。

### 2.3 AI 脚本中的数学工具函数

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

`smoothstep` 用于缓入缓出，`mix_point` 用于线性插值，`point3` 用于坐标约束和安全钳制。

---

## 三、角色映射与分组

### 3.1 字典式角色映射

`dntg20220730_v3.py` 用字典做角色分配：

```python
n2gn = {1:3, 2:4, 3:5, 4:0, 5:2, 6:-1, 7:1}  # 机号 → 组号
n2sg = [None, 2, 1, 0, 6, 3, 5, 4]            # 机号 → 符号组
```

每段可以有不同的映射，实现角色变换：

```python
for d, n in zip(ds, range(7)):
    gn = n2gn[n+1]
    if gn == -1:
        d.TurnOnAll(RED)
        move2(d, (center.real, center.imag, baseH), 2000)
    else:
        # gn 决定该机的运动参数
        iv, ih = (gn+step)%6, (gn+2*step)%6
        pos = center + rotateVs[iv]
        move2(d, (pos.real, pos.imag, baseH+dHs[ih]), 2000)
```

**设计要点**：角色映射使同一架机在不同段落承担不同职责，避免"固定中心/固定外圈"的退化。

### 3.2 分组差异与错峰

```python
if n == 0:
    d.intime(7)
    move2(d, (d.x-160, d.y, d.z), 1500)
    d.delay(1500)
elif n == 6:
    d.intime(7)
    move2(d, (d.x+160, d.y, d.z), 1500)
    d.delay(1500)
elif n == 3:
    d.intime(7)
    move2(d, (d.x, d.y-80*3**0.5, d.z), 1500)
    d.delay(1500)
    b = 0
    for a in [0,1,2,4,5,6]:
        b += li[li1[a]][2] / 6
    move2(d, (280, 280, b), 1500)
else:
    d.intime(7)
    d.delay(1500)
    move2(d, (li[li1[n]][0]+li3[n], li[li1[n]][1], li[li1[n]][2]), 1500)
```

**设计要点**：不同机在同一段内可以有完全不同的动作路径——有的先动、有的后动、有的走长路径、有的走短路径。

---

## 四、程序化灯光

### 4.1 数学驱动的颜色生成

`dntg20220730_v3.py` 用三角函数生成连续变化的颜色：

```python
for a in range(20):
    d.TurnOnAll(rgb2str(
        int(160 + 95.5*np.sin(3*2*np.pi/20*a)),
        int(160 + 95.5*np.sin(4*2*np.pi/20*a)),
        int(160 + 95.5*np.sin(2*2*np.pi/20*a))
    ))
    d.delay(100)
```

### 4.2 AI 脚本的 pulse_color 函数

```python
def pulse_color(base_color, drone_idx, tick_idx, tick_count):
    base = hex_to_rgb(base_color)
    warm = (255, 240, 190)
    cool = (110, 220, 255)
    accent = warm if (tick_idx // 3 + drone_idx) % 2 == 0 else cool
    phase = tick_idx / max(1, tick_count) + drone_idx / DRONE_COUNT
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * phase)
    return rgb_to_hex(scale_rgb(
        blend_rgb(base, accent, 0.20 + 0.35 * pulse),
        0.60 + 0.40 * pulse
    ))
```

**设计要点**：灯光不应硬编码颜色序列。用一个 `pulse_color` 函数，基于 phrase 主题色 + 机号 + 时间步，自动生成有节奏感的灯光变化。

### 4.3 apply_phrase_lights 模式

```python
def apply_phrase_lights(drone, drone_idx, phrase, duration_ms):
    step_ms = 100
    steps = max(1, int(duration_ms // step_ms))
    for tick_idx in range(steps):
        if (tick_idx + drone_idx) % 17 == 16:
            drone.TurnOffAll()  # 偶尔全灭制造呼吸感
        else:
            drone.TurnOnAll(pulse_color(phrase["color"], drone_idx, tick_idx, steps))
        drone.delay(step_ms)
```

100ms 步长 + 周期性 TurnOff 制造呼吸节奏。

---

## 五、速度求解与安全检查

### 5.1 基于距离的速度求解

```python
def phrase_step_count(phrase):
    duration = phrase["end"] - phrase["start"]
    for step_count in (4, 3, 2, 1):
        step_duration = duration / step_count
        if max_travel_time_for_steps(phrase, step_count) <= step_duration - 0.05:
            return step_count
    return 1
```

按距离估算所需时间，自动决定拆成几步。优先尝试 4 步（最平滑），逐步降到 1 步。

### 5.2 生成前预验证

```python
def validate_planned_keypoints():
    """在生成 pyfii 代码之前检查所有 phrase 的目标点距离"""
    for phrase in PHRASES:
        for sample_idx in range(samples + 1):
            t = sample_idx / samples
            points = [phrase_point(phrase, idx, t) for idx in range(DRONE_COUNT)]
            dist, pair = min_horizontal_distance(points)
            if dist < SAFE_DISTANCE_CM:
                raise RuntimeError(f"planned keypoint distance failed: {dist:.1f}cm")
```

**设计要点**：安全验证不应只在轨迹生成后做。在生成代码前先检查 phrase 声明的目标点，早发现问题。

### 5.3 安全常量

```python
F400_SAFE_DISTANCE_CM = 70       # F400 安全距离
MAX_2S_SEGMENT_DISTANCE_CM = 285 # 2秒内最大位移
```

安全约束作为显式常量，不埋在逻辑中。

---

## 六、验证与验收闭环

### 6.1 dntg20220730_v3 的验证链

```python
for d in ds:
    d.end()

F = pf.Fii('大闹天宫', ds, music=music_path)
F.save(True, field=6)

pf.show(F.dots, F.t0, [F.music], field=6, save='大闹天宫', FPS=25)
```

保存 `.fii` + 渲染视频 = 完整验收闭环。

### 6.2 AI 脚本的验证链

```python
# 1. 速度预验证
validate_planned_keypoints()

# 2. 生成并保存
build_drones()
F = pf.Fii(PROJECT_NAME, ds, music=str(music_path))
F.save(True, field=6)

# 3. 读回验证
data, t0, _, _, _ = pf.read_fii(PROJECT_PATH, fps=60, ignore_acc=False)
# 检查 distance between、action isn't completed

# 4. 视频验收
pf.show(data, t0, [music_path], field=6, save=PROJECT_NAME, FPS=25)
```

四步闭环：预验证 → 生成 → 读回 → 视频。

---

## 七、代码组织模式总结

### 推荐的代码结构

```
1. 常量声明
   - DRONE_COUNT, LAND_TIME_SEC
   - SAFE_DISTANCE_CM, MAX_SEGMENT_DISTANCE
   
2. 设计声明（声明层）
   - PHRASE_DURATIONS / FORMATIONS
   - PHRASE_DESIGNS / PHRASE_COLORS
   
3. 工具函数
   - clamp, point3, smoothstep, mix_point
   - hex/rgb 转换
   - 距离/时间计算
   
4. phrase 构建
   - build_phrases() → 结构化 phrase 对象列表
   
5. 动作生成函数
   - phrase_point(phrase, drone_idx, t)  # 数学轨迹
   
6. 灯光函数
   - pulse_color / apply_phrase_lights
   
7. 验证函数
   - validate_planned_keypoints()
   - min_horizontal_distance()
   
8. build_drones() 主函数
   - 创建 Drone 对象
   - takeoff
   - 遍历 phrases: inittime + move2 + 灯光
   - land
   
9. 保存与验收
   - Fii.save()
   - read_fii()
   - show()
```

### 关键设计原则

1. **声明与执行分离**：设计意图放在数据结构（列表、字典），执行逻辑放在函数
2. **数学优于枚举**：用函数表达轨迹（三角函数、复数旋转、smoothstep），不逐点写坐标
3. **角色可变化**：用字典做角色映射，每段可以重新分配
4. **灯光程序化**：灯光不是静态序列，而是基于时间/机号/颜色的函数
5. **先验证再生成**：生成 pyfii 代码前做距离和时间预检查
6. **四步验收闭环**：预验证 → 生成 → 读回 → 视频

### 应避免的模式

- 逐点硬编码全部坐标（不可维护，不可泛化）
- 固定角色分配（全程同一架机在同一个位置）
- 灯光作为事后添加（应与动作同步设计）
- 跳过读回验证（没有 warning 检查就没有安全保证）
- 用 random 直接决定最终动作（不可复现，不可调试）
