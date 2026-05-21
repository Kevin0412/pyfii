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
    best_score, best = -1e9, None
    for perm in itertools.permutations(range(N)):
        tt = [targets[i] for i in perm]
        md = 1e9
        for ratio in [0.2, 0.4, 0.6, 0.8]:
            for i in range(N):
                for j in range(i+1, N):
                    ai = tuple(starts[i][k]*ratio + tt[i][k]*(1-ratio) for k in range(2))
                    aj = tuple(starts[j][k]*ratio + tt[j][k]*(1-ratio) for k in range(2))
                    d = math.hypot(ai[0]-aj[0], ai[1]-aj[1])
                    if d < md: md = d
        score = md*2000 - max(math.dist(starts[i],tt[i]) for i in range(N))*0.01
        if score > best_score: best_score = score; best = tt
    return best
```

权重 `md*2000` 强烈倾向最安全分配。`max_d*0.01` 几乎不影响。

## 灯光

```python
def light(d, color, ticks):
    for tick in range(ticks):
        bright = int(100 + 155*math.sin(tick*math.pi/ticks))
        r = int(color[1:3], 16)*bright//255
        g = int(color[3:5], 16)*bright//255
        b = int(color[5:7], 16)*bright//255
        d.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}")
        d.delay(100)
```

推荐 10-20 ticks (1-2s)。每段不同颜色。

## 排队错峰

```python
for i,d in enumerate(ds): d.delay(i*offset_ms)  # offset=100-600ms
```

排在 intime 之后、第一个 move2 之前。

## 示例完整段

见 `context_packs/examples/segment_with_best_assign.py`
