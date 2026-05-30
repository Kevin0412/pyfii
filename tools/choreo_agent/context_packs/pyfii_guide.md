# Pyfii 编舞 — 只能用函数，不能写坐标

```python
geo = generate_safe_geo(prev, 'expand')
targets = best_assign([(p[0],p[1]) for p in prev], [(g[0],g[1]) for g in geo])
for i, drone in enumerate(drones):
    drone.delay(i * 80)
    tx, ty, tz = targets[i][0], targets[i][1], targets[i][2]
    ft = flight_time_ms(((tx-px)**2+(ty-py)**2+(tz-pz)**2)**0.5, 120, 200)
    drone.VelXY(120, 200); drone.VelZ(120, 200)
    move2(drone, (tx, ty, tz), ft)
    apply_light(drone, '#44aaff', 4)
    drone.delay(ft + 300)
prev = [(targets[i][0], targets[i][1], targets[i][2]) for i in range(7)]
```

generate_safe_geo mode: expand / rotate / breathe / contract
best_assign: 最优排列
flight_time_ms: 飞行时间

**重要：不要写坐标数字！用 generate_safe_geo。**
