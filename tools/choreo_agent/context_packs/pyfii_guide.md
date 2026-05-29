# Pyfii 编舞 — DNTG 风格

## 核心 API
```python
move2(d, (x,y,z), t_ms)  # 反算速度+飞行+delay(t_ms)
best_assign(prev, geo)   # 找最优排列
apply_light(d, "#RRGGBB", ticks)
```

## 三个编舞模式（按段意图选用）

### A. 展开式（适合推进/展开段）
geo1 从 prev 小幅偏移，geo2 大幅跳开：
```python
geo1 = [(prev[i][0]+35*math.sin(i*2.5), prev[i][1]+35*math.cos(i*2.5), 150) for i in range(7)]
geo2 = [(100,120,180),(280,80,200),(460,140,180),(420,380,190),(200,420,170),(340,340,210),(160,260,190)]
```

### B. 角色映射（适合分组/换位段）
不同机走不同路径：
```python
roles = {0:'left',1:'core',2:'core',3:'solo',4:'core',5:'core',6:'right'}
for i, drone in enumerate(drones):
    role = roles.get(i,'core')
    if role == 'left':   tx,ty,tz = 100, 280, 200
    elif role == 'right': tx,ty,tz = 460, 280, 200
    elif role == 'solo':  tx,ty,tz = 280, 280, 240
    else:                 tx,ty,tz = geo_core[i][0], geo_core[i][1], geo_core[i][2]
    move2(drone, (clamp_xy(tx), clamp_xy(ty), clamp_z(tz)), 3000)
```

### C. 旋转式（适合高潮/旋转段）
用 sin/cos 生成旋转几何：
```python
for gi in range(3):
    angle = 2*math.pi*gi/3
    r = 180 + 60*math.sin(angle)
    geo = [(280+r*math.cos(2*math.pi*i/7+angle), 280+r*math.sin(2*math.pi*i/7+angle), 150+50*math.cos(angle)) for i in range(7)]
    targets = best_assign(prev, geo) if gi>0 else geo
    for i, drone in enumerate(drones):
        move2(drone, (clamp_xy(targets[i][0]), clamp_xy(targets[i][1]), clamp_z(targets[i][2])), 2500)
        apply_light(drone, '#ff8844', 3)
        drone.delay(2500+300)
    prev = [(targets[i][0], targets[i][1], targets[i][2]) for i in range(7)]
```

## 规则
- 不用 inittime（auto_init 自动处理）
- 不用同心圆
- 每段尾更新 prev
- 几何间距 >= 100cm
