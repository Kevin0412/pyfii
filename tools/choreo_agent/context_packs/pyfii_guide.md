# Pyfii 编舞 API

## 核心 API（from function import *）
```python
move2(d, (x,y,z), t_ms, T=100)
# 反算速度 → VelXY(v,2v)+VelZ(v,2v) → d.move2(x,y,z)。
# 不推进时间游标；但记录预计飞行结束时间，供 auto_init 防止下一段提前开始。

apply_light(d, "#RRGGBB", ticks)
# ticks次TurnOnAll，每次delay 100ms。推进 cursor: ticks*100ms。

d.land()
# 降落段使用。LAND 段先 auto_init(drones)，可短灯光提示后对每架机 d.land()。

best_assign(prev, geo)
# 遍历全排列找最小路径间距最大的分配。返回重排后的 targets 列表；不要拆 perm/min_d。

far_assign(prev, geo, min_path_cm=90)
# 安全但鼓励远距离交换的分配。S04/S05、高潮、回卷、分组交换、或验证反馈
# “路径太短/小范围抖动”时使用；不要继续用相似几何 + best_assign 生成小挪动。

clamp_xy(v)  # [0, 560]
clamp_z(v)   # [80, 250]
```

## 时序模型（每次移动）
```python
move2(drone, (tx, ty, tz), flying_ms)           # 1. 发起飞行
apply_light(drone, '#color', ticks)              # 2. 灯光 (推进 ticks*100ms)
drone.delay(max(0, flying_ms - ticks * 100))     # 3. 等待飞行完成
```

这三步必须在同一个 per-drone loop 内作用到每架机。禁止在全队 `move2` 后只写
`apply_light(drones[0], ...)` 或 `drones[0].delay(...)`；那会导致其他机没有执行时间。

正式段主体移动不要用 4500ms 以上的慢速拖时长；常用 2000-3600ms。
如果段长需要覆盖，用多个快 keyframe、分组错峰或高度切层承接，而不是拉长
单个 move2。段尾空白由下一段 `auto_init()` 压缩，不靠超慢飞行或超长 delay 凑满整段。

短窗口（4-5s）的正式追加段尤其不能只把 `flying_ms` 写大：如果路径只有
70-120cm，底层最小速度/加速度会让真实运动提前结束。短窗口要用一个强
keyframe，并让多数无人机移动 240cm 左右或更长；通常写
`targets = far_assign(prev, geo, min_path_cm=220)`，目标几何要靠近场地边界/角点，
不要挤在中心小范围交换。

## 高度层
正式编舞段不能把一个 keyframe 写成全队同一高度。每个主体 keyframe 至少混合
3 个高度层（例如 100/160/220），整段 Z range 建议 ≥90cm。坏例子：
`geo = [(x1,y1,200), ..., (x7,y7,200)]`；这会被视为固定高度平面退化。

最后一个 move2 后面如果没有显式 delay，下一段开始前必须调用 `auto_init(drones)`，
它会按 `Drone.time` 和 helper 记录的未完成移动时间，把下一段推迟到动作完成之后。

## 60s 后再 LAND
前段可以被 `auto_init()` 压缩，但 LAND 前必须至少有一个正式编舞段真实结束在
60s 之后。如果 S01-S06 压缩后还没到 60s，系统会在 LAND 前追加 S07/S08 等
正式段继续编舞；不要靠某一段原地硬等来拖时间。

## LAND 降落段
LAND 不是正式编舞连续性段，不写 keyframe，不再 move2 凑动作。正确结构：
```python
auto_init(drones)
for d in drones:
    apply_light(d, "#ffffff", 3)
    d.land()
```
不要只给单架无人机降落；不要再生成展开/回卷/交换动作。

## 起飞
```python
drone.X = drone.x = x
drone.Y = drone.y = y
drone.takeoff(1, height_cm)
wait_until(drones, 4)
```

## 禁止
- d.VelXY / d.VelZ 裸调
- d.move2() 裸调（必须用 function.py 的 move2）
- inittime() 调用（时间游标由 takeoff/delay/move 链自然推进）
- import 新模块
