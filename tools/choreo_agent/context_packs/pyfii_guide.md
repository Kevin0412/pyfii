# Pyfii 编舞 API

## 核心 API（from function import *）
```python
move2(d, (x,y,z), t_ms, T=100)
# 反算速度 → VelXY(v,2v)+VelZ(v,2v) → d.move2(x,y,z)。
# 不推进时间游标；但记录预计飞行结束时间，供 auto_init 防止下一段提前开始。

apply_light(d, "#RRGGBB", ticks)
# ticks次TurnOnAll，每次delay 100ms。推进 cursor: ticks*100ms。

best_assign(prev, geo)
# 遍历全排列找最小路径间距最大的分配。返回 targets 列表。

clamp_xy(v)  # [0, 560]
clamp_z(v)   # [80, 250]
```

## 时序模型（每次移动）
```python
move2(drone, (tx, ty, tz), flying_ms)           # 1. 发起飞行
apply_light(drone, '#color', ticks)              # 2. 灯光 (推进 ticks*100ms)
drone.delay(max(0, flying_ms - ticks * 100))     # 3. 等待飞行完成
```

最后一个 move2 后面如果没有显式 delay，下一段开始前必须调用 `auto_init(drones)`，
它会按 `Drone.time` 和 helper 记录的未完成移动时间，把下一段推迟到动作完成之后。

## 起飞
```python
drone.X = drone.x = x
drone.Y = drone.y = y
drone.takeoff(1, height_cm)
drone.delay(3000)
```

## 禁止
- d.VelXY / d.VelZ 裸调
- d.move2() 裸调（必须用 function.py 的 move2）
- inittime() 调用（时间游标由 takeoff/delay/move 链自然推进）
- import 新模块
