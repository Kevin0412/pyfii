# Pyfii 编舞 — DNTG 风格

## 只有一个核心 API

```python
move2(d, (x, y, z), t_ms)
```

- `d`: 无人机对象
- `(x, y, z)`: 目标坐标 (cm)，xy∈[0,560]，z∈[80,250]
- `t_ms`: 总时间 (ms)，内部自动反算速度 + VelXY + move2 + delay

## 起飞

```python
d.X = d.x = clamp_xy(x0)
d.Y = d.y = clamp_xy(y0)
d.takeoff(1, z0)              # 1秒后起飞到z0(cm)
```

## 相对移动

```python
move2(d, (d.x+dx, d.y+dy, d.z+dz), t_ms)
```

## 排列

```python
targets = best_assign(prev, geo)
```

## 灯光

```python
apply_light(d, "#RRGGBB", ticks)
```

## 完整段模板

```python
geo = [(x1,y1,z1), (x2,y2,z2), ...]   # 非对称几何，间距≥200cm
geo2 = [(x1,y1,z1), ...]

for i, d in enumerate(drones):
    d.inittime(START_SEC)
    d.delay(i * 80)

for gi in range(2):
    geos = [geo, geo2]
    targets = best_assign(prev, geos[gi]) if gi > 0 else geos[gi]
    for i, d in enumerate(drones):
        move2(d, (clamp_xy(targets[i][0]), clamp_xy(targets[i][1]), clamp_z(targets[i][2])), 1200)
        apply_light(d, "#2255aa", 5)
        d.x, d.y, d.z = targets[i]   # 更新追踪
    prev = [(d.x, d.y, d.z) for d in drones]
```

## 关键：move2 调用方式

正确: move2(d, (x, y, z), t_ms)  -- function.py 封装
错误: d.move2(x, y, z)           -- 不要用底层 Drone 方法
错误: d.move2(x, y, z, t_ms)     -- 不存在四参数

## 禁止
- 不添加任何 import
- 不调用 d.VelXY/VelZ/delay/move2 底层 API — 只用 move2(d, p, t)
- 不发明不存在属性
- 不同心圆
