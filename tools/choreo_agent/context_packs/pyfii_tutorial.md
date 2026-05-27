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
