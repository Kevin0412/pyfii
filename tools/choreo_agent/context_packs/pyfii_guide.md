# Pyfii 编舞 — 数学工具驱动

## 核心 API
```python
move2(d, (x,y,z), t_ms)           # 反算速度+飞行（内部已含 delay）
best_assign(prev, geo)             # 最优排列
apply_light(d, "#RRGGBB", ticks)   # 灯光，ticks×100ms
clamp_xy(v), clamp_z(v)            # 边界钳制
```

## 工作流程
1. 从预计算 geo 候选中选择一个（或组合两个作为 keyframe1/2）
2. `best_assign(prev, geo)` 求最优排列
3. 每 keyframe：`move2 + apply_light + delay`
4. 每段尾更新 `prev`

## 代码模板
```python
prev = [(d.x, d.y, d.z) for d in drones]

# Keyframe 1: 使用候选坐标
geo1 = [(377,107,106),(175,164,135),(396,429,239),(94,352,208),(66,65,123),(329,264,156),(192,464,101)]
targets1 = best_assign(prev, geo1)
for i, drone in enumerate(drones):
    tx, ty, tz = clamp_xy(targets1[i][0]), clamp_xy(targets1[i][1]), clamp_z(targets1[i][2])
    move2(drone, (tx, ty, tz), 3500)
    apply_light(drone, '#44aaff', 4)
    drone.delay(3500 + 400)
prev = [(targets1[i][0], targets1[i][1], targets1[i][2]) for i in range(7)]
```

## 规则
- 不用 inittime（auto_init 处理）
- 不用 safe_geo —— 直接复制预计算候选
- 2 个 keyframe，不同候选或相同候选的不同速度
