# DeepSeek Cannon 设计全流程经验总结

> 为 Agent 搭建提供方法论基础

## 一、流程篇

### 1.1 增量设计是不可妥协的铁律

**教训**: 反复尝试一次性写出5段全量，然后面对数百个警告无从下手。
**正确**: 段1→验证(零警告)→段2→验证→... 逐段追加。

```
for each segment:
   设计几何 → 排列搜索 → read_fii验证 → 零警告通过 → 输出prev → 下一段
```

Agent 实现：每个段独立子任务，输入为`prev状态`，输出为`新段代码 + 新prev + 验证结果`。

### 1.2 不要在没有验证通过时继续

一段有警告就修这一段，不要跳到下一段。"28个警告可接受"的思维导致后续段叠加出上千警告。

### 1.3 纸面设计先于代码

crosscut_v9 的成功在于 phrase 命名和 waypoint 手工设计。代码只是实现手段，不是设计工具。Agent 应先输出几何描述，再生成代码。

## 二、技术篇

### 2.1 排列搜索是核心安全机制

**发现**: 手工指定无人机到目标位置的映射，无论如何小心都会产生路径交叉。
**解法**: `best_assign()` 遍历7!=5040种排列，找到线性插值路径上最小间距最大的分配。

**关键参数**:
- 评分函数: `score = min_distance * 2000 - max_distance * 0.01`
- min_distance权重高(2000)促使搜索选择最安全的分配
- max_distance权重极低(0.01)，几乎不影响选择
- 检查比例: [0.2, 0.4, 0.6, 0.8]，4个采样点足够

**局限**: 首段(散布呼吸)不用搜索——各机在自己起始位附近，直接i→i匹配。用搜索反而会跨机分配。

### 2.2 安全几何库

经过验证的安全几何类型:
- 环 (r=130-200)
- 双排 (间距120, y差200+)
- 四角 (四角+中心+内点)
- 旋转环 (环+小角度偏移)

危险几何类型(易产生碰撞):
- 对角线 (7点共线，排列搜索难以分离)
- 之字形 (间距<100cm)
- 十字 (中心密集)

**原则**: 几何内部各点间距 > 51cm (pyfii F400阈值)，越大越安全。

### 2.3 时间预算

**pyfii飞行时间公式** (a=200cm/s²默认):
- 大距离(d ≥ v²/a): `t = v/a + d/v` (有匀速阶段)
- 小距离(d < v²/a): `t = 2×√(d/a)` (仅加速-减速，未达最大速度)
- 实际配置: accRange(50,400), velRange(20,200)

实际可用时间 = light_ticks×100ms + delay_ms

**计算流程**:
1. 排列搜索后得到每个机的飞行距离d
2. 速度 v = min(200, d/available_time*0.8)
3. 验证: v/200 + d/v < available_time

**常见错误**: delay预算不够导致动作未完成。只要有一个action warning，就要增加delay或提高速度。

### 2.4 灯效

100ms正弦渐变灯效:
```python
for tick in range(ticks):
    bright = 100 + 155*sin(tick*pi/ticks)
    r = base_r * bright // 255
    d.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}"); d.delay(100)
```

- ticks过少: 灯效不明显
- ticks过多: 占飞行时间，导致动作未完成
- 推荐: 10-20 ticks (1-2s)

### 2.5 排队延迟

异步效果通过delay实现:
```python
for i,d in enumerate(ds): d.delay(i*offset_ms)  # offset=100-600ms
```

- 所有机intime统一
- delay错峰出发
- 不能超过该段的时间预算

**注意**: 段间过渡时，前段的排队延迟会导致后段intime冲突。需计算"最晚机的结束时间"来设定下一段的intime。

### 2.6 坐标系与硬约束

| 参数 | F400 |
|------|------|
| XY范围 | [0, 560] |
| Z范围 | [80, 250] |
| VelXY | [20, 400] |
| intime | 必须整数秒 |
| intime | 不可倒退 |
| 段间余量 | >0.5s |

**浮点坐标**: `math.cos/sin`返回浮点数，赋给`d.X/d.Y`会导致.fii文件坐标带小数。必须`int(round(x))`。

## 三、设计篇

### 3.1 队形设计

**重复问题**: 视觉相似即重复，不是坐标不同就不重复。如环/大环/偏转环都是环形——观众看来是同一个东西。

**解决**: 每段用不同的基础几何类型(线/框/环/弧/星/十字/散射等)，不依赖参数变体。

**不对称队形**: T形/L形/拱形等在排列搜索后仍可辨识。对称队形(环/双排)排列后看起来一样。

### 3.2 音乐响应

