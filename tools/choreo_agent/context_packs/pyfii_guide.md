# Pyfii 编舞 — DNTG 完整模式

## 核心 API
```python
move2(d, (x,y,z), t_ms)           # 反算速度+飞行（内部已含 delay）
drone.VelXY(v, a); drone.VelZ(v, a)  # 手动设速度加速度
best_assign(prev, geo)             # 最优排列
flight_time_ms(dist, v, a)         # 计算飞行时间
apply_light(d, "#RRGGBB", ticks)   # 灯光，ticks×100ms
clamp_xy(v), clamp_z(v)            # 边界钳制
```

## 编舞流程
1. 根据 prev 分布设计 geo 坐标（7个(x,y,z)，XY间距>=100cm，Z 100-250cm）
2. `best_assign(prev, geo)` 求最优排列
3. 对每个 keyframe：`VelXY + VelZ` 设速度，`move2 + delay` 执行
4. 用 `flight_time_ms(d, v, a)` 算 delay 值
5. 每段尾更新 `prev`

## 代码模板
```python
prev = [(d.x, d.y, d.z) for d in drones]

# Keyframe 1: 展开
v1, a1 = 120, 200
geo1 = [(110,140,130),(210,185,148),(280,265,168),(420,190,145),(495,340,130),(370,420,145),(210,400,130)]
targets = best_assign(prev, geo1)
for i, drone in enumerate(drones):
    tx, ty, tz = clamp_xy(targets[i][0]), clamp_xy(targets[i][1]), clamp_z(targets[i][2])
    drone.VelXY(v1, a1); drone.VelZ(v1, a1)
    d_3d = ((tx-drone.x)**2+(ty-drone.y)**2+(tz-drone.z)**2)**0.5
    ft = flight_time_ms(d_3d, v1, a1)
    move2(drone, (tx, ty, tz), ft)
    apply_light(drone, '#ff6644', 4)
    drone.delay(ft + 300)
prev = [(targets[i][0], targets[i][1], targets[i][2]) for i in range(7)]
```

## 规则
- 不用 inittime（auto_init 处理）
- 不用 safe_geo —— 自己设计坐标
- 2-3 个 keyframe，速度/方向有变化
- Z 轴渐进（100→150→200→150）
