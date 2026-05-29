# Pyfii 编舞

## 核心 API
```python
move2(d, (x,y,z), t_ms)   # 反算速度+飞行，不要额外 delay
apply_light(d, "#RRGGBB", ticks)
best_assign(prev, geo)
safe_geo(mode)             # 算法保证7点间距≥120cm
```

## safe_geo 模式
| 模式 | 半径 | 适用于 |
|------|------|--------|
| expand | 泊松圆盘采样 | 推进/展开 |
| rotate | 150cm环+1中心 | 高潮/旋转 |
| breathe | 120-220cm呼吸 | 过渡 |
| contract | 80-130cm收缩 | 收束/降落 |

## 代码模板
```python
geo = safe_geo('expand')
targets = best_assign(prev, geo)
for i, drone in enumerate(drones):
    tx, ty, tz = clamp_xy(targets[i][0]), clamp_xy(targets[i][1]), clamp_z(targets[i][2])
    move2(drone, (tx, ty, tz), 3500)
    apply_light(drone, '#ff6644', 4)
    drone.delay(3500 + 400)
prev = [(targets[i][0], targets[i][1], targets[i][2]) for i in range(7)]
```

## 规则
- 不用 inittime / VelXY / flight_time_ms
- 不用 drone.x = tx
- 不用同心圆
- 每段尾更新 prev
