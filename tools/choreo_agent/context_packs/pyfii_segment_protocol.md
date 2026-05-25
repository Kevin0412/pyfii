# Segment Protocol

## 每次只生成当前段

输入：
- `segment_id`
- `start_time` / `end_time`
- music cue (能量、情绪、节奏密度)
- `start_state` (prev positions)
- `design_memory` 摘要
- `human_feedback` (如有)
- 当前段历史尝试

输出：
- 当前段代码（含 marker）
- 设计说明
- 是否改变出口状态
- 需要验证的点

禁止：
- 修改前段
- 添加后段
- 覆盖整个 design.py
- 生成不存在的 Pyfii API

## 几何定义格式

```python
geo = [
    [(x0,y0,z0), (x1,y1,z1), ..., (x6,y6,z6)],  # 几何1: 7机坐标
    [(x0,y0,z0), ..., (x6,y6,z6)],               # 几何2
    ...                                           # 几何3-4
]
```

每个几何内部各点间距 > 51cm（F400 安全阈值）。

## 排列搜索

必须使用 `best_assign()`：

```python
def best_assign(starts, targets):
    """全排列搜索路径最短距离最大的分配。用作离线工具，结果硬编码。"""
    N = len(starts)
    best_md, best_perm = -1, None
    for perm in itertools.permutations(range(N)):
        tt = [targets[i] for i in perm]
        md = 1e9
        for i in range(N):
            for j in range(i+1, N):
                d = _segment_distance(starts[i], targets[perm[i]], starts[j], targets[perm[j]])
                if d < md: md = d
        if md > best_md:
            best_md = md
            best_perm = perm
    return best_perm, best_md

线段距离用计算几何精确解（叉积+投影），不采样。
权重 `md*2000` 强烈倾向最安全分配。`max_d*0.01` 几乎不影响。

## 灯光

```python
def apply_light(drone, color, ticks):
    """正弦渐变灯光，ticks=步数(每步100ms)"""
    for tick in range(ticks):
        bright = int(100 + 155 * math.sin(tick * math.pi / ticks))
        r = int(color[1:3], 16) * bright // 255
        g = int(color[3:5], 16) * bright // 255
        b = int(color[5:7], 16) * bright // 255
        drone.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}")
        drone.delay(100)
```

`apply_light()` 每 tick 会 `delay(100)`，因此它本质上也是等待。正式编舞段默认只用 3-6 ticks 的短灯光脉冲；除非同一时间还有其它分组在飞行，否则不要在全体 move2 后使用 `ticks > 8`。

每段可使用不同颜色。每个 move2 后可以接短灯光脉冲，但不能用纯灯光/纯 delay 填满 1 秒以上；如需长呼吸，必须让另一组错峰运动或做轻微 Z/XY 变化承接。

## 排队错峰

```python
for i,d in enumerate(ds): d.delay(i*offset_ms)  # offset=100-600ms
```

排在 inittime 之后、第一个 move2 之前。

注意：错峰只改变起步时间，不自动保证连贯性。正式段里每个 1 秒窗口都应至少有一组无人机在 `move2` 或轻微 Z/XY 变化中，不能出现全体一起等灯光/等 delay 的空窗。


## dntg 技巧：相对移动 + 条件分支

```python
# 相对移动：从当前位置偏移
drone.move(drone.x + dx, drone.y + dy, drone.z + dz)

# 条件分支：不同机走不同路径
for i, drone in enumerate(drones):
    drone.inittime(10)
    if i < 3:
        drone.move2(280 + 80*i, 280, 180)
    elif i == 3:
        drone.move2(280, 280, 200)
    else:
        drone.move2(280, 280 + 80*(i-4), 180)
```

## 示例完整段

见 `context_packs/examples/segment_with_best_assign.py`
