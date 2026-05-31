# Pyfii Distilled Choreography Patterns

本文件是人类编舞经验蒸馏，优先级高于“凑过验证”。你不是在排列 7 个点，而是在为音乐设计 3D 舞台运动。

## 设计前先写段落草图

生成代码前，在心里完成这四项，再落成 Python：

1. `beats`: 把段落切成 2-5 个 keyframe interval。
2. `story`: 每个 interval 的动机，例如散开、汇聚、推进、抬升、回卷、收束。
3. `layers`: low/mid/high 高度层，哪些机升、哪些机降、哪些保持前景。
4. `speed`: 每个 interval 期望持续多久，按 3D 距离选速度/加速度。

坏：先写一串 target，然后用 delay 修到段尾。
好：先定“这个 2.2 秒是斜向推进同时抬升”，再设计 target 和速度。

agent 可以在草图阶段使用 planning tools 或临时 helper，把自然语言意图转成：

```text
keyframe cue -> geometry layer -> safe assignment -> per-drone speed/accel/delay table
```

final `design.py` 只保留这些具体表和 PyFii 命令，不保留规划工具函数。

## 样例 A：晨光开场

意图：分散低密度开场，逐步汇聚成有方向的推进，再舒展到开阔姿态。

结构：

```text
4.0-5.4  起飞后低层散布，A 组先动，B 组后动，形成晨光开始流动
5.4-7.6  扇形向前推进，中间 1 架抬到 high，左右翼保持 mid
7.6-10.2 双弧线打开，前景低、后景高，避免同心圆
10.2-12.7 斜向收束到开阔终止姿态，至少 3 架仍在移动到 12s 后
```

要点：

- 不要从标准圆开始；起飞点可以是非对称散布或浅 V。
- 高度随叙事推进：low -> mixed -> high/mid -> resolved。
- 末尾收束不是小波动，而是进入一个新构图。

坏味道：

```text
ring r=130 z=150 -> ring r=180 z=150 -> ring r=220 z=150
```

## 样例 B：Canon 推进

意图：同一个主题分组错峰进入，但不是每架机排队孤立动。

结构：

```text
13.0-14.0  A 组 3 架斜向推进并升高
13.5-15.0  B 组 2 架从另一侧切入，形成交错但不同高度避让
14.2-16.2  C 组 2 架补齐前景，A 组继续进入下一 keyframe
16.2-20.0  三组重叠流动，不能出现只有一架在慢挪
20.0-22.6  全队回卷到非圆终止姿态
```

代码倾向：

```python
groups = {
    "A": [0, 2, 4],
    "B": [1, 5],
    "C": [3, 6],
}
group_offsets_ms = {"A": 0, "B": 450, "C": 850}
```

错峰是为了形成重叠运动，不是让大家依次孤零零地走完。

## 样例 C：非圆几何替代

当你想写“开阔、庄严、对称”时，不要默认圆。可选：

- 浅 V：中轴高，两翼中低，适合推进。
- 双弧：左右两组是不同半径/不同高度，不共享同一个中心。
- 星芒：中心只允许 0-1 架，其它点在射线上分层，避免穿心。
- 斜框线：四角不是静态方框，而是沿对角线滚动。
- 波浪：X/Y 与 Z 都有相位差，不能只是同一平面蛇形。

坏：

```python
[(280+r*cos(2*pi*i/N+phase), 280+r*sin(...), 160) for i in range(N)]
```

好：

```python
targets = [
    left_low, left_mid, center_high, right_mid, right_low, back_high, front_low
]
```

## 样例 D：高度层写法

固定高度会让画面像 2D 队形图。每段至少设计 2-3 个高度层。

```python
height_layers = {
    "low": 115,
    "mid": 155,
    "high": 205,
}

if i in front_group:
    z = height_layers["low"]
elif i == focus_drone:
    z = height_layers["high"]
else:
    z = height_layers["mid"] + 15 * math.sin(i)
```

经验：

- 前景低、后景高，画面更有深度。
- 汇聚时可以整体升高，收束时可以局部压低。
- Z 变化要和 XY 运动同时发生，不要最后追加几下上下抖动。

## 样例 E：速度/加速度节奏

不要整段一个速度。速度表达音乐：

```python
intervals = [
    {"seconds": 1.6, "feel": "quick ignition"},
    {"seconds": 2.4, "feel": "broad expansion"},
    {"seconds": 2.0, "feel": "gathering"},
    {"seconds": 2.6, "feel": "resolved finish"},
]
```

经验：

- 远距离大展开可用 140-200，短距离过渡可用 60-110。
- acceleration 是独立节奏参数；`a = 2v` 只是常用稳定候选，不要写死。
- 如果动作太早结束，先降速或拉长路线，不要补 delay。
- 如果 action warning，提速、缩短距离，或增加这次 move 后的执行预算。

## 样例 F：段尾收束

段尾最后 1 秒必须是有意义的群体收束。

坏：

```text
主体 8s 完成 -> 最后 3s 单机小 Z 波动 / 纯灯光 / 每架依次 delay
```

好：

```text
最后 1.8s 全队从双弧收成斜向 V；前景 3 架降低，后景 4 架升高，12.0s 后仍有至少一组共同运动
```

收束姿态应成为下一段入口，而不是临时补丁。

## 样例 G：安全但不保守

安全不等于缩小动作。避免中心对穿的办法：

- 扇区保持：每架机保持大致区域，但区域内部做弧线和高度变化。
- 分层避让：交错时用不同 Z，但不要靠 Z 单独躲；XY 路径仍要错开。
- 交换分组：不是全队同时换位，而是 2-3 组重叠切换。
- 外圈绕行：需要换到对侧时沿外弧走，不穿中心。

坏：所有机缩到中心 250-330 的小范围。
好：全场 XY span 400+，但路径不互相切穿。

## 生成前自检

输出代码前自查：

- 是否有 2-5 个有动机的 keyframe interval？
- 是否至少两种非同构几何或路线趋势？
- 是否有 low/mid/high 高度层，而不是固定 z？
- 是否每个 keyframe 都按 3D 距离调速？
- 是否最后 1 秒仍有有效群体运动？
- 是否没有用圆形参数变体、单机小波动、长 delay 凑时长？

## 计算沙箱

生成代码前，先在 agent 规划阶段计算最佳排列和飞行时间。不要把沙箱计算块写进 final segment：

```python
# === SANDBOX_CALC ===
prev = [(x1,y1,z1), ...]
geo = [(x1,y1,z1), ...]

# 计算最佳排列
targets = best_assign(prev, geo)  # 返回重排后的 targets 列表，不拆 perm/min_d

# 计算飞行时间
v, a = 200, 400
for i in range(7):
    d = distance_3d(prev[i], geo[i])
    ft = flight_time_ms(d, v, a)
    # d7: dist=Xcm, flight=Yms

# === SANDBOX_END ===
```

然后将计算结果变成 final 代码里的常量：
- targets = best_assign(prev, geo)  # 或直接写硬编码 targets 表
- move2(drone, target, flying_ms)
- drone.delay(Y)  # flying_ms - light_ticks*100 + margin

## DNTG 反算速度

```python
def vel_for_distance_time(distance_cm, time_s):
    for v in range(50, 201):
        if time_s > flight_time_s(distance_cm, v, v*2):
            return v
    return 200
```

## 时间预算速查
每个 move2 需要的 delay = flight_time_ms(d, v, a) - light_ticks*100 + 100。
全段总 delay 累加必须小于正式窗口长度 * 1000 - 1000ms 余量。
