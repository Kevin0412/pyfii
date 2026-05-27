# Pyfii 飞行模型教程（Agent 必读）

## 物理模型

无人机飞行的物理模型：move2(x,y,z) 让无人机从当前位置飞向目标，耗时由 VelXY 设定的速度和加速度决定。

```
飞行时间(秒) = 加速段 + 匀速段
- 如果距离短(< v²/a)：纯加速，t = 2√(d/a)
- 如果距离长(≥ v²/a)：t = 2v/a + (d-v²/a)/v
```

`flight_time_ms(d, v, a)` 已封装在 `function.py` 中，直接调用。

## 核心工作流

每个 move2 的正确写法：

```python
# 1. 设置速度（同一move内VelXY=VelZ）
drone.VelXY(150, 300)  # 速度150cm/s, 加速度300cm/s²
drone.VelZ(150, 300)

# 2. 执行移动
drone.move2(tx, ty, tz)

# 3. 计算飞行时间
d = distance_3d(prev[i], (tx, ty, tz))
ft = flight_time_ms(d, 150, 300)

# 4. 灯光（在delay之前或之后）
apply_light(drone, color, 15)  # 15 ticks × 100ms = 1500ms

# 5. 延迟 = 飞行时间 - 灯光占用 + 余量
delay_ms = max(0, ft - 15*100 + 150)  # +150ms 余量
drone.delay(delay_ms)
```

## 排列（best_assign）

每段设计多个几何。几何间的过渡排列用 `best_assign` 计算：

```python
# 几何定义
geo1 = [(x1,y1,z1), (x2,y2,z2), ...]

# 前段出口位置
prev_xy = [(px, py) for px, py, pz in prev]

# 计算最优排列
perm, min_d = best_assign(prev_xy, [(x,y) for x,y,z in geo1])
# 结果: perm = (3, 0, 5, 1, 4, 6, 2)  ← 硬编码到代码中
#       min_d = 89.3cm  ← 确保 > 51cm
```

**不要用恒等映射 `perm = (0,1,2,3,4,5,6)`**。每次都用 best_assign。

## 时间预算

生成前必须先计算总时间：

```python
total_ms = 0
for move in all_moves:
    d = distance_3d(prev[i], target[i])
    total_ms += flight_time_ms(d, v, a) + light_ticks*100 + 150

total_s = total_ms / 1000
# 必须满足: total_s + 1.0 < end_time - start_time
```

## 起飞

```python
drone.X = drone.x = x_pos    # 物理起点
drone.Y = drone.y = y_pos    # 逻辑起点（后续相对移动的参考）
drone.takeoff(1, 110)        # 飞到高度110cm
```

## 常见错误

| 错误 | 后果 | 正确做法 |
|------|------|---------|
| `delay = 1500` 固定 | 动作未完成或冗余悬停 | 用 flight_time_ms 计算 |
| `perm = (0,1,...,6)` 恒等 | 碰撞 (minD < 51cm) | 用 best_assign |
| VelXY ≠ VelZ | 动作不一致 | 每次move前同时设置 |
| 未计算总时间 | inittime + delay 超边界 | 生成前先算预算 |
