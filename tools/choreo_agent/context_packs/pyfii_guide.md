# Pyfii 编舞 — 科学设计

## 核心思路：选模式，不写坐标
用算法保证几何安全，agent 只选模式、速度和灯光。

```python
geo = safe_geo('expand')        # 展开/旋转/呼吸/收缩
targets = best_assign(prev, geo)
for i, drone in enumerate(drones):
    move2(drone, (clamp_xy(targets[i][0]), clamp_xy(targets[i][1]), clamp_z(targets[i][2])), 3000)
    apply_light(drone, '#ff6644', 4)
    drone.delay(3000 + 400)
prev = [(targets[i][0], targets[i][1], targets[i][2]) for i in range(7)]
```

## 四种模式
| 模式 | 适用于 | 效果 |
|------|--------|------|
| `expand` | 推进/展开段 | 泊松圆盘采样，非对称散布全场 |
| `rotate` | 高潮/旋转段 | 中心1机+外围6机旋转环 |
| `breathe` | 过渡段 | 同心环呼吸(120-220cm半径) |
| `contract` | 收束/降落段 | 收缩到80-130cm半径 |

## 规则
- 不用 inittime（auto_init 自动处理）
- 每段尾更新 prev
