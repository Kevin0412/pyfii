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
        # Agent motion tool should have estimated this before writing code:
        # 3D distance, desired interval -> concrete speed/accel/delay.
        speed = speeds[gi][i]
        accel = accels[gi][i]
        delay_ms = delays[gi][i]
        d.VelXY(speed, accel)
        d.VelZ(speed, accel)
        d.move2(...)
        light_ticks = 3
        apply_light(d, color, light_ticks)
        d.delay(delay_ms)
        current = target

prev = assigned_targets[-1]

# === AGENT_SEGMENT_END S03 ===
```

## 时间线和速度设置

- **VelXY 和 VelZ 最好成对设置，并使用相同 speed/accel**。这不是 PyFii API 本身的限制，而是为了兼容原始 XML/回放语义，避免水平与垂直运动按不同速度字段解释。
- **每个 keyframe 都要重新计算速度/加速度**；不要整段固定 `VelXY(200, 400)` 或只设置一次速度。

`move2()` 发起移动但不推进命令时间；`delay()` 和 `apply_light()` 才推进本机命令时间。因此正确链路是 `move2() -> 短灯光/执行等待 -> move2()`。不要每个 move 前都 `inittime()`；只在段首或明确绝对 cue 处使用。

- 先按音乐把段落拆成 keyframe interval，再为每个移动选择距离、速度和加速度。
- 如果移动太早结束，优先降低速度、增加路径弧度/中间 keyframe、改变高度层，或让分组错峰；不要在段尾补无运动长 delay。
- `delay()` 只有在紧跟一个正在执行的 `move2()`、用于给飞行留时间时才是合理的。
- 如果动作未完成(action warning)，先检查本次 `move2()` 后的 light+delay 是否覆盖飞行时间；必要时缩短距离、提速或增加该移动后的执行时间预算。

## 飞行时间公式

飞行时间估算属于 agent 侧运动学小工具，不要把 `dist3()` / `flight_time_ms()` / `speed_for_interval()` / `move_interval()` 定义进 segment 代码里。生成段代码前先用 3D distance 和梯形/三角速度曲线估算，再写入具体的 `speed`、`accel`、`delay_ms`。

核心模型：

- 3D distance = sqrt(dx² + dy² + dz²)。
- 加速距离 = v² / (2a)。
- 如果 distance >= 2 * 加速距离：有匀速段，time = 2v/a + (distance - 2 * 加速距离) / v。
- 如果 distance < 2 * 加速距离：只有加速/减速三角曲线，time = 2 * sqrt(distance / a)。

acceleration 是独立参数：`a = 2v` 只是某些 dntg/经验写法里的稳定候选，不能当硬规则。柔和动作可用较低 acceleration，利落动作可用较高 acceleration，但必须保持在合法范围内。

确保：
- 生成段代码前必须先算每个 keyframe interval 的距离和飞行时间。
- 对每个移动，`light_ticks * 100ms + delay_ms >= estimated_flight_ms(distance, v, a) + 100`。
- 如果音乐 interval 比飞行时间长很多，应调整路线和速度，让真实移动占据 interval 的主体，而不是补长 delay。

## 高度层

- 正式段不能全程固定高度；目标几何必须包含 low/mid/high 的高度层。
- 至少一半无人机在本段内有明显 Z 变化，通常 >=25cm。
- 速度预算用 3D 距离 `sqrt(dx² + dy² + dz²)`，不要只用 XY；这是 agent 侧估算，不要在段代码里新增 helper。

## 错误处理

| 错误 | 原因 | 修复 |
|------|------|------|
| `Out of range` | XY超出[0,560]或Z超出[80,250] | clamp坐标 |
| `Time arrangement error` | inittime倒退或段间冲突 | 推后inittime |
| `action isn't completed` | 下一条移动开始太早或飞行时间预算不够 | 计算本次 move2 的飞行时间，提速/缩短距离/增加该移动后的执行时间 |
| `distance between` | 两机<51cm | 增间距或提搜索权重 |
| `ValueError: invalid literal` | 坐标含浮点数 | int(round(x)) |

- **不要复制 best_assign、motion_math、planning_tools 的定义到 design.py**，这些是离线工具，只需使用计算结果。
- **每个 move2 必须给足够时间完成动作**：delay >= flight_time_ms + margin。动作未完成是硬错误。
- **S01 可接受车道退化，但 S02 必须跳出**：换几何语言、换空间组织方式、换高度层次。

- **起飞**: `drone.X=drone.x=x; drone.Y=drone.y=y; drone.takeoff(1, z)`
- **降落**: `drone.land()` 或 `drone.end()`，LAND段内agent自主安排时间
- **VelXY 和 VelZ 在同一 move 中值必须一致，但每次 move2 前可修改**
- **agent 可在 `function.py` 中自定义辅助函数**（纯Python标准库+math，不导入pyfii）
- **每个几何使用不同 Z 高度**，产生三维层次感，不要所有几何在同一平面
- **相邻段不能使用相同退化类型**（如S01车道退化→S02必须跳出），最佳是零退化
