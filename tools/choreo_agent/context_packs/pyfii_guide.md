# Pyfii 编舞 — 数学工具驱动

## 可用数学工具（agent 侧使用）
```python
generate_safe_geo(prev, mode, n=7, min_spacing_cm=120)
# 模式: expand/rotate/breathe/contract
# 返回: 7个(x,y,z)，保证XY间距>=120cm

best_assign(prev_xy, geo_xy)
# 返回: (permutation, min_distance_cm)

predict_crossings(prev, geo)
# 返回: [(i, j, closest_cm), ...] 按最近距离排序

flight_time_ms(dist_3d, speed_cm_s, accel_cm_s2)
# 返回: 飞行时间(ms)
```

## 编舞流程
1. 根据意图选 mode → `geo = generate_safe_geo(prev, mode)`
2. 检查间距：确保 min spacing >= 100cm
3. `best_assign(prev, geo)` 排列
4. 检查路径：`predict_crossings(prev, geo)` — 如果 worst < 80cm，加 `drone.delay(i * 80)` 错峰
5. 每 keyframe：计算 `flight_time_ms`，设 `VelXY/VelZ`，`move2 + apply_light + delay`
6. 更新 `prev`

## 代码模板
```python
prev = [(d.x, d.y, d.z) for d in drones]

# Keyframe 1 (13-18s): expand
geo1 = generate_safe_geo(prev, 'expand')
targets1 = best_assign([(p[0],p[1]) for p in prev], [(g[0],g[1]) for g in geo1])
for i, drone in enumerate(drones):
    drone.delay(i * 80)  # 错峰避免路径交叉
    tx, ty, tz = clamp_xy(targets1[i][0]), clamp_xy(targets1[i][1]), clamp_z(targets1[i][2])
    d3d = ((tx-drone.x)**2+(ty-drone.y)**2+(tz-drone.z)**2)**0.5
    ft = flight_time_ms(d3d, 120, 200)
    drone.VelXY(120, 200); drone.VelZ(120, 200)
    move2(drone, (tx, ty, tz), ft)
    apply_light(drone, '#44aaff', 4)
    drone.delay(ft + 300)
prev = [(targets1[i][0], targets1[i][1], targets1[i][2]) for i in range(7)]

# Keyframe 2 (18-23s): rotate
geo2 = generate_safe_geo(prev, 'rotate')
targets2 = best_assign([(p[0],p[1]) for p in prev], [(g[0],g[1]) for g in geo2])
for i, drone in enumerate(drones):
    tx, ty, tz = clamp_xy(targets2[i][0]), clamp_xy(targets2[i][1]), clamp_z(targets2[i][2])
    d3d = ((tx-drone.x)**2+(ty-drone.y)**2+(tz-drone.z)**2)**0.5
    ft = flight_time_ms(d3d, 100, 180)
    drone.VelXY(100, 180); drone.VelZ(100, 180)
    move2(drone, (tx, ty, tz), ft)
    apply_light(drone, '#ff8844', 4)
    drone.delay(ft + 300)
prev = [(targets2[i][0], targets2[i][1], targets2[i][2]) for i in range(7)]
```

## 规则
- 不用 inittime（auto_init 处理）
- 不用 safe_geo 模块——generate_safe_geo 在 function.py 中
- 必须加 drone.delay(i*80) 错峰
- 每 keyframe 用不同速度和颜色
