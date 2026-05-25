# Best Assign — 离线匹配工具

> 用作 AI 编码阶段的工具，结果硬编码写入 `design.py`。不放运行时代码。

## 接口

```python
from tools.choreo_agent.core.best_assign import best_assign

perm, min_d = best_assign(starts, targets)
# starts:  [(x0,y0), ...]
# targets: [(x0,y0), ...]
# perm:    (3,0,5,1,6,2,4)  — drone i → target perm[i]
# min_d:   85.9              — 路径上任意两机最短距离(cm)
```

## 算法

全排列 7! = 5040，每条排列计算 21 对路径线段的最短距离（叉积+投影精确解，不采样）。取最小间距最大的排列。

< 50ms，AI编码阶段可直接调用。

## AI 硬编码示例

```python
perm, _ = best_assign(prev_xy, geo_xy)
# AI 将结果写成:
for i, drone in enumerate(drones):
    tx, ty, tz = geo_targets[perm[i]]
    drone.move2(tx, ty, tz)
```

## 测试

```
starts: 7机当前出口  →  targets: 7个安全目标点
perm=(...)  min_d=85.9cm  max_move=144cm
```
