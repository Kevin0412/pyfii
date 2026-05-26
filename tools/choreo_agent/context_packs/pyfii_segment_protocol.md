# Segment Protocol

## 每次只生成当前段

输入：
- `segment_id`
- `start_time` / `end_time`
- music cue (能量、情绪、节奏密度)
- `start_state` (prev positions)
- `design_memory` 摘要
- `human_feedback` (如有)
- 当前段历史尝试

输出：
- 当前段代码（含 marker）
- 设计说明
- 是否改变出口状态
- 需要验证的点

禁止：
- 修改前段
- 添加后段
- 覆盖整个 design.py
- 生成不存在的 Pyfii API

## 首段起飞布局

首段 `S01` 的代码拥有起飞布局和正式编舞两部分。agent 必须自己设计起飞位置，不要依赖 template 或 `state.json` 预设点位。

推荐结构：

```python
start_positions = [
    (x0, y0),
    ...
]

for i, drone in enumerate(drones):
    drone.X = drone.x = clamp_xy(start_positions[i][0])
    drone.Y = drone.y = clamp_xy(start_positions[i][1])
    drone.takeoff(1, 110)

# 正式编舞从 4.0s 后开始调度
for i, drone in enumerate(drones):
    drone.inittime(4.0)
    ...
```

起飞和起飞后的准备等待不计入正式编舞质量门；正式段窗口内仍必须满足安全、运动包络、连续性和有效动作质量。

## 时间线规划

PyFii 时间不是 Python `for` 循环的全局时间；每架无人机都有自己的命令游标。`inittime()` 把本机游标切到绝对秒数，`delay()` / `apply_light()` 推进本机游标，`move2()` 只在当前游标发起移动但不推进游标。

段内不要每次移动都 `inittime()`。推荐结构是：

```python
drone.inittime(segment_start)
drone.move2(x1, y1, z1)
apply_light(drone, color, 3)
drone.delay(rest_ms_for_this_move)
drone.move2(x2, y2, z2)
apply_light(drone, color2, 3)
drone.delay(rest_ms_for_this_move)
```

这里的 `delay()` 不是用来“悬停填时间”，而是给刚发起的移动留出执行时间。灯光可以插在移动执行窗口里，但灯光/等待总时长必须和本次移动飞行时间对应。

正式段必须先做时间预算：

- 把音乐段拆成 2-5 个 keyframe interval，例如开场、汇聚、展开、收束。
- 对每个 interval，估算每架机的 3D 距离，用飞行时间公式选择速度/加速度，让真实移动覆盖 interval 的主体。
- 不要把多个短几何快速串完后用静止等待填尾；如果 interval 太长，降低速度、增加路径弧度或增加中间 keyframe。
- 至少安排一个真实 `move2()` / Z/XY 变化在 `segment_end - 1s` 后仍在执行，并在 `segment_end` 前完成。
- 如果段落是 4-24s，动作不能在 10s 左右结束；每架机的主体动作链应覆盖到 23s 后。

## 几何定义格式

```python
geo = [
    [(x0,y0,z0), (x1,y1,z1), ..., (x6,y6,z6)],  # 几何1: 7机坐标
    [(x0,y0,z0), ..., (x6,y6,z6)],               # 几何2
    ...                                           # 几何3-4
]
```

每个几何内部各点间距 > 51cm（F400 安全阈值）。

## 排列搜索

必须使用 `best_assign()`：

```python
def best_assign(starts, targets):
    """全排列搜索路径最短距离最大的分配。用作离线工具，结果硬编码。"""
    N = len(starts)
    best_md, best_perm = -1, None
    for perm in itertools.permutations(range(N)):
        tt = [targets[i] for i in perm]
        md = 1e9
        for i in range(N):
            for j in range(i+1, N):
                d = _segment_distance(starts[i], targets[perm[i]], starts[j], targets[perm[j]])
                if d < md: md = d
        if md > best_md:
            best_md = md
            best_perm = perm
    return best_perm, best_md

线段距离用计算几何精确解（叉积+投影），不采样。
权重 `md*2000` 强烈倾向最安全分配。`max_d*0.01` 几乎不影响。

## 灯光

```python
def apply_light(drone, color, ticks):
    """正弦渐变灯光，ticks=步数(每步100ms)"""
    for tick in range(ticks):
        bright = int(100 + 155 * math.sin(tick * math.pi / ticks))
        r = int(color[1:3], 16) * bright // 255
        g = int(color[3:5], 16) * bright // 255
        b = int(color[5:7], 16) * bright // 255
        drone.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}")
        drone.delay(100)
```

`apply_light()` 每 tick 会 `delay(100)`，因此它也会推进本机命令游标。正式编舞段默认只用 3-6 ticks 的短灯光脉冲；除非这段时间被正在执行的移动覆盖，否则不要在全体 move2 后使用 `ticks > 8`。

每段可使用不同颜色。每个 move2 后可以接短灯光脉冲和执行等待，但不能用无运动覆盖的纯灯光/纯 delay 填满 1 秒以上；如需长呼吸，必须让另一组错峰运动，或把呼吸设计成仍在执行的弧线/高度 keyframe。

## 排队错峰

```python
for i,d in enumerate(ds): d.delay(i*offset_ms)  # offset=100-600ms
```

排在 inittime 之后、第一个 move2 之前。

注意：错峰只改变起步时间，不自动保证连贯性。正式段里每个 1 秒窗口都应至少有一组无人机在 `move2` 或轻微 Z/XY 变化中，不能出现全体一起等灯光/等 delay 的空窗。


## dntg 技巧：相对移动 + 条件分支

```python
# 相对移动：从当前位置偏移
drone.move(drone.x + dx, drone.y + dy, drone.z + dz)

# 条件分支：不同机走不同路径
for i, drone in enumerate(drones):
    drone.inittime(10)
    if i < 3:
        drone.move2(280 + 80*i, 280, 180)
    elif i == 3:
        drone.move2(280, 280, 200)
    else:
        drone.move2(280, 280 + 80*(i-4), 180)
```

## 示例完整段

见 `context_packs/examples/segment_with_best_assign.py`
