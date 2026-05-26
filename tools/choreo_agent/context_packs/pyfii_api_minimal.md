# Pyfii Minimal API

## Import

```python
import pyfii as pf
```

## Create 7 F400 Drones

```python
N = 7
drones = [pf.Drone(0, 0, pf.drone_config_6m, f"192.168.51.{51+i}") for i in range(N)]
```

## Lifecycle (每架机必须按此顺序)

```python
drone.X = drone.x = 280       # 起始 X
drone.Y = drone.y = 280       # 起始 Y
drone.takeoff(1, 110)         # (耗时秒, 目标高度cm)
drone.inittime(4)               # 开始时间秒，必须是整数
# ... moves and lights ...
drone.inittime(68)
drone.land()
drone.end()
```

## Time

```python
drone.inittime(24)  # 秒，整数。把本机命令游标切到绝对时间，不可倒退。
drone.delay(100)    # 毫秒。推进本机命令游标；delay(42) 是 42ms，不是 42s。
```

`inittime()` 不是每个移动前都要调用。段内常用结构是：

```python
drone.inittime(segment_start)
drone.VelXY(v, a)
drone.VelZ(v, a)
drone.move2(x1, y1, z1)  # 在当前游标发起移动；move2 本身不推进游标
drone.delay(t_ms)        # 给这次移动留执行时间，期间无人机正在飞
drone.move2(x2, y2, z2)  # 下一次移动在新的游标时间开始
```

## Move

`drone.x`, `drone.y`, `drone.z` 记录当前目标点，可用于相对移动：

```python
drone.move2(x, y, z)       # 绝对坐标
drone.move(drone.x+dx, drone.y+dy, drone.z+dz)  # 相对移动
```

坐标必须是整数。`math.cos/sin` 返回浮点数，必须取整：
```python
x = int(round(x))
```

## Coordinate Clamp

Pyfii F400 要求坐标在合法范围内：

```python
def clamp_xy(v):
    """将 XY 坐标限制在场地 [0, 560] 范围内"""
    return max(0, min(560, int(round(v))))

def clamp_z(v):
    """将 Z 坐标限制在安全高度 [80, 250] 范围内"""
    return max(80, min(250, int(round(v))))
```

## Speed

```python
drone.VelXY(120, 240)   # (speed cm/s, acc cm/s²)
drone.VelZ(120, 240)    # 纵向速度
```

speed range = (20, 200) cm/s。acceleration 默认 ~200 cm/s²，范围 (50, 400)。
示例里的 `120, 240` 只是 API 格式示范，不表示 acceleration 必须等于 2 * speed；acceleration 可以根据柔和/利落/急促等动作质感独立选择。

`VelXY` 和 `VelZ` 最好成对设置，并使用同一组 speed/acceleration。这不是 PyFii Python API 本身的物理限制，而是为了匹配原始 XML/回放里的速度字段语义，避免水平与垂直运动被不同规则解释。每次 keyframe 重新选择速度时，同时写：

```python
drone.VelXY(speed, accel)
drone.VelZ(speed, accel)
```

速度 200 + 加速度 400 都飞不完，才需要延长这次移动后的执行预算；不要在段尾补无运动覆盖的长 delay。

## Light

基本开关：
```python
drone.TurnOnAll("#ff0000")
drone.TurnOffAll()
```

灯光模式见 `pyfii_light_patterns.md`（正弦渐变、呼吸、闪烁、彩虹等）。

## Save

```python
pf.Fii(str(OUT_DIR), drones, music=str(MUSIC_PATH)).save(field=6)
```

`OUT_DIR` 是目录路径，不是文件名。

## Read Back & Validate

```python
data, t0, music, field, dev = pf.read_fii(str(OUT_DIR), fps=60, ignore_acc=False)
# data[i][frame] = (t_ms, x, y, z, angle, led, acc)

pf.show(data, t0, [str(MUSIC_PATH)], field=field, device=dev, max_fps=60, show=False)
# show=False: 只检查距离警告，不渲染窗口
```

## Render Video

```python
pf.show(data, t0, [str(MUSIC_PATH)], field=field, device=dev,
        max_fps=60, save=str(OUT_DIR/'2d'), FPS=25)
# 3D 评委视角:
pf.show(data, t0, [str(MUSIC_PATH)], field=field, device=dev,
        max_fps=60, save=str(OUT_DIR/'3d'), FPS=25,
        ThreeD=True, imshow=[90,0], d=(600,450))
```

## F400 Constants

| Param | Value |
|-------|-------|
| XY range | [0, 560] cm |
| Z range | [80, 250] cm |
| minD warning | < 51cm |
| max speed | 200 cm/s |
| acc range | 50-400 cm/s² |

## function.py
设计代码中通过 `from function import *` 导入辅助函数。可用函数见 coding_rules。
