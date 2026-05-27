# Pyfii 编舞教程（Agent 必读）

pyfii 是自定义无人机编舞库，不在模型训练集中。以下是你需要知道的全部内容。

## 必须导入

```python
from function import clamp_xy, clamp_z, distance_3d, flight_time_ms, apply_light, best_assign
```

## 每段的固定模板

```python
geo = [(x1,y1,z1), (x2,y2,z2), ...]   # 几何点
geo2 = [(x1,y1,z1), ...]
geo3 = [(x1,y1,z1), ...]

for i, d in enumerate(drones):
    d.inittime(START_TIME)
    d.VelXY(120, 240); d.VelZ(120, 240)
    d.delay(i * 100)

for gi in range(3):
    geos = [geo, geo2, geo3]
    targets = geos[gi] if gi == 0 else best_assign(prev, geos[gi])
    for i, d in enumerate(drones):
        dd = math.hypot(prev[i][0]-targets[i][0], prev[i][1]-targets[i][1])
        spd = min(200, max(120, int(dd/2.0)))
        d.VelXY(spd, spd*2); d.VelZ(spd, spd*2)
        d.move2(clamp_xy(targets[i][0]), clamp_xy(targets[i][1]), clamp_z(targets[i][2]))
        apply_light(d, color, 12); d.delay(1200)
    prev = targets
```

## 起飞（仅 S01）

```python
S = [(60,120),(180,60),(350,60),(500,160),(500,380),(350,480),(160,480)]
for i, d in enumerate(drones):
    d.X = d.x = S[i][0]; d.Y = d.y = S[i][1]
    d.takeoff(1, 110)
prev = [(d.x, d.y, 110) for d in drones]
```

## 几何设计

禁止同心圆（所有点在同一半径的圆上）——必然碰撞。
使用：对角线、四角、双排、V形、扇形、散射。
```

## 禁止

- 不用恒等排列 perm=(0,1,2,3,4,5,6) — 用 best_assign
- 不自创函数名 — 只用上面列出的
- 不在注释中算 best_assign — 必须出现在代码中
```