**错误**: "渐强→动作幅度递增"导致前期无聊、后期凌乱。
**正确**: 
- 队形密度/复杂度随音乐递增
- 节奏变化(段1慢、段2中、段3快)
- 灯光可独立承担音乐表达

### 3.3 疏密节奏

- 段1(低能): 4几何，每几何3s — 慢速展开
- 段2(中能): 3-4几何，每几何2-3s — 中速
- 段3(中高): 队列大转移 — 单几何长距离
- 段4(高能): 数学几何 — 密集变化
- 段5-6: 收缩→炸开 — 动静对比
- 段7-8: 署名+降落 — 收尾

### 3.4 大范围转移

**挑战**: 从四角位置飞向对角位置时，7机同时直线运动会交叉。

**解法**:
- 排队延迟: 不同机在不同时间出发
- 曲线转移: 弧形替代对角线
- 多点过渡: 中间点+排列搜索重新分配

## 四、最终版设计说明 (8段, DS署名, 64.5s, 零警告)

### 4.1 整体结构

| 段 | 时间 | 几何数 | 设计意图 | 关键技法 |
|---|---|---|---|---|
| 段1 | 4-14s | 3×2子步 | 从散布到有序，渐入 | 中点子步增加复杂度 |
| 段2 | 14-24s | 3×2子步 | 对角线→大环→四角，几何丰富 | 排列搜索处理过渡 |
| 段3 | 24-34s | 1大转移 | 弧形大转移，排队错峰 | 排队delay避免交叉 |
| 段4 | 34-42s | 3几何 | 正七边形→星形→螺旋，数学美 | 对称几何天然安全 |
| 段5 | 42-47s | 1收束 | 鳞次栉比收缩向中心 | 排队+收缩环 |
| 段6 | 47-50s | 1炸开 | 同步爆发，动静对比 | 同步move2+白光 |
| 段7 | 50-58s | 3环变体 | 空中炫技，环形变体 | 偏转角避重复 |
| 段8a | 58-60s | D字 | DeepSeek署名 | 左竖3+右弧4 |
| 段8b | 60-63s | S字 | DeepSeek署名 | 手写S形7点 |
| 降落 | 63-65s | — | 收尾 | land() |

### 4.2 几何选择逻辑

- **段1-2**: 安全几何为主(环/双排/四角)，用中点子步增加复杂度但不增加碰撞风险
- **段3**: 弧形替代对角线——直线大转移会产生路径交叉，曲线+排队delay解决了这个问题
- **段4**: 数学几何(正七边形/星形/螺旋)天然间距大，排列搜索轻松处理
- **段5-6**: 收缩→炸开形成动静对比，放大视觉冲击
- **段7**: 环形变体(不同角度偏移)避免重复感
- **段8**: 字母队形手写坐标，D和S间距设计确保排列搜索能找到零碰撞分配

### 4.3 音乐响应

- 卡农 156BPM，0-16s低能→16-32s中能→32-48s中高→48-64s高能
- 段1慢速、段2中速、段3大转移、段4密集变化，对应能量爬升
- 段5-6动静对比对应音乐高潮后的回落
- 灯光颜色随段变化：蓝→橙→红→白→暖色→白→签名蓝

### 4.4 最终指标

- XY(490,502): 近乎全场覆盖
- minD=51cm: 刚好在F400安全阈值边
- 0 distance warnings / 0 action warnings
- 2D/3D视频: `output/deepseek_cannon/`

## 五、协作篇

### 5.1 用户反馈的价值

纯AI原生设计(v5)产生526警告+大量动作未完成。人工迭代后(v3+)达到零警告。用户的视觉验收发现了我看不到的问题：队形重复、高度单调、灯光简陋。

### 5.2 沟通问题

- 我看不到视频，只能靠用户描述判断效果
- 多次"改了但没生效"——文件编辑操作不可靠
- S字设计反复4次才通过——缺乏视觉闭环

**Agent启示**: Agent必须有视觉验证能力(通过read_fii的warning作为代理信号)。

## 六、Agent设计路线图

### 6.1 核心能力

1. **分段生成**: 输入prev状态+段时长+音乐能量，输出几何+代码
2. **排列搜索**: 内置best_assign，自动找最安全分配
3. **自我验证**: read_fii + show(show=False) 检查warning
4. **几何库**: 预置安全几何模板，按需组合
5. **时间计算**: 精确计算飞行时间，自动调整light/delay

### 6.2 流程

```
for segment in music_segments:
    energy = analyze(segment)
    geometries = generate_geometries(energy, prev_state, library)
    code = generate_code(geometries, time_budget)
    warnings = validate(code)
    while warnings > 0:
        adjust(code)  # 调间距/速度/delay
    prev_state = extract_final_positions(code)
    append_to_script(code)
```

### 6.3 几何库

