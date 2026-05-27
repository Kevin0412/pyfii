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


## 核心概念：动作编排 vs 排列

编排不是机械分配目标点。每架无人机有自己的运动轨迹：

- 不同的机可以走**不同的方向**（左右分流）
- 不同的机可以走**不同的速度**（快机大步、慢机细腻）
- 不同的机可以走**不同的高度**（高层掠影、低层穿行）
- 不同的机可以走**不同的路径形状**（直飞、弧线、折线）

DNTG 每段给不同机设计了独特路径——不是"全部飞向环"，而是"左机左移、右机右移、中心机上升"。

## 排列设计

几何间的无人机-目标点映射（排列）影响安全性。两种方式：

### 方式A：手动设计（推荐）

根据空间关系手动分配——让靠近左边起点的机继续走左边，避免交叉：

```python
# 条件分支：不同机走不同方向
for i, drone in enumerate(drones):
    if i < 3:     # 左组 → 左弧
        tx, ty = left_arc[i]
    else:         # 右组 → 右弧
        tx, ty = right_arc[i-3]
    drone.move2(tx, ty, tz)
```

条件分支 + 相对移动 + 高度错层 = dntg 的安全策略。

### 方式B：best_assign（工具辅助）

当手动设计困难时，用 `best_assign(prev_xy, geo_xy)` 计算机械最优排列：

```python
perm, min_d = best_assign(prev_xy, [(x,y) for x,y,z in geo])
# 硬编码结果: perm = (3, 0, 5, 1, 4, 6, 2)
```

**best_assign 是工具不是唯一解**。能手动设计就不要机械调用。

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
