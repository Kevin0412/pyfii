# Pyfii 编舞 API

## 核心 API（from function import *）
```python
move2(d, (x,y,z), t_ms, T=100)
# 反算速度 → VelXY(v,2v)+VelZ(v,2v) → d.move2(x,y,z)。
# 不推进时间游标；但记录预计飞行结束时间，供 auto_init 防止下一段提前开始。

move_group(drones, targets, flying_ms, color="#ffffff", ticks=4)
# 同步 keyframe 兜底原语。它会隐藏每架机的灯光/等待细节，正式段不要把它
# 当作主编舞结构；主要用于 smoke、极简单同步段或修复时临时落地。

move_group_staggered(drones, targets, flying_ms, color="#ffffff", ticks=4, group_mod=3, stagger_ms=120)
# 卡农/分组错峰兜底原语。正式段更推荐展开 per-drone loop，自行写
# `if i % group_mod: drone.delay(...)`，保留每架机灯光和等待细节。

pulse_group(drones, color="#ffffff", ticks=3)
# 全队短灯光脉冲；不能用它凑长时间。

custom_points(points, n=None)
# 手写目标点表的标准化和安全检查。正式编舞主路径：
# 先写有叙事意图的 n 个 (x,y,z)，再 best_assign/far_assign。

apply_light(d, "#RRGGBB", ticks)
# ticks次TurnOnAll，每次delay 100ms。推进 cursor: ticks*100ms。

d.land()
# 降落段使用。LAND 段先 auto_init(drones)，可短灯光提示后对每架机 d.land()。

best_assign(prev, geo)
# 遍历全排列找最小路径间距最大的分配。返回重排后的 targets 列表；不要拆 perm/min_d。

far_assign(prev, geo, min_path_cm=90)
# 安全但鼓励远距离交换的分配。S04/S05、高潮、回卷、分组交换、或验证反馈
# “路径太短/小范围抖动”时使用；不要继续用相似几何 + best_assign 生成小挪动。

active_min_path_cm(flying_ms)
# 按 keyframe 名义时长估算最低路径长度。3s 以上 keyframe 如果路径太短，真实
# 飞行会提前完成，后半段只是在 delay，容易被低活动打回。长 keyframe 写：
# `targets = far_assign(prev, geo, min_path_cm=active_min_path_cm(3400))`。

clamp_xy(v)  # [0, 560]
clamp_z(v)   # [80, 250]
```

## 时序模型（每次移动）
正式段默认展开 per-drone loop，保留每架机的动作、灯光和等待细节：
```python
targets = best_assign(prev, geo)
flying_ms = 3000
ticks = 4
for i, drone in enumerate(drones):
    move2(drone, targets[i], flying_ms)
    apply_light(drone, "#44aaff", ticks)
    drone.delay(max(0, flying_ms - ticks * 100 + 100))
prev = [(t[0], t[1], t[2]) for t in targets]

targets = far_assign(prev, geo2, min_path_cm=140)
flying_ms = 3000
ticks = 4
for i, drone in enumerate(drones):
    stagger = (i % 3) * 80
    if stagger:
        drone.delay(stagger)
    move2(drone, targets[i], flying_ms)
    apply_light(drone, "#ffaa44", ticks)
    drone.delay(max(0, flying_ms - ticks * 100 + 100))
prev = [(t[0], t[1], t[2]) for t in targets]
```

几何主路径是手写目标点表：
```python
geo = custom_points([
    (45, 65, 100), (185, 45, 170), (340, 75, 230),
    (505, 55, 130), (75, 260, 210), (280, 230, 150),
    (505, 275, 240), (150, 500, 120), (405, 485, 190),
], n=len(drones))
targets = best_assign(prev, geo)
flying_ms = 3000
ticks = 4
for i, drone in enumerate(drones):
    move2(drone, targets[i], flying_ms)
    apply_light(drone, "#88ccff", ticks)
    drone.delay(max(0, flying_ms - ticks * 100 + 100))
prev = [(t[0], t[1], t[2]) for t in targets]

geo = custom_points([
    (80, 500, 230), (120, 300, 150), (70, 110, 100),
    (250, 70, 210), (330, 240, 120), (500, 90, 180),
    (530, 330, 240), (390, 500, 140), (220, 430, 200),
], n=len(drones))
targets = far_assign(prev, geo, min_path_cm=active_min_path_cm(3000))
flying_ms = 3000
ticks = 4
for i, drone in enumerate(drones):
    if i % 3:
        drone.delay((i % 3) * 80)
    move2(drone, targets[i], flying_ms)
    apply_light(drone, "#ffcc44", ticks)
    drone.delay(max(0, flying_ms - ticks * 100 + 100))
prev = [(t[0], t[1], t[2]) for t in targets]
```

`geo_wide_v/geo_arrow/geo_box/geo_diagonal/geo_wave/geo_grid` 这类模板已从 agent
导出面下线。S02-S05 不允许调用模板函数；模板参数变体不是编舞。assign 是安全
路径分配层，坐标表才是构图层。

`move_group/move_group_staggered` 是比 assign 更低级的执行模板：它能快速保证时间链，
但会让段落看起来像“坐标表堆叠”。S01-S06 纯 helper 执行会被 composition gate
打回。正式段至少一个主体 keyframe 应展开：
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
安全距离主要看 XY 平面；不要把同一 XY 上不同 Z 的多架无人机当成安全分离。

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

## 设计卡
正式段代码开头必须包含 5 行设计卡注释，用于把当前段绑定到全局章法：
```python
# role: 当前段在作品里的功能
# motifs: 使用/变奏的母题
# beat: 节奏和启动方式
# formation: 队形/空间结构
# lighting: 灯光弧线
```
如果设计卡写“卡农/错峰/分组”，代码必须在 per-drone loop 内明确按 i/group 分批
delay；如果写“高潮/爆发”，实际动作幅度和灯光变化必须跟得上。

## 9机旧版成功样例蒸馏
`codex_9drone_flash_full_20260605_1` 的观感优于后续 V2，关键不在坐标本身，而在结构：

- 0 次 `geo_*`，0 次 `move_group`，正式段全部展开 per-drone loop。
- S02/S03/S05 每段 3 个 keyframe；S04 可用 5 个短 keyframe 形成抒情展开；S06 用“中继点 + 终点”两段式收尾。
- 每个 keyframe 都有独立颜色或 tick 变化，S04/S05 尤其不能整段只用 1-2 种颜色。
- `best_assign/far_assign` 只负责安全路径分配；坐标表负责构图；`move2/apply_light/delay` 链负责节奏和质感。
- 不要复制旧坐标，但要复制这种章法：手写非同构几何、多色灯光、明确 per-drone 执行细节。

## 禁止
- d.VelXY / d.VelZ 裸调
- d.move2() 裸调（必须用 function.py 的 move2）
- inittime() 调用（时间游标由 takeoff/delay/move 链自然推进）
- import 新模块
