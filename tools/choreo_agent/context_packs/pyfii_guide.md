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
## 代码模板（严格复制此模式，只替换坐标）

```python
geo = [(x1,y1,z1), ..., (x7,y7,z7)]
geo2 = [(x1,y1,z1), ..., (x7,y7,z7)]

for i, drone in enumerate(drones):
    drone.inittime(13)
    drone.delay(i * 80)

for gi in range(2):
    geos = [geo, geo2]
    targets = best_assign(prev, geos[gi]) if gi > 0 else geos[gi]
    for i, drone in enumerate(drones):
        tx, ty, tz = targets[i]
        move2(drone, (tx, ty, tz), 3500)
        apply_light(drone, "#2255aa", 5)
        drone.x, drone.y, drone.z = tx, ty, tz
    prev = [(drone.x, drone.y, drone.z) for drone in drones]
```

注意：move2(drone, ..., 3500) 内部已完成 delay(3500)，**不要**再写 drone.delay(...)。


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

正确: move2(d, (x, y, z), t_ms)  -- function.py 封装，内部已完成 VelXY+move2+delay，不要额外加 delay
错误: move2(d, p, t) 之后又写 d.delay(...) -- 会重复计时导致时间溢出
错误: d.move2(x, y, z)           -- 不要用底层 Drone 方法
错误: d.move2(x, y, z, t_ms)     -- 不存在四参数

## 段代码是片断，不是完整脚本

只写段内动作逻辑。**不要写**：
- PYFII_AGENT_SEGMENT_START/END 标记
- drones = [...] 或 Drone(...) 创建
- prev = [...] 硬编码
- import 语句

段代码嵌入到已有 design.py 的 marker 之间执行，drones 和 prev 已存在。


## 非对称几何安全模式（已验证）

第一步：小幅度呼吸（从 prev 偏移 30-40cm）
第二步：非对称大展开（四角/散射/V形，间距≥200cm）

```python
geo1 = [(prev[i][0] + 35*math.sin(i*2.5), prev[i][1] + 35*math.cos(i*2.5), Z1) for i in range(7)]
geo2 = [(x1,y1,z2), ..., (x7,y7,z2)]  # 非对称坐标

for gi in range(2):
    geos = [geo1, geo2]
    targets = best_assign(prev, geos[gi]) if gi > 0 else geos[gi]
    ...
```

关键：第一步小幅度移动让 best_assign 正确排列，第二步大跳时才不会交叉。

## 必须
- 每段结束时必须：prev = [(drone.x, drone.y, drone.z) for drone in drones]


## 已验证通过的具体代码示例

### S02 (13-23s) 通过示例
```python
geo1 = [(prev[i][0] + 40*math.sin(i*2), prev[i][1] + 40*math.cos(i*2), 140) for i in range(7)]
geo2 = [(100,120,170),(280,80,190),(460,140,170),(420,380,180),(200,420,160),(340,340,200),(160,260,180)]
for i, drone in enumerate(drones):
    drone.inittime(13); drone.VelXY(120, 240); drone.VelZ(120, 240); drone.delay(i * 80)
for gi in range(2):
    geos = [geo1, geo2]
    targets = best_assign(prev, geos[gi]) if gi > 0 else geos[gi]
    for i, drone in enumerate(drones):
        tx, ty, tz = targets[i]
        dd = math.hypot(prev[i][0]-tx, prev[i][1]-ty)
        spd = min(200, max(100, int(dd/2.0)))
        drone.VelXY(spd, spd*2); drone.VelZ(spd, spd*2)
        drone.move2(clamp_xy(tx), clamp_xy(ty), clamp_z(tz))
        apply_light(drone, '#44aadd', 6)
        ft = flight_time_ms(((tx-prev[i][0])**2+(ty-prev[i][1])**2+(tz-prev[i][2])**2)**0.5, spd, spd*2)
        drone.delay(max(800, int(ft*1.2)))
    prev = [(targets[i][0], targets[i][1], targets[i][2]) for i in range(7)]
```


## 禁止
- 不添加任何 import
- 不调用 d.VelXY/VelZ/delay/move2 底层 API — 只用 move2(d, p, t)
- 不发明不存在属性
- 不同心圆
