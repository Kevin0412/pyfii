# Pyfii Minimal API

## Import

```python
import pyfii as pf
```

## Create 7 F400 Drones

```python
N = 7
ds = [pf.Drone(0, 0, pf.drone_config_6m, f"192.168.51.{51+i}") for i in range(N)]
```

## Lifecycle (每架机必须按此顺序)

```python
d.X = d.x = 280    # 起始 X
d.Y = d.y = 280    # 起始 Y
d.takeoff(1, 110)  # (耗时秒, 目标高度cm)
d.intime(4)        # 开始时间秒，必须是整数
# ... moves and lights ...
d.intime(68)
d.land()
d.end()
```

## Time

```python
d.intime(24)    # 秒，整数。不可倒退。
d.delay(100)    # 毫秒。
```

`delay(42)` 是 42 毫秒，不是 42 秒。

## Move

```python
d.move2(x, y, z)
```

坐标必须是整数。`math.cos/sin` 返回浮点数，必须取整：

```python
x = int(round(x))
```

快捷函数：
```python
def cl(x): return max(10, min(550, int(round(x))))  # clamp XY
def cz(z): return max(80,  min(240, int(round(z))))  # clamp Z
```

## Speed

```python
d.VelXY(120, 240)   # (min_speed, max_speed) cm/s
d.VelZ(120, 240)    # 纵向速度
```

max speed = 200cm/s。acceleration 默认 ~200cm/s²，范围(50,400)。

## Light

```python
d.TurnOnAll("#ff0000")
d.TurnOffAll()
```

## Save

```python
pf.Fii(str(OUT_DIR), ds, music=str(MUSIC_PATH)).save(field=6)
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

## Constants (F400)

| Param | Value |
|-------|-------|
| XY range | [0, 560] cm |
| Z range | [80, 250] cm |
| minD warning | < 51cm |
| max speed | 200 cm/s |
| acc range | 50-400 cm/s² |
