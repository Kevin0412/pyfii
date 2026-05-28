# Pyfii 编舞 — DNTG 风格


## 设计原则（从人类作品蒸馏）

好的编舞不是一堆 keyframe，而是有时间结构的：

### 1. 能量曲线
速度不是恒定的——应该有 **爆发 → 衰减 → 再加速** 的节奏：
- 段初：高速冲击（100-140cm/s），制造视觉冲击
- 段中：减速过渡（40-60cm/s），准备下一波
- 段末：再次加速（70-90cm/s），进入下一段

实现：不同 keyframe 用不同的 move2 时间——短的快，长的慢。

### 2. 空间密度呼吸
间距要有变化，不能永远是同心圆等距：
- 密集时刻：平均间距 200-250cm（聚拢，张力）
- 稀疏时刻：平均间距 280-350cm（扩散，释放）
- 疏→密→疏 循环，形成"呼吸"感

实现：geo 的半径和中心点随 keyframe 变化，不是固定 pattern。

### 3. Z轴渐进分层
高度不要全平：
- 开始时同高度（起飞后 100-120cm）
- 中段逐步拉开跨度（20→50→90cm）
- 不同机在不同高度层，形成立体感

实现：geo 的 z 坐标递增 15-25cm/keyframe，不同机不同 z 值。

### 4. 速度峰值分布
整个作品应该有速度的高峰和低谷：
- 不要在每段都均匀分布速度
- 把高能动作集中在前 1/3 和后 1/3
- 中间 1/3 可以相对平缓（为高潮蓄力）

## 只有一个核心 API

```python
move2(d, (x, y, z), t_ms)
```

- `d`: 无人机对象
- `(x, y, z)`: 目标坐标 (cm)，xy∈[0,560]，z∈[80,250]
- `t_ms`: 总时间 (ms)，内部自动反算速度 + VelXY + move2 + delay

## 起飞

```python
d.X = d.x = clamp_xy(x0)
d.Y = d.y = clamp_xy(y0)
d.takeoff(1, z0)              # 1秒后起飞到z0(cm)
```

## 相对移动

```python
move2(d, (d.x+dx, d.y+dy, d.z+dz), t_ms)
```

## 排列

```python
targets = best_assign(prev, geo)
```

## 灯光

```python
apply_light(d, "#RRGGBB", ticks)
```

## 人类设计模式（从 dntg20220730_v3 蒸馏）

### 模式 A：数学轨迹（推荐）
不要逐点写坐标——用数学函数生成轨迹：
```python
import cmath, math
E = math.e

# 旋转几何
center = complex(280, 280)
R = 150
for gi in range(4):
    theta = 2*math.pi*gi/4 + math.pi/6
    rotateV = E**(theta*1j)
    geo = [(center.real + R*rotateV.real, center.imag + R*rotateV.imag, 150+30*gi) 
           for _ in range(7)]
    # ... best_assign + move2 ...
```

### 模式 B：角色映射与分组差异
同一段内不同机走不同路径——避免"全体同步"退化：
```python
roles = {0: 'left_wing', 1: 'core', 2: 'core', 3: 'solo', 4: 'core', 5: 'core', 6: 'right_wing'}

for i, drone in enumerate(drones):
    role = roles.get(i, 'core')
    if role == 'left_wing':
        tx, ty, tz = clamp_xy(280-150), clamp_xy(280), clamp_z(200)
    elif role == 'right_wing':
        tx, ty, tz = clamp_xy(280+150), clamp_xy(280), clamp_z(200)
    elif role == 'solo':
        tx, ty, tz = clamp_xy(280), clamp_xy(280), clamp_z(250)
    else:  # core group
        tx, ty, tz = geo_core[i][0], geo_core[i][1], geo_core[i][2]
    move2(drone, (tx, ty, tz), 3000)
    apply_light(drone, '#ff6644', 4)
    drone.delay(3000 + 400)
prev = [(drone.x, drone.y, drone.z) for drone in drones]
```

### 模式 C：连续轨迹（高密度 + 数学函数）
```python
n_steps = 12  # 12个小步 ≈ 连续运动
for step in range(n_steps):
    phase = 2*math.pi*step/n_steps
    r = 180 + 60*math.sin(phase)
    geo = [(280+r*math.cos(2*math.pi*i/7+phase), 280+r*math.sin(2*math.pi*i/7+phase), 150+50*math.cos(phase)) 
           for i in range(7)]
    targets = best_assign(prev, geo) if step > 0 else geo
    for i, drone in enumerate(drones):
        move2(drone, (clamp_xy(targets[i][0]), clamp_xy(targets[i][1]), clamp_z(targets[i][2])), 1200)
        apply_light(drone, '#44aadd', 2)
        drone.delay(1200 + 200)
    prev = [(targets[i][0], targets[i][1], targets[i][2]) for i in range(7)]
```

