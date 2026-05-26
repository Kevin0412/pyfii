# Pyfii Coding Rules

## 硬规则

1. **只修改当前未锁定 segment。**
2. **不允许修改 locked segment。**
3. **不允许提前设计下一段。**
4. **不要猜不存在的 Pyfii API。** 优先模仿已有代码。
5. **`inittime()` 是秒级整数。**
6. **`delay()` 是毫秒。**
7. **所有坐标必须 `int(round())`。** `math.cos/sin` 返回值是浮点数。
8. **每段结束必须更新 `prev = targets`。**
9. **所有机始终有动作**，不悬停。长时间小范围运动效果等同悬停。
- **同一架机的下一个 `move2()` 必须在上一个移动有足够执行时间后再开始**，否则会出现 action warning 或中途截断。
- **段间留 >0.5s 余量**，确保上一段最晚动作完成后再开始下一段。


## 段内结构

```python
# === AGENT_SEGMENT_START S03 locked=false ===
# intent: ...
# start_time: 24.0
# end_time: 34.0

geo = [...]              # 几何定义

for i,d in enumerate(ds):
    d.inittime(start)
    current = prev[i]
    for gi in range(len(geo)):
        target = assigned_targets[gi][i]
        interval_s = intervals_s[gi]
        distance = dist3(current, target)
        speed = speed_for_interval(distance, interval_s)
        d.VelXY(speed, speed * 2)
        d.VelZ(speed, speed * 2)
        d.move2(...)
        light_ticks = 3
        apply_light(d, color, light_ticks)
        d.delay(max(0, flight_time_ms(distance, speed, speed * 2) - light_ticks * 100 + 120))
        current = target

prev = assigned_targets[-1]

# === AGENT_SEGMENT_END S03 ===
```

## 时间线和速度设置

- **VelXY 和 VelZ 必须使用相同的速度和加速度值**
- **每个 keyframe 都要重新计算速度/加速度**；不要整段固定 `VelXY(200, 400)` 或只设置一次速度。

`move2()` 发起移动但不推进命令时间；`delay()` 和 `apply_light()` 才推进本机命令时间。因此正确链路是 `move2() -> 短灯光/执行等待 -> move2()`。不要每个 move 前都 `inittime()`；只在段首或明确绝对 cue 处使用。

- 先按音乐把段落拆成 keyframe interval，再为每个移动选择距离、速度和加速度。
- 如果移动太早结束，优先降低速度、增加路径弧度/中间 keyframe、改变高度层，或让分组错峰；不要在段尾补无运动长 delay。
- `delay()` 只有在紧跟一个正在执行的 `move2()`、用于给飞行留时间时才是合理的。
- 如果动作未完成(action warning)，先检查本次 `move2()` 后的 light+delay 是否覆盖飞行时间；必要时缩短距离、提速或增加该移动后的执行时间预算。

## 飞行时间公式

```python
def dist3(p0, p1):
    return math.sqrt(
        (p1[0] - p0[0]) ** 2 +
        (p1[1] - p0[1]) ** 2 +
        (p1[2] - p0[2]) ** 2
    )

def flight_time_s(distance_cm, v, a):
    """PyFii readback uses a trapezoid/triangle speed curve on 3D distance."""
    if distance_cm <= 0:
        return 0.0
    accel_dist = v * v / (2 * a)
    if distance_cm >= 2 * accel_dist:  # 有匀速阶段
        return 2 * v / a + (distance_cm - 2 * accel_dist) / v
    else:                     # 仅加速-减速
        return 2 * math.sqrt(distance_cm / a)

def flight_time_ms(distance_cm, v, a):
    return int(math.ceil(flight_time_s(distance_cm, v, a) * 1000))

def speed_for_interval(distance_cm, desired_s):
    """用 VelXY(v, 2v) 时，长移动约 distance/v + 0.5s。"""
    if distance_cm <= 1:
        return 60
    usable_s = max(0.6, desired_s - 0.5)
    return min(200, max(45, int(distance_cm / usable_s)))
```

短距离会走三角速度曲线；长距离才有匀速阶段。使用 `VelXY(v, 2*v)` 时，多数长移动约为 `distance / v + 0.5s`。

确保：
- 生成段代码前必须先算每个 keyframe interval 的距离和飞行时间。
- 对每个移动，`light_ticks * 100ms + delay_ms >= flight_time_ms(distance, v, a) + 100`。
- 如果音乐 interval 比飞行时间长很多，应调整路线和速度，让真实移动占据 interval 的主体，而不是补长 delay。

## 高度层

- 正式段不能全程固定高度；目标几何必须包含 low/mid/high 的高度层。
- 至少一半无人机在本段内有明显 Z 变化，通常 >=25cm。
- 速度预算用 3D 距离：`dist3((x,y,z), (tx,ty,tz))`，不要只用 XY。

## 错误处理

| 错误 | 原因 | 修复 |
|------|------|------|
| `Out of range` | XY超出[0,560]或Z超出[80,250] | clamp坐标 |
| `Time arrangement error` | inittime倒退或段间冲突 | 推后inittime |
| `action isn't completed` | 下一条移动开始太早或飞行时间预算不够 | 计算本次 move2 的飞行时间，提速/缩短距离/增加该移动后的执行时间 |
| `distance between` | 两机<51cm | 增间距或提搜索权重 |
| `ValueError: invalid literal` | 坐标含浮点数 | int(round(x)) |
