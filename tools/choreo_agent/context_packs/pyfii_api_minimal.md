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
drone.intime(4)               # 开始时间秒，必须是整数
# ... moves and lights ...
drone.intime(68)
drone.land()
drone.end()
```

## Time

```python
drone.intime(24)   # 秒，整数。不可倒退。
drone.delay(100)   # 毫秒。delay(42) 是 42ms，不是 42s。
```

## Move

```python
drone.move2(x, y, z)
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
drone.VelXY(120, 240)   # (min_speed, max_speed) cm/s
drone.VelZ(120, 240)    # 纵向速度
```

max speed = 200 cm/s。acceleration 默认 ~200 cm/s²，范围 (50, 400)。

速度 200 + 加速度 400 都拉满还飞不完，才需要延长 delay。

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