### 编码原则
1. 数学函数表达轨迹，不硬编码坐标
2. 每段可重新分配角色——同一机在不同段有不同职责
3. 同段内分组差异——避免"全体同步 move2"退化
4. 灯光用三角函数驱动连续变化，不用静态颜色序列

```python
geo = [(x1,y1,z1), ..., (x7,y7,z7)]
geo2 = [(x1,y1,z1), ..., (x7,y7,z7)]

t0 = auto_init(drones, 4)   # S01 起始秒
# 后续段：auto_init(drones) 自动接续
# 每段末尾检查：if should_land(drones): break  # 超60s自动降落
for i, drone in enumerate(drones):
    drone.delay(i * 80)

for gi in range(2):
    geos = [geo, geo2]
    targets = best_assign(prev, geos[gi]) if gi > 0 else geos[gi]
    for i, drone in enumerate(drones):
        tx, ty, tz = targets[i]
        move2(drone, (tx, ty, tz), 3500)
        apply_light(drone, "#2255aa", 5)
        drone.x, drone.y, drone.z = tx, ty, tz
    prev = [(drone.x, drone.y, drone.z) for drone in drones]
```

注意：move2(drone, ..., 3500) 内部已完成 delay(3500)，**不要**再写 drone.delay(...)。


```python
geo = [(x1,y1,z1), (x2,y2,z2), ...]   # 非对称几何，间距≥200cm
geo2 = [(x1,y1,z1), ...]

for i, d in enumerate(drones):
    d.inittime(START_SEC)
    d.delay(i * 80)

for gi in range(2):
    geos = [geo, geo2]
    targets = best_assign(prev, geos[gi]) if gi > 0 else geos[gi]
    for i, d in enumerate(drones):
        move2(d, (clamp_xy(targets[i][0]), clamp_xy(targets[i][1]), clamp_z(targets[i][2])), 1200)
        apply_light(d, "#2255aa", 5)
        d.x, d.y, d.z = targets[i]   # 更新追踪
    prev = [(d.x, d.y, d.z) for d in drones]
```

## 关键：move2 调用方式

正确: move2(d, (x, y, z), t_ms)  -- function.py 封装，内部已完成 VelXY+move2+delay，不要额外加 delay
错误: move2(d, p, t) 之后又写 d.delay(...) -- 会重复计时导致时间溢出
错误: d.move2(x, y, z)           -- 不要用底层 Drone 方法
错误: d.move2(x, y, z, t_ms)     -- 不存在四参数

## 段代码是片断，不是完整脚本

只写段内动作逻辑。**不要写**：
- PYFII_AGENT_SEGMENT_START/END 标记
- drones = [...] 或 Drone(...) 创建
- prev = [...] 硬编码
- import 语句

段代码嵌入到已有 design.py 的 marker 之间执行，drones 和 prev 已存在。


## 非对称几何安全模式（已验证）

第一步：小幅度呼吸（从 prev 偏移 30-40cm）
第二步：非对称大展开（四角/散射/V形，间距≥200cm）

```python
geo1 = [(prev[i][0] + 35*math.sin(i*2.5), prev[i][1] + 35*math.cos(i*2.5), Z1) for i in range(7)]
geo2 = [(x1,y1,z2), ..., (x7,y7,z2)]  # 非对称坐标

for gi in range(2):
    geos = [geo1, geo2]
    targets = best_assign(prev, geos[gi]) if gi > 0 else geos[gi]
    ...
```

关键：第一步小幅度移动让 best_assign 正确排列，第二步大跳时才不会交叉。

## 必须
- 每段结束时必须：prev = [(drone.x, drone.y, drone.z) for drone in drones]


## 已验证通过的具体代码示例

### S02 (13-23s) 通过示例
```python
geo1 = [(prev[i][0] + 40*math.sin(i*2), prev[i][1] + 40*math.cos(i*2), 140) for i in range(7)]
geo2 = [(100,120,170),(280,80,190),(460,140,170),(420,380,180),(200,420,160),(340,340,200),(160,260,180)]
for i, drone in enumerate(drones):
    # auto_init 已在 for 循环前调用; drone.VelXY(120, 240); drone.VelZ(120, 240); drone.delay(i * 80)
for gi in range(2):
    geos = [geo1, geo2]
    targets = best_assign(prev, geos[gi]) if gi > 0 else geos[gi]
    for i, drone in enumerate(drones):
        tx, ty, tz = targets[i]
        dd = math.hypot(prev[i][0]-tx, prev[i][1]-ty)
        spd = min(200, max(100, int(dd/2.0)))
        drone.VelXY(spd, spd*2); drone.VelZ(spd, spd*2)
        drone.move2(clamp_xy(tx), clamp_xy(ty), clamp_z(tz))
        apply_light(drone, '#44aadd', 6)
        ft = flight_time_ms(((tx-prev[i][0])**2+(ty-prev[i][1])**2+(tz-prev[i][2])**2)**0.5, spd, spd*2)
        drone.delay(max(800, int(ft*1.2)))
    prev = [(targets[i][0], targets[i][1], targets[i][2]) for i in range(7)]
```



