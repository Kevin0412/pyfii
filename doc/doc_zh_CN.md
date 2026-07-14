# PyFii 使用文档

PyFii 可以用 Python 编排 Fii 无人机动作、生成 `.fii` 工程、读取轨迹并预览或导出视频。网页工具的使用方法见 [GUI 使用引导](pyfii_gui_guide.md)。

## 1. 创建无人机

```python
import pyfii as pf

# F400，起飞位置为 (100, 100)
d1 = pf.Drone(100, 100)

# F600
d2 = pf.Drone6(100, 100)
```

也可以显式指定场地配置：

```python
d1 = pf.Drone(100, 100, config=pf.drone_config_6m)
d2 = pf.Drone(100, 100, config=pf.drone_config_4m)
```

`drone_config_6m` 和 `drone_config_4m` 分别对应 6 米、4 米场地。一个工程中的无人机型号必须一致。

## 2. 编排动作

下面是常用动作。`inittime()` 和 `takeoff()` 的时间单位是秒，`delay()` 的单位是毫秒；位置和距离的单位是厘米。

```python
d1.takeoff(1, 100)       # 1 秒时起飞到 100 cm
d1.inittime(4)           # 把时间光标移到第 4 秒
d1.VelXY(120, 240)       # 水平速度、加速度
d1.VelZ(120, 240)        # 竖直速度、加速度
d1.ARate(30)             # 角速度，°/s
d1.move2(300, 300, 150)  # 移动到绝对坐标
d1.move(20, 0, 0)        # 相对当前位置移动
d1.Yaw(90)               # 相对旋转
d1.Yaw2(180)             # 转到绝对朝向
d1.delay(500)            # 等待 500 ms
d1.land()
d1.end()                 # 完成动作与灯光合并，必须调用
```

起飞前可以修改 `d1.X`、`d1.Y`；`d1.x`、`d1.y`、`d1.z` 表示编排过程中记录的当前目标位置。

以下特殊动作会写入 Fii 工程，但当前模拟器不一定能完整还原其真实运动：

```python
d1.nod(direction, distance)
d1.SimpleHarmonic2(direction, amplitude)
d1.RoundInAir(startpos, centerpos, height, velocity)
```

模拟结果不能替代真机安全检查。不要通过修改配置范围绕过设备、场地或比赛规则的限制。

## 3. 编写灯光

F400 常用灯光方法：

```python
d1.TurnOnSingle(light_id, color)
d1.TurnOffSingle(light_id)
d1.TurnOnAll(color_or_colors)
d1.TurnOffAll()
d1.BlinkSingle(light_id, color)
d1.Breath(color)
d1.BlinkFastAll(colors)
d1.BlinkSlowAll(colors)
d1.HorseRace(colors)
```

颜色可以写成六位十六进制字符串或 RGB 元组：

```python
d1.TurnOnAll("#66ccff")
d1.TurnOnAll((102, 204, 255))
d1.TurnOnAll(["#ff0000", "#00ff00", "#0000ff"])
```

F600 的灯光接口不同，例如 `AllOn()`、`AllOff()`、`BodyOn()` 和 `MotorOn()`。完整写法见 [灯光编写](tutorial/light.md)。

## 4. 保存 Fii 工程

所有无人机调用 `end()` 后，再创建并保存工程：

```python
name = "output/demo"
project = pf.Fii(name, [d1], music="music.mp3")
project.save()
```

PyFii 1.6.0 会根据无人机型号和 `drone_config_4m` / `drone_config_6m` 自动写入机型与场地。旧的 `field=` 参数仍被接受，但会被忽略并产生兼容性 warning，新代码不要再传它。

## 5. 读取与预览

推荐使用 `from_fii()` 读取工程。它返回一个 `DroneTrack`，集中保存轨迹、时长、音乐、场地和机型：

```python
track = pf.from_fii(name, fps=200)
pf.show(track)
```

`ignore_acc=True` 可用于对照旧的无加速度视觉效果，但默认加速度模式才是当前检查和交付应使用的模式：

```python
visual_track = pf.from_fii(name, fps=60, ignore_acc=True)
pf.show(visual_track)
```

旧的五项返回值和多参数 `show()` 仍然兼容：

```python
data, t0, music, field, device = pf.read_fii(name, fps=200)
pf.show(data, t0, music, field=field, device=device)
```

轨迹中每个采样点的结构为：

```python
(time_ms, x, y, z, yaw_deg, led, (ax, ay, az))
```

其中位置单位为厘米，加速度单位为 `cm/s²`。

只运行安全距离检查、不显示窗口：

```python
pf.show(track, show=False)
```

warning 表示需要检查，但不会自动中止预览；解析失败、缺少 `.fii` 或动作组文件等异常会中止当前操作。

## 6. 二维、三维与视频

二维预览：

```python
pf.show(track, skin=1)
```

三维正交视图：

```python
pf.show(track, ThreeD=True, imshow=[120, -15], d=(1, 0))
```

三维透视视图：

```python
pf.show(track, ThreeD=True, imshow=[90, 0], d=(600, 450))
```

导出 MP4：

```python
pf.show(track, save="demo", FPS=25)
```

`FPS` 是输出视频帧率；降低它会减少需要绘制的帧数，但不会刻意改变动作时长。音乐存在且本机可以执行 FFmpeg 时，渲染器会把音乐封装进最终 MP4。

直接使用新的渲染类时，可以把同一个 `DroneTrack` 传给二维或三维渲染器：

```python
from pyfii import FiiRender2D, FiiRender3D

renderer = FiiRender2D(track, {"FPS": 25, "max_fps": 200})
renderer.save("demo_2d")

renderer3d = FiiRender3D(
    track,
    {
        "FPS": 25,
        "max_fps": 200,
        "imshow": [90, 0],
        "d": (600, 450),
    },
)
renderer3d.save("demo_3d")
```

`show(track, ...)` 是日常使用入口；直接实例化渲染类更适合 GUI、批处理或需要逐帧进度回调的封装。

实时预览快捷键：空格暂停，`q` 后退，`e` 前进，`Esc` 退出。三维预览暂停后可使用 `w/a/s/d` 调整视角。

## 7. 脚本模式与专题教程

- [安装](tutorial/install.md)
- [编队飞行](tutorial/group_flight.md)
- [脚本模式](tutorial/script_mode.md)
- [灯光编写](tutorial/light.md)
- [内部原理](tutorial/principle.md)

Web GUI 位于 `apps/pyfii-gui/`，提供工程上传、warning 展示、二维/三维交互预览和 MP4 导出。部署和开发方式见 [GUI 架构与部署](pyfii_gui.md)。
