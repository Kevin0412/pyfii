# Pyfii 飞行模型教程（Agent 必读）

## 物理模型

无人机飞行的物理模型：move2(x,y,z) 让无人机从当前位置飞向目标，耗时由 VelXY 设定的速度和加速度决定。

```
飞行时间(秒) = 加速段 + 匀速段
- 如果距离短(< v²/a)：纯加速，t = 2√(d/a)
- 如果距离长(≥ v²/a)：t = 2v/a + (d-v²/a)/v
```

`flight_time_ms(d, v, a)` 是 agent 规划层工具；final `design.py` 里不要调用它。final 代码应写已经预算好的 `flying_ms` 常量。

## 核心工作流

每个 move2 的正确写法是使用 `function.py` 的包装器，不要裸调 `drone.VelXY` / `drone.VelZ` / `drone.move2`：

```python
flying_ms = 3200  # 规划阶段已算好
move2(drone, (tx, ty, tz), flying_ms)
apply_light(drone, color, 4)  # 4 ticks * 100ms = 400ms
drone.delay(max(0, flying_ms - 4*100 + 100))
```


## 核心概念：动作编排 vs 排列

编排不是机械分配目标点。编排目标：所有无人机轨迹在空间中不重合。每架机有独立轨迹，但关键是轨迹间要安全分离（方向错开、高度错层、时间错峰）：

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
    move2(drone, (tx, ty, tz), flying_ms)
```

条件分支 + 相对移动 + 高度错层 = dntg 的安全策略。

### 方式B：best_assign（工具辅助）

当手动设计困难时，用 `function.py` 里的 `best_assign(prev, geo)` 计算机械最优排列：

```python
geo = [(120,160,150), ...]  # 7 个完整 (x,y,z)
targets = best_assign(prev, geo)
```

**best_assign 返回重排后的 targets 列表，不返回 `(perm, min_d)`，不要拆包。** 能手动设计就不要机械调用。

## 时间预算

生成前必须先计算总时间：

```python
total_ms = 0
for move in all_moves:  # 规划阶段，不复制进 final segment
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

## 分配函数时序模型

分配函数决定"哪架机飞哪个目标"——但它们的安全判断依赖时序假设：

| 函数 | 时序假设 | 采样密度 | 适用场景 |
|------|---------|---------|---------|
| `best_assign` | 全员同步(delays=0) | 5 点 | 同步非交叉小动作 |
| `far_assign` | 全员同步(delays=0) | 51 点 | 同步大交换 |
| `safe_assign` | **真实错峰(delays=传入值)** | **60fps** | 错峰/分组/任何有 delays 的场景 |
| `safe_move` | 内部调 safe_assign | 60fps | 推荐默认 |

**规则：如果执行时有 delays（ripple_move / drone.delay），分配必须用 `safe_assign` 或 `safe_move`。** `best_assign`/`far_assign` 假设全员同步，在错峰时序下保证无效——preflight 会拦截这种不匹配。

正确组合：
```python
delays = ripple_delays(prev, mode='by_index', step_ms=130)
targets = safe_assign(prev, geo, delays=delays, flying_ms=2800)  # 同一 delays
prev = ripple_move(drones, targets, 2800, delays)                # 同一 delays
```

或一步到位：
```python
prev = safe_move(drones, prev, geo, 2800, mode="wave")
```

## 常见错误

| 错误 | 后果 | 正确做法 |
|------|------|---------|
| `delay = 1500` 固定 | 动作未完成或冗余悬停 | 用 flight_time_ms 计算 |
| `perm = (0,1,...,6)` 恒等 | 碰撞 (minD < 51cm) | 用 best_assign |
| 裸调 VelXY/drone.move2 | preflight 拒绝 | 用 `move2(drone, target, flying_ms)` 包装器 |
| 直接写 inittime | preflight 拒绝 | S01 用 `wait_until`，S02+ 用 `auto_init` |
| 未计算总时间 | delay 超边界 | 生成前先算预算 |

- **agent 可以在 `function.py` 中添加自定义函数**（如 best_assign 排列实现），不需要外部注入

- **每个 move2 后 delay 留 100-200ms 余量**，确保动作完整执行（dntg 经验）
