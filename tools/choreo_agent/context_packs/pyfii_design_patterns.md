# Pyfii 设计模式 (DNTG + Cannon 经验)

> 来源: `doc/human_choreography_distillation.md` + `doc/cannon_design_lessons.md`

## 高度层次

别只在固定高度飞。每个几何用不同高度，高低交替产生层次：

```
起飞110 → 环165→190→165 → 斜对称248→88→168
```

Z 范围 80-250，起伏节奏感。

## 相对移动

用 `drone.x/y/z` 做偏移，不写死绝对坐标：

```python
drone.move(drone.x - 160, drone.y, drone.z)        # 左移
drone.move(drone.x, drone.y + 80, drone.z - 40)     # 下移+降低
```

## 条件分支

不同机走不同路径：

```python
for i, drone in enumerate(drones):
    drone.inittime(10)
    if i < 4:
        drone.move2(drone.x + 80, drone.y, drone.z)
    else:
        drone.move2(drone.x - 80, drone.y, drone.z + 30)
```

## 变速

dntg 中 move2 用不同时间（1000/1500/1600/2000ms），不是统一值。Cannon 经验：用 best_assign 确保 perms 正确后，可因距离不同用不同速度。

## 速度计算器

```python
def flight_time_ms(distance_cm, speed_cms, acc_cms2):
    """给定距离、速度、加速度，返回飞行时间(ms)"""
    if distance_cm <= 0: return 0
    accel_dist = speed_cms * speed_cms / (2 * acc_cms2)
    if distance_cm >= 2 * accel_dist:
        t_s = 2 * speed_cms / acc_cms2 + (distance_cm - 2 * accel_dist) / speed_cms
    else:
        t_s = 2 * math.sqrt(distance_cm / acc_cms2)
    return int(math.ceil(t_s * 1000))
```

延迟必须 >= 飞行时间：`drone.delay(flight_time_ms(d, v, a) + margin)`

## 圆形可以好

dntg 利萨如段是圆形但配合高度变化不单调。圆形本身不坏，坏的是纯同心圆无变化。
