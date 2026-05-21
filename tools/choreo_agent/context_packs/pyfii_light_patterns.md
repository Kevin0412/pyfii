# Pyfii Light Patterns

## 基本开关

```python
drone.TurnOnAll("#ff0000")
drone.TurnOffAll()
```

## 模式1: 正弦渐变 (推荐默认)

```python
def light_sine(drone, color, ticks, pause_ms=0):
    """
    ticks: 渐变步数 (每步 100ms)
    pause_ms: 渐变结束后保持时间
    """
    for tick in range(ticks):
        bright = int(100 + 155 * math.sin(tick * math.pi / ticks))
        r = int(color[1:3], 16) * bright // 255
        g = int(color[3:5], 16) * bright // 255
        b = int(color[5:7], 16) * bright // 255
        drone.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}")
        drone.delay(100)
    if pause_ms > 0:
        drone.delay(pause_ms)
```

## 模式2: 交替闪烁 (节奏感)

```python
def light_blink(drone, color, times, on_ms=300, off_ms=200):
    for _ in range(times):
        drone.TurnOnAll(color)
        drone.delay(on_ms)
        drone.TurnOffAll()
        drone.delay(off_ms)
```

## 模式3: 彩虹色轮 (全场炫彩)

```python
def light_rainbow(drone, ticks):
    for tick in range(ticks):
        hue = tick / ticks
        r = int((math.sin(hue * 2*math.pi) * 0.5 + 0.5) * 255)
        g = int((math.sin(hue * 2*math.pi + 2.09) * 0.5 + 0.5) * 255)
        b = int((math.sin(hue * 2*math.pi + 4.19) * 0.5 + 0.5) * 255)
        drone.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}")
        drone.delay(100)
```

## 模式4: 恒定 + 延迟

```python
drone.TurnOnAll("#ff0000")
drone.delay(2000)    # 保持2秒
drone.TurnOffAll()
```

## 设计原则

- **light 和 delay 是飞行时间预算的一部分**。light(10ticks) + delay(500ms) = 1.5s 悬停。确保这段总时间 > 飞行时间。
- **速度200+加速度400拉满后还不够时间** → 必须增大 delay，不能缩短 light。
- **错峰灯光**：不同机用不同 ticks 或 delay，产生层次感。
