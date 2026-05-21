# Best Assign — 离线匹配工具

> **定位**: AI 编码阶段一次性调用，结果直接写入 `design.py`。
> **不要**: 作为运行时函数放在 `design.py` 中。
> **原因**: AI 有充分 token 预算做离线搜索，硬编码结果更可审计。

## 匹配策略（6种）

AI 生成段代码时调用本工具，拿到 permutation 后硬编码写入。

| 策略 | 评分函数 | 视觉效果 | 适用场景 |
|------|----------|----------|----------|
| `first_match` | 第一个不碰撞的排列 | 一般 | 快速原型 |
| `min_distance` | 最大化路径最小间距 | 最安全 | 保守设计 |
| `max_min_distance` | 同上但更激进 | 惊险安全 | 大动作展示 |
| `min_max_move` | 最小化最远移动距离 | 动作快 | 密集几何 |
| `max_total_move` | 最大化总移动距离 | 视觉丰富 | 展开段 |
| `max_max_move` | 最大化最远单机移动 | 冲击力 | 爆发展开 |

## 剪枝规则

对 7 机 (5040 排列) **不需要剪枝**——全排列 < 50ms。
对 9 机 (362880 排列) 建议启用：

```python
def prune(perm, starts, threshold=51):
    """只剪起始距离<51cm的对向交换（已处碰撞范围）"""
    for i in range(N):
        for j in range(i+1, N):
            if perm[i] == j and perm[j] == i:
                if math.dist(starts[i], starts[j]) < threshold:
                    return True
    return False
```

阈值 = F400 碰撞阈值。100 次随机测试零误杀最优解。

## 离线工具接口

```python
from tools.choreo_agent.core.best_assign import assign, Strategy

result = assign(
    starts=[(x0,y0), ..., (x6,y6)],
    targets=[(x0,y0), ..., (x6,y6)],
    strategy=Strategy.MIN_DISTANCE,
    prune_enabled=False,  # 7机不需要
)
# result.permutation: (2, 5, 0, 3, 6, 1, 4)
# result.min_distance_cm: 57.0
# result.max_move_cm: 320.0
```

AI 拿到 `permutation` 后硬编码：

```python
geo_targets = [(100,200,180), (300,150,175), ...]
# AI 硬编码分配
for i, drone in enumerate(drones):
    tx, ty, tz = geo_targets[perm[i]]
    drone.move2(tx, ty, tz)
```

## 测试结果

```
=== best_assign 测试 ===
start: 7 drones scattered
target: 7-point ring r=140
  first_match:          min_d=57.3cm  max_move=394cm  perm=(0,4,1,2,6,3,5)
  min_distance(安全):    min_d=123.6cm max_move=144cm  perm=(4,5,6,0,1,2,3)
  min_max_move(最快):    min_d=123.6cm max_move=144cm  perm=(4,5,6,0,1,2,3)
  max_total_move(丰富):  min_d=55.3cm  max_move=359cm  perm=(6,0,1,2,3,5,4)
```
