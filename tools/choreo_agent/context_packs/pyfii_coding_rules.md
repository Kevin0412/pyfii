# Pyfii Coding Rules

## 硬规则

1. **只修改当前未锁定 segment。**
2. **不允许修改 locked segment。**
3. **不允许提前设计下一段。**
4. **不要猜不存在的 Pyfii API。** 优先模仿已有代码。
5. **`inittime()` 是秒级整数。**
6. **`delay()` 是毫秒。**
7. **所有坐标必须 `int(round())`。** `math.cos/sin` 返回值是浮点数。
8. **每段结束必须更新 `prev = targets`。**
9. **所有机始终有动作**，不悬停。长时间小范围运动效果等同悬停。
10. **段间留 >0.5s 余量**避免 intime 冲突。

## 段内结构

```python
# === AGENT_SEGMENT_START S03 locked=false ===
# intent: ...
# start_time: 24.0
# end_time: 34.0

geo = [...]              # 几何定义

for i,d in enumerate(ds):
    d.inittime(start)
    d.VelXY(v, v*2)
    d.VelZ(v, v*2)

for gi in range(len(geo)):
    targets = best_assign(prev, geo[gi])
    for i,d in enumerate(ds):
        d.move2(...)
        light(d, color, ticks)
        d.delay(delay_ms)
    prev = targets

# === AGENT_SEGMENT_END S03 ===
```

## 速度设置

- 优先 VelXY(200, 400)，VelZ(200, 400)
- 如果动作未完成(action warning)，先检查是否已到200上限
- 200+400都拉满还飞不完，才需要延长 light ticks 或 delay

## 飞行时间公式

```python
def flight_time(d, v, a=200):
    """d: cm, v: cm/s, a: cm/s²"""
    if d <= 0: return 0
    accel_dist = v*v / (2*a)
    if d >= 2 * accel_dist:  # 有匀速阶段
        return 2*v/a + (d - 2*accel_dist)/v
    else:                     # 仅加速-减速
        return 2 * math.sqrt(d/a)
```

确保 `light_ticks * 100ms + delay_ms > flight_time(d, v) * 1000`

## 错误处理

| 错误 | 原因 | 修复 |
|------|------|------|
| `Out of range` | XY超出[0,560]或Z超出[80,250] | clamp坐标 |
| `Time arrangement error` | intime倒退或段间冲突 | 推后intime |
| `action isn't completed` | 飞行时间不够 | 提速或加delay |
| `distance between` | 两机<51cm | 增间距或提搜索权重 |
| `ValueError: invalid literal` | 坐标含浮点数 | int(round(x)) |
