# Best Assign — 离线匹配工具

> **定位**: AI 编码阶段一次性调用，结果直接写入 `design.py`。
> **不要**: 作为运行时函数放在 `design.py` 中。`design.py` 只包含硬编码的坐标分配。
> **原因**: 运行时排列搜索耗时，反复调用无意义。AI 有充分 token 预算做离线搜索。

## 匹配策略（6种）

AI 生成段代码时，调用本工具获取最优分配，然后**把结果硬编码写入 `design.py`**。

| 策略 | 评分函数 | 视觉效果 | 适用场景 |
|------|----------|----------|----------|
| `first_match` | 第一个不碰撞的排列 | 一般 | 快速原型 |
| `min_distance` | 最大化路径最小间距 | 安全 | 保守设计 |
| `max_min_distance` | 同上但更激进 | 惊险安全 | 大动作展示 |
| `min_max_move` | 最小化最远移动距离 | 动作快 | 密集几何 |
| `max_total_move` | 最大化总移动距离 | 视觉丰富 | 展开段 |
| `max_max_move` | 最大化最远单机移动 | 冲击力 | 爆发展开 |

## 剪枝规则

```python
def prune(perm):
    """如果 ad1→bd2 且 ad2→bd1 同时发生，必然交叉 → 剪掉"""
    for i in range(N):
        for j in range(i+1, N):
            if perm[i] == j and perm[j] == i:
                return True  # 对向交换，99%交叉
    return False
```

对 9 机：`9! = 362880`。剪掉对向交换后约 150000，可接受。

## 离线工具接口

```python
from tools.choreo_agent.core.best_assign import assign, Strategy

result = assign(
    starts=[(x0,y0), ..., (x6,y6)],
    targets=[(x0,y0), ..., (x6,y6)],
    strategy=Strategy.MIN_DISTANCE,
    prune_enabled=True,
)
# result.permutation: (2, 5, 0, 3, 6, 1, 4)  # drone i → target perm[i]
# result.min_distance_cm: 57.0
# result.max_move_cm: 320.0
```

AI 拿到 `permutation` 后，直接硬编码：

```python
# AI 硬编码分配
assert tuple(perm) == (2, 5, 0, 3, 6, 1, 4)
geo_targets = [(100,200,180), (300,150,175), ...]
for i, drone in enumerate(drones):
    tx, ty, tz = geo_targets[perm[i]]
    drone.move2(tx, ty, tz)
```
