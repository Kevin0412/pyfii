# 脚本模式

> 2026-07-14 按 PyFii 1.6.0 复核。脚本模式指 `Fii.save()` 在官方 Blockly XML 之外同时生成可编辑的 `pyfiiCode.py` 和工程重建脚本；它不是另一套轨迹格式。

## 生成脚本工程

下面生成四架 F400、4 米毯的最小工程：

```python
import pyfii as pf

starts = [(60, 60), (60, 300), (300, 60), (300, 300)]
targets = [(120, 120), (120, 240), (240, 120), (240, 240)]
drones = []

for index, ((x, y), (target_x, target_y)) in enumerate(zip(starts, targets), start=1):
    drone = pf.Drone(x, y, config=pf.drone_config_4m, ip=f"192.168.0.{index}")
    drone.takeoff(1, 100)
    drone.inittime(4)
    drone.VelXY(100, 200)
    drone.move2(target_x, target_y, 100)
    drone.inittime(8)
    drone.land()
    drone.end()
    drones.append(drone)

project = "output/script_mode_demo"
pf.Fii(project, drones).save()
```

`Fii.save()` 根据 `Drone` 配置自动写入 F400 和 4 米场地，不再需要传 `field=`。

## 生成内容

工程目录中与脚本模式直接相关的是：

```text
output/script_mode_demo/
├── script_mode_demo.fii
├── script_mode_demo.py
├── readme.md
└── 动作组/
    ├── checksums.xml
    ├── 动作组1/
    │   ├── pyfiiCode.py
    │   └── webCodeAll.xml
    └── ...
```

- `webCodeAll.xml` 是厂商工程使用的 Blockly XML，也是 PyFii 读回动作的主输入。
- `pyfiiCode.py` 是单架无人机动作的线性 Python 表示，便于查看和修改动作。
- 根目录同名 `.py` 会依次执行各动作组的 `pyfiiCode.py`，重新生成工程并调用兼容渲染入口。
- `readme.md` 是随工程生成的动作速查说明。

## 修改与重新生成

1. 先备份工程，编辑对应动作组的 `pyfiiCode.py`。
2. 保持时间单调，确认 `takeoff()`、`inittime()`、`delay()`、移动、灯光和 `land()` 的顺序。
3. 在工程目录运行同名脚本，使它能按相对路径找到 `动作组/`：

```bash
cd output/script_mode_demo
python script_mode_demo.py
```

4. 使用当前推荐入口重新读回并验证：

```python
import pyfii as pf

track = pf.from_fii("output/script_mode_demo", fps=200)
pf.show(track, show=False)
pf.show(track)
```

warning 表示工程可以继续读取但存在需要检查的问题，例如动作未完成、距离过近、缺省速度或未拼接积木；解析 error 则必须先修复。脚本成功运行不等于安全验收通过。

## 限制

- `pyfiiCode.py` 是 PyFii 生成格式，不保证能执行任意手写 Python 模块、import 或复杂控制流。
- 根目录重建脚本仍使用部分兼容 API；新应用和 GUI 应直接使用 `DroneTrack` 与 renderer，不要解析这个脚本来获取轨迹。
- `addlights=True` 属于旧的灯光覆写流程，涉及重写动作组并执行生成脚本。普通编舞优先在原始 Python 源中修改灯光后重新保存。
- 修改脚本后仍需默认加速度读回、结构化 warning 检查和 2D/3D 预览；必要时再在真机环境验证。