## 非同步动作（进阶）

不同无人机可以有不同的飞行时间，形成波浪/涟漪效果：

```python
geo = [...]
targets = best_assign(prev, geo)
base_t = 3000  # 基础飞行时间(ms)
for i, drone in enumerate(drones):
    tx, ty, tz = targets[i]
    t = base_t + i * 200  # 每架机递增200ms
    move2(drone, (clamp_xy(tx), clamp_xy(ty), clamp_z(tz)), t)
    apply_light(drone, '#ff8844', 4)
    drone.delay(t + 400)
prev = [(targets[i][0], targets[i][1], targets[i][2]) for i in range(7)]
```

关键：`t = base_t + i * offset` 实现错峰到达。offset 可为正（序列）或负（反向序列）。


## 连续轨迹（高密度关键帧）

用小步长、多 keyframe 模拟连续运动：

```python
n_kf = 8  # 关键帧数量
for gi in range(n_kf):
    angle = 2 * math.pi * gi / n_kf
    r = 180 + 40 * math.sin(angle)
    geo = [(280 + r * math.cos(2*math.pi*i/7 + angle),
            280 + r * math.sin(2*math.pi*i/7 + angle),
            150 + 30 * math.cos(angle)) for i in range(7)]
    targets = best_assign(prev, geo) if gi > 0 else geo
    t = 1500  # 每小段1.5s
    for i, drone in enumerate(drones):
        tx, ty, tz = targets[i]
        move2(drone, (clamp_xy(tx), clamp_xy(ty), clamp_z(tz)), t)
        apply_light(drone, '#44aadd', 2)
        drone.delay(t + 200)
    prev = [(targets[i][0], targets[i][1], targets[i][2]) for i in range(7)]
```

关键：n_kf ≥ 6 时可视为连续运动，步长小避免碰撞。


## 人类编舞知识库（从 output/ 7 个作品蒸馏）

### 空间调度原则
- **大幅度覆盖**：优秀作品 XY 跨度 300-500cm，Z 跨度 200cm+。不要困在中心 280,280
- **中心可以移动**：场地中心不应锁死——重心偏移和回收表达行进、寻找、冲突、收束
- **密度要呼吸**：宽阵→窄阵→团簇→展开交替，不要一直是同心圆等距
- **高度层是叙事**：Z 不仅是避撞，而是塔、帘、斜坡、上升、坠落、聚焦的视觉语言

### 角色与分组
- **角色可变化**：同一机在不同段有不同职责。用 `roles = {0: "wing", 1: "core", ...}` 分配
- **分组差异**：同段内不同机走不同路径——`if role == "wing": ... elif role == "solo": ...`
- **焦点机突出**：选 1-2 架机承担更多/更高的动作，其余配合

### 灯光原则
- **灯光与动作分工**：大动作按 phrase 走，灯光按 beat/onset 走（100/500/1000ms 级）
- **数学驱动颜色**：sin/cos 生成连续颜色变化，不用静态序列
- **灯光密度随能量**：高能段灯光密集，低能段稀疏或暗色

### 禁止退化（Anti-patterns）
- ❌ 固定中心绕圈（同心圆）——那不是编舞，是退化
- ❌ 全体同步 move2——没有角色差异就没有编舞感
- ❌ 均匀模板格——队形要在宽窄疏密间变化
- ❌ 灯光作为装饰——灯光是节奏工具，必须与动作同步

### 主题驱动的动作词汇
从人类作品中提取的主题-动作映射：
- **太空/上升**：逐级 Z 上升、电梯层级、solo_focus、高度层分化
- **推进/启程**：左→右中心迁移、加速展开、大 XY 跨越
- **爆发/冲突**：全场推进、大中心移动、密集切换 + 跑马灯
- **留白/对峙**：负空间、小范围 XY、低 Z 维持、暗色灯光
- **收束/回落**：队形收缩、Z 下降、灯光收束

## 禁止
- 不添加任何 import
- 不调用 d.VelXY/VelZ/delay/move2 底层 API — 只用 move2(d, p, t)
- 不发明不存在属性
- 不同心圆
