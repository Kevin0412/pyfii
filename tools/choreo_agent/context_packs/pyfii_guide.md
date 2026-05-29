# Pyfii 编舞 — LLM 自主设计几何

## 核心 API
```python
move2(d, (x,y,z), t_ms)   # 反算速度+飞行，不要额外 delay
apply_light(d, "#RRGGBB", ticks)
best_assign(prev, geo)     # 找最优排列
```

## 坐标设计原则
- 根据 prev 坐标分布设计 geo
- 两两 XY 间距 >= 120cm（在 560x560 场地内）
- 利用 prev 已有分布：扩散/旋转/收束
- Z 轴 100-250cm 渐进变化
- 配合音乐意图（展开用大间距，呼吸用环，收束用小间距）

## 代码模板
```python
geo = [(x1,y1,z1), (x2,y2,z2), ...]  # 7个坐标
targets = best_assign(prev, geo)
for i, drone in enumerate(drones):
    drone.delay(i * 80)
    tx, ty, tz = clamp_xy(targets[i][0]), clamp_xy(targets[i][1]), clamp_z(targets[i][2])
    move2(drone, (tx, ty, tz), 3500)
    apply_light(drone, '#ff6644', 4)
    drone.delay(3500 + 400)
prev = [(targets[i][0], targets[i][1], targets[i][2]) for i in range(7)]
```

## 规则
- 不用 safe_geo —— 自己算坐标
- 不用 inittime / VelXY
- 每段尾更新 prev