每类几何有参数(半径/间距/中心/角度)，Agent按需实例化。

### 6.4 待解决问题

- 如何从音乐自动提取段边界和能量值
- 几何"视觉差异"的量化指标
- 自动化时间线管理(段间intime计算)
- 灯光模式库的建设

## 附录：最终版蒸馏卡片

- 来源：`tests/_cannon_seg1.py` (commit `c417bfa`)
- 音乐：`cannon_in_D.mp3`，68s，156BPM
- 设备：F400 × 7
- 视频：`output/deepseek_cannon/2d.mp4` + `3d.mp4`
- 关键技术：排列搜索(权重2000)、100ms正弦渐变灯效、排队延迟(80-700ms)、距离调速、中点子步、弧形大转移
- 几何库：散布呼吸、环(130-200)、双排、四角(四角+中心+内点)、旋转环(多角度偏移)、正七边形、4-fold星形、螺旋、D字(左竖3+右弧4)、S字(手写7点曲线)
- XY覆盖：490×502（全场极限）
- 安全性：0距离警告、0动作未完成、minD=51cm

```json
{
  "source": "tests/_cannon_seg1.py",
  "duration": "64.5s",
  "segments": [
    {
      "time_range": [0, 4],
      "intent": "七机散布起飞",
      "music_cue": "能量0.10，前奏",
      "formation": "六角散布(60-500范围)+中心(280,280)",
      "z_range": "100-110cm",
      "speed": "—"
    },
    {
      "time_range": [4, 14],
      "intent": "从散布渐入有序：呼吸→环130→双排",
      "music_cue": "能量0.25-0.33，主题引入",
      "formation": "每几何×2子步(中点过渡)，3几何=6运动阶段",
      "z_range": "115-155cm，高度差5cm/机",
      "speed": "VelXY(120,240)，子步内按距离动态调速",
      "light": "#2255aa/#3388cc正弦渐变, 8+8 tick每子步",
      "key_technique": "中点子步增加复杂度但不增加碰撞风险"
    },
    {
      "time_range": [14, 24],
      "intent": "几何丰富展开：对角线→大环150→四角",
      "music_cue": "能量0.37-0.40，声部叠加",
      "formation": "3几何×2子步，对角线(80间距)→环→四角外扩",
      "z_range": "155-180cm",
      "speed": "VelXY(120,240)，排队100ms，按距离调速",
      "light": "#cc6600/#cc8800/#ddaa00渐变, 8+8 tick",
      "key_technique": "排列搜索处理非安全几何(对角线)的过渡"
    },
    {
      "time_range": [24, 34],
      "intent": "弧形大转移——从四角飞向弧形，排队错峰避碰撞",
      "music_cue": "能量0.47-0.55，中高能",
      "formation": "单几何弧形(160+60i,200+120sin(i))，排队700ms/机",
      "z_range": "195cm",
      "speed": "VelXY(180,360)，排队后全速",
      "light": "#cc2244, 30 tick (3s展示)",
      "key_technique": "曲线替代对角线+排队delay=大转移零碰撞"
    },
    {
      "time_range": [34, 42],
      "intent": "数学几何美：正七边形190→4-fold星形→螺旋内收",
      "music_cue": "能量0.55-0.61，高能高潮",
      "formation": "3几何无子步，排队600ms，对称几何天然安全",
      "z_range": "205-220cm",
      "speed": "VelXY(150,300)，按距离调速",
      "light": "#ffffff/#ffddee/#ffbbdd, 25 tick (2.5s展示)",
      "key_technique": "对称几何天然间距大，排列搜索轻松处理"
    },
    {
      "time_range": [42, 47],
      "intent": "鳞次栉比收缩向中心环80",
      "music_cue": "能量0.53→回落，高潮后",
      "formation": "单几何收束环，排队300ms/机",
      "z_range": "150cm",
      "speed": "VelXY(100,200)",
      "light": "#ffbb88, 15 tick",
      "key_technique": "排队+收缩=鳞次栉比视觉效果"
    },
    {
      "time_range": [47, 50],
      "intent": "同步炸开——所有机从中心环同时爆发式外飞",
      "music_cue": "能量骤降前最后一次爆发",
      "formation": "大环200，所有机同步move2",
      "z_range": "210cm",
      "speed": "VelXY(200,400)",
      "light": "#ffffff, 18 tick (1.8s白光)",
      "key_technique": "同步+白光=爆发感，中心向外放射无交叉"
    },
    {
      "time_range": [50, 58],
      "intent": "空中炫技：3个环形变体(190/180/170，不同偏转角)",
      "music_cue": "能量回落(~0.50)，收束前展示",
      "formation": "偏转环(π/4)→偏转环(-π/5)→偏转环(π/6)",
      "z_range": "215-220cm",
      "speed": "VelXY(160,320)，排队500ms，按距离调速",
      "light": "#ffddee/#ffccdd/#ffbbcc/#ffaabb, 10 tick",
      "key_technique": "环形变体不同偏转角=避免重复感"
    },
    {
      "time_range": [58, 60],
      "intent": "D字署名——左竖3机+右弧4机",
      "music_cue": "能量低位，收尾",
      "formation": "D: (180,120)(180,280)(180,440)+(300,100)(380,200)(380,360)(300,460)",
      "z_range": "180-190cm",
      "speed": "VelXY(120,240)",
      "light": "#44aadd, 10 tick",
      "key_technique": "手写字母坐标，间距设计确保排列搜索零碰撞"
    },
    {
      "time_range": [60, 63],
      "intent": "S字署名——上下横线+弧线",
      "music_cue": "音乐即将结束",
      "formation": "S: (180,100)(320,100)(360,200)(240,280)(160,360)(240,440)(360,460)",
      "z_range": "190cm",
      "speed": "VelXY(120,240)",
      "light": "#44aadd, 10 tick",
      "key_technique": "手写S形7点，D→S排列搜索(w=2000)零碰撞过渡"
    },
    {
      "time_range": [63, 65],
      "intent": "全体降落",
      "music_cue": "音乐结束(68s)，3s余量",
      "formation": "land()",
      "z_range": "→0",
      "speed": "—"
    }
  ]
}
```

