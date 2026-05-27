# Pyfii 真实 API 教程（基于源码）

pyfii 不在模型训练集中。以下是从 `src/pyfii/drone.py` 提取的真实行为。

## 时间系统

`drone.intime(秒)` — 跳到指定时间点（四舍五入到整数）。不能倒退。
`drone.delay(毫秒)` — 从当前时间点往后推。move2后必须跟delay给飞行留时间。

错误示例：`drone.intime(4); drone.move2(...); drone.intime(5)` — 第二个intime会因时间倒退抛"Time arrangement error"。

## 起飞

```python
drone.X = drone.x = 280   # 必须同时设X和x
drone.Y = drone.y = 280   # 必须同时设Y和y
drone.takeoff(1, 110)     # 1秒起飞到110cm
```
`takeoff`之后：`drone.x/y/z`表示起飞后的悬停位置。

## 移动

```python
drone.VelXY(速度cm/s, 加速度cm/s²)
drone.VelZ(速度cm/s, 加速度cm/s²)
drone.move2(目标x, 目标y, 目标z)
drone.delay(飞行所需毫秒)
```

`move2`只定义目标不推进时间——飞行时间由`delay`提供。
`VelXY`和`VelZ`必须在`move2`之前设置。

## 排列

```python
# 方式1: 直接映射（当起点排列自然合理时）
targets = geo[gi]

# 方式2: best_assign（当起点排列可能导致交叉时）
targets = best_assign(prev, geo[gi])
```

## 禁止发明
以下不存在，永远不要用：
- `drone.VelXY_speed` / `drone.speed` / `drone.vel`
- `pyfii.movej()` / `pyfii.set_time()` / `pyfii.best_assign()`
- `drone.fly_to()` / `drone.go()`

## 参考示例

以下是一段正确 pyfii 代码的结构（模仿此模式，换你自己的坐标）：

```python
geo = [(80+80*i, 80+80*i, 140) for i in range(7)]
geo2 = [(80,80,160),(480,80,160),(80,480,160),(480,480,160),(280,280,170),(200,200,160),(360,360,160)]
geo3 = [(100+60*i, 200+120*math.sin(i), 180) for i in range(7)]

for i, d in enumerate(drones):
    d.inittime(23)
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
        apply_light(d, "#2255aa", 12); d.delay(1200)
    prev = targets
```

## 排列策略（参考 crosscut）

crosscut 不用 best_assign，而是用 `choose_targets` 自己的排列算法。核心思路：

```python
def choose_targets(start_points, raw_targets):
    """对每个起点，找距离最近且未被占用的目标点"""
    used = [False] * len(raw_targets)
    result = [None] * len(start_points)
    for i, sp in enumerate(start_points):
        best_j, best_d = -1, float('inf')
        for j, tp in enumerate(raw_targets):
            if used[j]: continue
            d = math.hypot(sp[0]-tp[0], sp[1]-tp[1])
            if d < best_d: best_d = d; best_j = j
        used[best_j] = True
        result[i] = raw_targets[best_j]
    return result
```

也可以每段预定义坐标列表（PHRASE_STATES 模式）——人类设计关键状态，agent 只处理过渡。

## 速度计算

```python
def travel_time(distance_cm, speed, acc):
    accel_dist = speed*speed/(2*acc)
    if distance >= 2*accel_dist:
        return 2*speed/acc + (distance-2*accel_dist)/speed
    return 2*math.sqrt(distance/acc)

def speed_for_segment(distance_cm, duration_sec):
    """给定距离和时间，反算速度"""
    for v in range(50, 201):
        if travel_time(distance_cm, v, v*2) < duration_sec:
            return v
    return 200
```
