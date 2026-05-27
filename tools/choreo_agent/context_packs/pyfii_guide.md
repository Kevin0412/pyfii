# Pyfii 编舞编程指南

pyfii 是自定义无人机编舞库，不在 LLM 训练集中。以下是你需要的全部知识。

## 核心 API

```python
drone.X = drone.x = 280   # 必须同时设置 X 和 x
drone.Y = drone.y = 280
drone.takeoff(1, 110)     # 1秒后起飞到110cm

drone.intime(秒)          # 跳到指定时间（四舍五入整数），不能倒退
drone.delay(毫秒)          # 从当前时间点往后推

drone.VelXY(速度cm/s, 加速度cm/s²)
drone.VelZ(速度cm/s, 加速度cm/s²)
drone.move2(目标x, 目标y, 目标z)
# move2 后必须跟 delay，否则动作未完成
```

## function.py 已有函数

```python
clamp_xy(v)   # 限制坐标在合法范围
clamp_z(v)
flight_time_ms(distance_cm, speed, acc)  # 返回毫米级飞行时间
apply_light(drone, color, light_id)
best_assign(prev, targets)  # 返回最优排列
```

## 正确代码模式

```python
# 几何定义
geo = [(80,80,130),(480,80,130),(80,480,130),(480,480,130),(280,280,140),(160,160,130),(400,400,130)]

for i, d in enumerate(drones):
    d.inittime(START_SEC)
    d.VelXY(120, 240); d.VelZ(120, 240)
    d.delay(i * 80)

# 每个 keyframe 都要更新 drone.x/y/z
targets = best_assign(prev, geo)
for i, d in enumerate(drones):
    dd = math.hypot(prev[i][0]-targets[i][0], prev[i][1]-targets[i][1])
    spd = min(200, max(120, int(dd/2.0)))
    d.VelXY(spd, spd*2); d.VelZ(spd, spd*2)
    d.move2(clamp_xy(targets[i][0]), clamp_xy(targets[i][1]), clamp_z(targets[i][2]))
    apply_light(d, "#2255aa", 6)
    ft = flight_time_ms(dd, spd, spd*2)
    d.delay(max(400, ft + 100))
    d.x, d.y, d.z = targets[i][0], targets[i][1], targets[i][2]  # 更新追踪

prev = [(t[0], t[1], t[2]) for t in targets]
```

## 禁止
- **不要加任何 import** — design.py 头部已导入所有需要的模块
- 不要写 

- 不发明不存在属性（d.VelXY_speed、drone.speed 等）
- 不写恒等排列 perm=(0,1,2,3,4,5,6) — 用 best_assign
- 不用同心圆几何 — 用非对称几何（四角、对角、V形）
- move2 后必须跟 delay（≥ flight_time_ms + 100ms）