## 七、代码修改方法论（避免文件损坏）

### 7.1 问题根因

两天内文件损坏 10+ 次，根因：

1. **`edit_file` 的搜索/替换不精确**：old_string 和 new_string 有细微差异（缩进、空格、变量名）时产生混合代码
2. **Python `str.replace` 的字符串匹配失败**：代码中看似相同的行实际有不同的尾随空格或注释
3. **`write_file` 覆盖整个文件**：一旦用错，所有段丢失
4. **多次增量修改累积错误**：每次改一点，5次后代码面目全非
5. **没有验证步骤**：改完直接跑，SyntaxError 才回头找

### 7.2 Agent 代码修改规范

**原则一：最小修改单元**

不要用 `edit_file` / `str.replace` 修改已有代码。改为：

```
1. 读取完整文件
2. 用 ast/parso 解析 AST
3. 在 AST 层面修改（替换函数体、修改变量值）
4. 用 ast.unparse() 写回
5. 语法检查（compile）
6. 运行验证（read_fii + show）
```

若 AST 不可用，退而求其次：用精确的行号范围替换，避免字符串匹配。

**原则二：修改前备份**

```
cp script.py script.py.bak.$(date +%s)
```

任何修改失败后，从备份恢复。

**原则三：单次修改单次验证**

```
修改 → compile检查语法 → 运行 → read_fii → 警告为0 → 提交
```

不在一个修改中做多件事。一次只改一个参数（速度、间距、delay）。

**原则四：增量追加优于修改已有**

对于逐段设计，最佳方式是不修改已有段：
```
# 段1 (锁定)
... 
# 段2 (锁定)
...
# 段3 (新段) ← 只追加，不修改前面
```

### 7.3 常见补丁模式

| 问题 | 检测 | 修复方式 |
|------|------|----------|
| 动作未完成(action warning) | `grep -c 'action isn'` | 提速 VelXY(200,400) / 减 light ticks / 增 delay |
| 距离过近(distance warning) | show(show=False) | 增几何间距 / 提排列搜索权重 / 换安全几何 |
| 坐标越界 | `Exception: Out of range` | `max(10, min(550, x))`  clamp |
| 时间冲突 | `Time arrangement error` | 推后 intime / 减 delay / 合并几何 |
| 浮点坐标 | `ValueError: invalid literal` | `int(round(x))` |
| 语法错误 | `compile(script)` | 从 git 回退，重新改 |

### 7.4 Agent 自修复流程

```
while True:
    run script
    if SyntaxError:
        restore from git
        retry with different strategy
    if action_warnings > 0:
        increase speed or reduce light ticks
    if distance_warnings > 0:
        increase geometry spacing or search weight
    if time_error:
        push intime forward
    if out_of_range:
        add clamp
    if all_zero:
        break
```

### 7.5 重要教训

- **信 pyfii，不信自己**：pyfii 的 warning 是权威。不要自己写验证函数，不要设自定义安全常量。
- **action warning 和 distance warning 同等重要**：长期忽略 action warning 导致轨迹误差。
- **速度是最后一个变量**：先确定几何和时间线，最后调速度。
- **200 是硬上限**：VelXY max=200。如果 200 都飞不完，必须调时间或距离。
