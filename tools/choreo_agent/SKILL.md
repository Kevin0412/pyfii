# Pyfii Choreography Skills

> Generated file. Edit `core/skills.py` (the registry) and regenerate — do not
> hand-edit the cards below. Regenerate with:
> `python -c "import core.skills as s, pathlib; pathlib.Path('SKILL.md').write_text(s.render_full_skill_doc())"`

This is the explicit catalog of the Pyfii Choreo Agent's **choreography skills**:
the semantic units the internal AI agent uses to turn music into a 3D drone show.
It is Stage 1 of *internal skillization* — making the abilities that already live
in `project_template/scripts/function.py` explicit, documented, and testable.

## Primitive vs. skill

- A **primitive function** is the executable implementation in `function.py`
  (e.g. `ripple_move`, `light_wave`). It is the *kernel*.
- A **skill** is the semantic choreography unit built around a primitive (or, for
  composites, around several): it carries purpose, when-to-use / when-not, key
  parameters, safety constraints, common validation failure modes, an example,
  and which other skills it combines with.

Two kinds:

- **Primitive skills** wrap exactly one `function.py` function.
- **Composite skills** are *documented patterns* that combine primitives into a
  recognizable phrase (e.g. *center-out climax*, *call-and-response*). They are
  **not** new functions and carry **no hardcoded coordinate tables** — the agent
  writes its own geometry with `custom_points(...)` each time. This deliberately
  avoids the template degeneration that retired the old `geo_*` helpers.

## Anatomy of a skill card

`category` (motion / lighting / timing / grouping / composition) · `role fit`
(which musical section: opening / buildup / development / expand / climax /
transition / closure / calm) · `purpose` · `when to use` · `when NOT` ·
`key params` · `safety` · `validation risks` · `combines with` · `example`.

## Safety & validation philosophy

Skills never weaken Pyfii's deterministic gates — they make success *more likely*
by telling the agent the constraints up front. Every card names its **validation
risks** and the gate that guards them:

- **collision gate** — `dense_minD > 51cm`; XY spacing is the hard floor. Always
  pass `targets` through `best_assign` / `far_assign` before any executor.
- **window-fill gate** — each segment's content must fill its music window
  (cursor within −1.0/+1.5s of the window end), or the show desyncs from the
  cues. Motif executor durations are deterministic — sum them to the window.
- **low-activity / effective-motion gate** — lighting-only or static stretches
  without real movement get rejected; lit holds are fine, dark stillness is not.
- **sync gate (S02–S05)** — at least one keyframe must break time-sync; the wave
  executors and `ripple_delays` provide this for free (unless delays degenerate
  to all-zero on a ring — use `spiral`/`sweep` there).

The registry (`core/skills.py`) is the single source of truth; the prompts and
this document are generated from it, and `core/test_skills.py` enforces that
every documented skill maps to a real function.

## Primitive skill cards

### wave-ripple-move  ·  `ripple_move()`

- **category**: motion
- **role fit**: buildup, development, expand, climax, any
- **purpose**: 波次推进：每架机按 delays 错峰启动飞向 targets，启动瞬间点亮——先动先亮。
- **when to use**: 需要队形整体迁移又要有方向感/层次感时；中心向外扩散、横向扫过、螺旋展开。
- **when NOT**: 需要严格同步齐动的宣言时刻；或本段只做灯光不移动（用 light_wave）。
- **key params**: flying_ms 飞行时长；delays 用 ripple_delays(prev, mode=...) 算；hold_ticks 亮灯节拍；gradient_to= 飞行中持续变色（强烈推荐增加色彩）。
- **safety**: 内部用 best_assign/far_assign 后的 targets，自身不保证路径间距——targets 必须先经安全分配；段尾自动对齐 max(delays)+flying_ms。
- **validation risks**: 若 delays 全为 0（环形队形 center_out 退化）则同起同停，触发同步门；路径太近触发碰撞门。
- **combines with**: wave-delays, spatial-ranks, light-wave, safe-assign
- **music fit**: 渐强段、推进段、连续律动段。

```python
delays = ripple_delays(prev, mode='spiral', step_ms=150)
prev = ripple_move(drones, best_assign(prev, geo), 2600, delays, colors=palette, hold_ticks=8, gradient_to=cool)
```

### chain-follow  ·  `follow_chain()`

- **category**: motion
- **role fit**: development, transition, expand
- **purpose**: 链式跟随/蛇形：头机沿 waypoints 逐点推进，后机依次延迟 lag_hops 跳走同一路径。
- **when to use**: 蛇形游走、领舞带队、长线条流动；想要单一清晰路径而非整体平移。
- **when NOT**: 需要全场铺开的对称构图；机数多且路径弯折密集（链上间距易不足）。
- **key params**: waypoints 路径点（≥(机数-1)*lag_hops+1 个）；hop_ms 每跳时长；lag_hops 跟随间隔；进链顺序自动按离 waypoints[0] 远近。
- **safety**: 函数自校验：相距 lag 的波点对 XY 必须 ≥min_xy_cm(默认51)，否则抛错；preflight 也会静态预检报数。每机总耗时=len(waypoints)*hop_ms，天然对齐。
- **validation risks**: 波点不足或链上间距不足直接运行期抛错；waypoints 过密触发碰撞门。
- **combines with**: handwritten-geometry
- **music fit**: 流动的旋律线、行进段、过渡段。

```python
wps = custom_points([...一条蛇形路径...], min_xy_cm=60)
prev = follow_chain(drones, wps, 700, lag_hops=1, colors=palette)
```

### group-call-response  ·  `group_relay()`

- **category**: motion
- **role fit**: buildup, development, climax
- **purpose**: 分组问答接力：lead 组先动（另一组原地亮灯应答），到位后另一组再动——组色对话。
- **when to use**: 左右/前后两组呼应、一问一答的乐句结构、对称交替的能量。
- **when NOT**: 全队需要统一动作时；奇偶交替分组在视觉上读不出两组时。
- **key params**: group_ids 用 split_groups(prev, mode=...) 算；flying_ms 单程时长；gap_ms 问答间隔；colors=(组0色,组1色)；gradient_to 可加渐变。
- **safety**: **每架机飞向自己的 targets[i]，gids 只决定先后时序，不是让两组飞向同一组点**——两组的目标必须在不同空间区域，否则两组先后穿过同一片空间会对穿碰撞。总时长=2*flying_ms+gap_ms，所有机段尾自动对齐；应答组等待期间持续亮灯。targets 仍需 best_assign/far_assign 安全分配。
- **validation risks**: 两组路径交叉触发碰撞门；分组在空间上不可分时读作噪声。
- **combines with**: split-groups, safe-assign
- **music fit**: 对答式乐句、呼应段、交替强拍。

```python
gids = split_groups(prev, mode='left_right')
prev = group_relay(drones, best_assign(prev, geo), gids, 2300, colors=('#ff6040','#4060ff'), gap_ms=250)
```

### light-wave  ·  `light_wave()`

- **category**: lighting
- **role fit**: opening, calm, transition, development, any
- **purpose**: 静止队形上的灯光涟漪：按 delays 依次点亮，不移动，段尾对齐。
- **when to use**: 定格造型上让光波扫过（开场点亮、留白呼吸、过渡换色）；亮灯定格的首选。
- **when NOT**: 需要真实位移制造能量时（光不动会触发低活动/有效运动门）。
- **key params**: delays 用 ripple_delays(prev, mode=...) 算（与动作同一份=先动先亮）；hold_ticks 每机亮灯节拍；gradient_to= 流光溢彩。
- **safety**: 不移动——只能用在已有真实运动的段里做定格点缀，不能单独撑满整段，否则低活动门打回。耗时=max(delays)+hold_ticks*100。
- **validation risks**: 整段只有 light_wave 无移动→低活动门 / 有效群体运动门打回。
- **combines with**: wave-delays, wave-ripple-move, static-pose-active-light
- **music fit**: 长音、留白、段落起句的点亮。

```python
delays = ripple_delays(prev, mode='center_out', step_ms=120)
light_wave(drones, delays, palette, hold_ticks=6, gradient_to=cool)
```

### group-fade  ·  `fade_group()`

- **category**: lighting
- **role fit**: transition, closure
- **purpose**: 全队同步渐变：duration_ms 内 c_from→c_to（dntg 式持续变色）。
- **when to use**: 段落间换色过渡、收束渐隐、情绪转换。
- **when NOT**: 需要逐机独立色彩身份时（用 per-drone gradient_to）。
- **key params**: c_from/c_to 起止色；duration_ms 渐变时长。
- **safety**: 纯灯光不移动；与移动段衔接或定格期使用，单独使用需确保该区间有运动覆盖。
- **validation risks**: 长时间静止渐变无移动→低活动门。
- **combines with**: ending-flash-fade-closure, breathing-transition
- **music fit**: 渐弱、转场、尾声。

```python
fade_group(drones, '#ffd060', '#101060', duration_ms=1800)
```

### group-breathe  ·  `breathe_group()`

- **category**: lighting
- **role fit**: opening, calm, transition
- **purpose**: 呼吸明暗：亮度按余弦凹陷到 floor 再回满，cycles 个周期，全程亮灯。
- **when to use**: 定格造型上的呼吸感（留白、蓄力、静态展示）；满亮起步衔接前一拍。
- **when NOT**: 高能爆发段（呼吸太柔）。
- **key params**: color 基色；cycles 周期数；period_ms 单周期时长；floor 最暗亮度比例。
- **safety**: 不移动；用于已有运动的段内定格期。耗时=cycles*period_ms。亮灯不间断，合法定格。
- **validation risks**: 整段只呼吸不动→低活动门。
- **combines with**: static-pose-active-light, breathing-transition
- **music fit**: 安静段、悬停、蓄力。

```python
breathe_group(drones, (120, 40, 255), cycles=2, period_ms=1600)
```

### group-flash  ·  `flash_group()`

- **category**: lighting
- **role fit**: climax, closure
- **purpose**: 全队同步频闪：times 次亮-灭，可双色交替，结束自动回亮（防黑灯静止）。
- **when to use**: 强拍宣言、高潮齐爆、结尾标点。
- **when NOT**: 柔和过渡、留白（频闪太硬）；不要连续多段反复用（疲劳）。
- **key params**: color 主色；times 次数；on_ms/off_ms 亮灭时长；alt_color 双色交替。
- **safety**: 结束自动回亮 color，不会留下黑灯静止；本身不移动，配合到位定格或强拍使用。
- **validation risks**: 在静止段长时间频闪占时但无移动→低活动门；过度使用降低观感。
- **combines with**: ending-flash-fade-closure, center-out-climax
- **music fit**: 重拍、爆点、收束标点。

```python
flash_group(drones, '#ffffff', times=3, on_ms=200, off_ms=120, alt_color='#ff3030')
```

### spatial-ranks  ·  `spatial_ranks()`

- **category**: timing
- **role fit**: any
- **purpose**: 按空间结构给每架机波次序号 rank（0=第一波），动序即光序的底层计算器。
- **when to use**: 需要按构图位置决定先后（中心先/边缘先/扫过/螺旋）时的底层工具。
- **when NOT**: 通常直接用 ripple_delays（它内部调用本函数并乘步长）。
- **key params**: mode=center_out/sweep_x/sweep_y/spiral/by_index；reverse 反向；quantize_cm 合并相近波。
- **safety**: 纯计算，无副作用。注意环形/等距队形 center_out 会全员同 rank（退化为同步）——要可见波次改 spiral/sweep。
- **validation risks**: 无（计算器）；但退化的 rank 会让下游 ripple_move 同起同停触发同步门。
- **combines with**: wave-delays
- **music fit**: 通用底层。

```python
ranks = spatial_ranks(prev, mode='center_out')
```

### wave-delays  ·  `ripple_delays()`

- **category**: timing
- **role fit**: any
- **purpose**: 波次延迟表(ms)=rank*step_ms，直接喂 ripple_move / light_wave，是动序即光序的纽带。
- **when to use**: 任何波次推进/光波。同一份 delays 同时喂动作和灯光就是先动先亮。
- **when NOT**: 需要全员同步时（delays=全0 等于不错峰）。
- **key params**: mode 同 spatial_ranks；step_ms 波间步长(120-250 常用)；reverse 边缘先动=收拢。
- **safety**: 纯计算；环形 center_out 退化提醒同 spatial-ranks。
- **validation risks**: 退化 delays→同步门。
- **combines with**: wave-ripple-move, light-wave, spatial-ranks
- **music fit**: 通用底层。

```python
delays = ripple_delays(prev, mode='sweep_x', step_ms=150)
```

### split-groups  ·  `split_groups()`

- **category**: grouping
- **role fit**: any
- **purpose**: 把当前队形按空间结构分成 0/1 两组，返回每机组号——问答/异步分组的输入。
- **when to use**: 需要左右/前后/内外/奇偶两组对比或对话时。
- **when NOT**: 全队统一动作；分组在空间上不可分辨时。
- **key params**: mode=left_right/front_back/inner_outer/alternate。
- **safety**: 纯计算；分组应在空间上可读（left_right/front_back 优于 alternate）。
- **validation risks**: 无（计算器）。
- **combines with**: group-call-response
- **music fit**: 通用底层。

```python
gids = split_groups(prev, mode='left_right')
```

### beat-ms  ·  `beat_ms()`

- **category**: timing
- **role fit**: any
- **purpose**: 节拍转毫秒：把动作/灯光时长贴到音乐拍上。beat_ms(120,4)=2000ms。
- **when to use**: 想让 keyframe / 频闪 / 光波节奏对齐 BPM 时。
- **when NOT**: 段落由 phrase 而非 beat 驱动时（大动作按句走）。
- **key params**: bpm 节拍；beats 拍数（动作用 2-4 拍，灯光跟拍用 0.5-1 拍）。
- **safety**: 纯计算；结果仍受单 keyframe 可完成路径长度约束（别用半拍硬飞跨场）。
- **validation risks**: 过短 flying_ms 配长路径→动作未完成门。
- **combines with**: beat-aligned-light-wave, wave-ripple-move
- **music fit**: 强节奏、律动明确的音乐。

```python
flying_ms = beat_ms(bpm, 4)   # 4 拍一个 keyframe
```

### drone-fade  ·  `fade_rgb()`

- **category**: lighting
- **role fit**: any, development
- **purpose**: 单机颜色渐变 c_from→c_to（dntg 持续变色的最小单元）。
- **when to use**: 在 per-drone loop 里给每架机独立的色彩演化；ripple_move 的 gradient_to 内部即用它。
- **when NOT**: 需要全队统一渐变时（用 fade_group）。
- **key params**: c_from/c_to；steps 插值步数；interval_ms。
- **safety**: 纯灯光；耗时=steps*interval_ms，嵌进飞行窗口避免动作后长亮静止。
- **validation risks**: 动作完成后长时间单机渐变静止→低活动门。
- **combines with**: wave-ripple-move
- **music fit**: 色彩叙事、个体身份。

```python
fade_rgb(drone, '#ff4040', '#4040ff', steps=20)
```

### safe-assign  ·  `best_assign()`

- **category**: composition
- **role fit**: any
- **purpose**: 最优安全分配：把 prev 到 geo 的映射重排成路径间距最大的就近方案。
- **when to use**: 每次设定 targets 前都要做——承接、收束、小幅重排首选；所有母题执行器的 targets 必须先经安全分配。
- **when NOT**: 需要大幅交换/展开时（用 far-assign）；刚体旋转/镜像/身份保持等专门映射（rotate_assign/mirror_assign/keep_assign）。
- **key params**: best_assign(prev, geo) 就近收束。返回 targets 列表，不要拆 perm/min_d。
- **safety**: 这是碰撞安全的第一道防线；时间同步采样最小路径间距最大化。
- **validation risks**: 跳过安全分配直接用原始 geo→碰撞门。
- **combines with**: handwritten-geometry, wave-ripple-move, group-call-response, far-assign
- **music fit**: 通用底层。

```python
targets = best_assign(prev, geo)
```

### far-assign  ·  `far_assign()`

- **category**: composition
- **role fit**: expand, climax, development
- **purpose**: 鼓励大距离安全交换的分配：在保持路径间距前提下奖励更长中位路径——制造展开、回卷、交换大动作。
- **when to use**: S04/S05 等长段、或反馈说路径太短/小范围抖动时；想要大幅位移而不退化成小挪动。
- **when NOT**: 承接/收束等需要就近稳定时（用 safe-assign）。
- **key params**: far_assign(prev, geo, min_path_cm=active_min_path_cm(flying_ms)[, min_spacing_cm=140])。返回 targets 列表。
- **safety**: 内部用时间同步采样惩罚碰撞并奖励中位路径；仍受单 keyframe 可完成路径长度约束（配合合理 flying_ms）。
- **validation risks**: min_path_cm 配过短 flying_ms→动作未完成门；过度大交换增加碰撞门压力。
- **combines with**: handwritten-geometry, wave-ripple-move, density-expand-contract
- **music fit**: 高潮、大展开、强能量段。

```python
targets = far_assign(prev, geo, min_path_cm=active_min_path_cm(2800))
```

### handwritten-geometry  ·  `custom_points()`

- **category**: composition
- **role fit**: any
- **purpose**: 标准化手写坐标表并校验帧内 XY 间距——正式编舞构图的主入口。
- **when to use**: 每个 keyframe 的目标构图都先写成 custom_points([...], n=len(drones), min_xy_cm=90)。
- **when NOT**: 灯光/分组等非坐标数据。
- **key params**: points 坐标表（整数表或 math 表达式）；n 机数；min_xy_cm 51-90（密集造型 55-75）。
- **safety**: 运行期裁剪坐标(XY0-560/Z80-250)并校验最小间距；comprehension 必须包进它，否则 preflight 打回。
- **validation risks**: min_xy 不足直接抛错；不包 custom_points 的 computed 点表被 preflight 拒。
- **combines with**: safe-assign
- **music fit**: 通用底层。

```python
geo = custom_points([(280+170*cos(2*pi*i/9), 280+170*sin(2*pi*i/9), 160+25*sin(i)) for i in range(9)], n=9, min_xy_cm=90)
```

### rotate-orbit  ·  `rotate_assign()`

- **category**: composition
- **role fit**: development, transition, expand
- **purpose**: 旋转分配：按角序把每架机映射到沿环移动 steps 位的目标——整体漩涡/轨道旋转。
- **when to use**: 同构队形（圆环/对称阵）想整体转动时；刚体旋转机间距离恒定，天然安全。
- **when NOT**: 异构队形（旋转会让间距突变）；需要大幅换位时（用 far-assign）。
- **key params**: rotate_assign(prev, geo, steps=±k)。steps 越大转动越剧烈，可负反向。geo 应与 prev 同构（同半径环）。
- **safety**: 同构刚体旋转最小间距恒定——这是最安全的大幅运动之一；仍需 ripple_move 错峰让观感更顺。
- **validation risks**: geo 与 prev 不同构时旋转路径可能交叉→碰撞门；纯旋转 Z 不变易触发固定高度退化，配合 Z 个性。
- **combines with**: handwritten-geometry, wave-ripple-move
- **music fit**: 回旋、盘旋、漩涡式律动。

```python
geo = custom_points([(280+170*cos(2*pi*i/9), 280+170*sin(2*pi*i/9), 150+30*sin(i)) for i in range(9)], n=9)
prev = ripple_move(drones, rotate_assign(prev, geo, steps=2), 2600, ripple_delays(prev, mode='spiral', step_ms=120), colors=palette)
```

### mirror-cross  ·  `mirror_assign()`

- **category**: composition
- **role fit**: development, climax
- **purpose**: 镜像对穿分配：每架机飞向自己关于构图质心的反射点附近——对称对穿。
- **when to use**: 想要穿越中心的对称大动作、戏剧性交叉时。
- **when NOT**: 不愿处理错峰时（同步对穿必撞）；密集队形（对穿空间不足）。
- **key params**: mirror_assign(prev, geo)。**必须配错峰**：move2/ripple_move 前给 delays（如 ripple_delays 或 delay(i*150)），让各机不同时刻过中心。
- **safety**: 错峰是对穿的安全机制（人类作品的对穿全部错峰）——不要为消碰撞丢掉对穿，要用错峰消碰撞。
- **validation risks**: 同步对穿（delays 全 0）→ 中心碰撞门必炸；错峰不足→碰撞门。
- **combines with**: handwritten-geometry, wave-delays, wave-ripple-move
- **music fit**: 戏剧冲突、强烈交叉、对抗式乐句。

```python
geo = custom_points([...对称目标阵...], n=9)
delays = [i*150 for i in range(9)]  # 错峰过中心
prev = ripple_move(drones, mirror_assign(prev, geo), 2600, delays, colors=palette)
```

### half-swap  ·  `swap_assign()`

- **category**: composition
- **role fit**: development, buildup
- **purpose**: 半场交换分配：左右(axis='x')或前后(axis='y')两半互换——组级换位叙事。
- **when to use**: 两半场整体对调、交错换位时；每半场内部用 best_assign 保路径安全。
- **when NOT**: 需要全队统一动作或精细个体路径时。
- **key params**: swap_assign(prev, geo, axis='x'|'y')。奇数机时中位机守中。
- **safety**: 半场内部 best_assign 保证路径间距；两半交叉穿越仍建议错峰。
- **validation risks**: 两半同时穿越中线→碰撞门；配错峰缓解。
- **combines with**: handwritten-geometry, wave-ripple-move, split-groups
- **music fit**: 换位、对调、交错段。

```python
prev = ripple_move(drones, swap_assign(prev, geo, axis='x'), 2600, ripple_delays(prev, mode='sweep_x', step_ms=130), colors=palette)
```

### identity-keep  ·  `keep_assign()`

- **category**: composition
- **role fit**: any, development
- **purpose**: 身份保持分配：drone i 固定走第 i 个目标，不重排——per-drone 叙事/色彩身份跟踪。
- **when to use**: 需要观众跟踪个体（palette 色彩身份、焦点机连续剧情）时。
- **when NOT**: 需要碰撞最优重排时（用 best_assign/far_assign）。
- **key params**: keep_assign(prev, geo)。交叉风险自行用错峰处理，validator 逐帧兜底。
- **safety**: 不做碰撞优化——必须自己保证 geo[i] 相对 prev[i] 的路径不交叉，或配足够错峰。
- **validation risks**: 目标顺序与起点顺序交叉→碰撞门；需手动错峰或调整 geo 顺序。
- **combines with**: handwritten-geometry, drone-fade
- **music fit**: 个体叙事、色彩身份、焦点跟踪。

```python
palette = [...9 色...]
prev = ripple_move(drones, keep_assign(prev, geo), 2600, [i*120 for i in range(9)], colors=palette)
```


## Composite skill cards

### center-out-climax

- **uses primitives**: `spatial_ranks()`, `ripple_delays()`, `ripple_move()`, `light_wave()`, `flash_group()`
- **category**: motion
- **role fit**: climax, expand
- **music fit**: 高潮爆发、能量峰值、主题宣告。
- **visual effect**: 中心机先动先亮，能量像冲击波向外铺满全场，光波同向扫出，峰值齐闪收束。
- **constraints**: geo 用 far_assign 求大动作；中心向外的 delays 要真的非零（避免环形退化）；峰值后用 flash_group 标点但不黑灯；填满窗口。
- **how to choose**: 段角色为 climax/expand 且音乐有明确爆点时首选。
- **avoid overuse**: 整场只有一个真高潮——不要每段都中心爆发，否则峰值贬值。

```python
geo = custom_points([...大圆环/放射阵...], n=len(drones))
delays = ripple_delays(prev, mode='center_out', step_ms=140)
prev = ripple_move(drones, far_assign(prev, geo, min_path_cm=active_min_path_cm(2600)), 2600, delays, colors=warm, hold_ticks=12, gradient_to=hot)
flash_group(drones, '#ffffff', times=2, on_ms=180)
```

### breathing-transition

- **uses primitives**: `best_assign()`, `fade_group()`, `breathe_group()`
- **category**: lighting
- **role fit**: transition, calm
- **music fit**: 段落之间的换气、情绪转换、能量回落。
- **visual effect**: 队形小幅就近重排到新姿态，灯光呼吸/渐变完成情绪过渡，不抢戏。
- **constraints**: 用 best_assign 求就近小动作；呼吸/渐变嵌进有移动的窗口，别让整段静止；保持亮灯。
- **how to choose**: 两个强段之间需要缓冲、或音乐转句时；只配短窗口(≤8s)或当长段的收尾点缀。
- **avoid overuse**: 过渡太多会让演出拖沓——相邻不超过一次。**不能当长段(≥10s)主体**：它是就近小动作，长段 quality 门要求中位路径≥80cm，呼吸式小动作会被反复打回（用 density-expand-contract / far_assign 做主体，再用它收尾）。

```python
prev = ripple_move(drones, best_assign(prev, geo), 2400, ripple_delays(prev, mode='sweep_x', step_ms=120), colors=palette)
breathe_group(drones, base_color, cycles=1, period_ms=1400)
```

### call-and-response

- **uses primitives**: `split_groups()`, `group_relay()`, `best_assign()`
- **category**: grouping
- **role fit**: buildup, development
- **music fit**: 对答乐句、左右呼应、交替强拍。
- **visual effect**: 左组动、右组亮灯应答，再换手——两组色彩对话，读出问答结构。
- **constraints**: 分组在空间上要可分（left_right/front_back 优先）；**两组的 targets 要在不同区域**（每机飞自己的 targets[i]，gids 只管时序）——别让两组飞向重叠点造成对穿碰撞；两组目标分别 best_assign；总时长=2*flying+gap 填满窗口。
- **how to choose**: 音乐有明显一问一答/对称乐句时。
- **avoid overuse**: 连续多段问答会单调——配合其他母题交替。

```python
gids = split_groups(prev, mode='left_right')
prev = group_relay(drones, best_assign(prev, geo), gids, 2300, colors=('#ff6040','#4060ff'), gap_ms=250)
```

### chain-follow-phrase

- **uses primitives**: `custom_points()`, `follow_chain()`
- **category**: motion
- **role fit**: development, transition
- **music fit**: 流动旋律线、行进、连绵乐句。
- **visual effect**: 全队像一条蛇沿设计路径鱼贯游走，头亮尾随，线条清晰。
- **constraints**: waypoints 写成 custom_points（min_xy_cm 可 55-60）；相距 lag 的波点间距≥51cm（函数自校验）；路径要有叙事方向。
- **how to choose**: 想要单一清晰路径而非整体平移时。
- **avoid overuse**: 蛇形看多会腻——一场一两次为宜。

```python
wps = custom_points([...一条贯穿场地的蛇形折线...], min_xy_cm=60)
prev = follow_chain(drones, wps, 700, lag_hops=1, colors=palette)
```

### static-pose-active-light

- **uses primitives**: `custom_points()`, `best_assign()`, `light_wave()`, `breathe_group()`
- **category**: lighting
- **role fit**: calm, opening, closure
- **music fit**: 长音、留白、造型展示、署名定格。
- **visual effect**: 队形飞到可读造型后保持静止展示，靠光波/呼吸维持视觉活性——亮灯定格是预算的一等公民。
- **constraints**: 造型前要有真实移动到位；定格期必须亮灯（light_wave/breathe_group），黑灯静止会被低活动门打回；定格 0.8-2s。
- **how to choose**: 需要让观众读图、音乐留白时。
- **avoid overuse**: 定格太久或太频繁→低活动门 + 拖沓。

```python
prev = ripple_move(drones, best_assign(prev, geo), 2600, ripple_delays(prev, mode='center_out'), colors=palette)
light_wave(drones, ripple_delays(prev, mode='spiral', step_ms=120), palette, hold_ticks=8, gradient_to=cool)
```

### ending-flash-fade-closure

- **uses primitives**: `flash_group()`, `fade_group()`
- **category**: lighting
- **role fit**: closure
- **music fit**: 尾声、最终标点、谢幕。
- **visual effect**: 署名造型上齐闪宣告，再整体渐隐收束——干净的结束语气。
- **constraints**: 用在 S06 收尾造型到位后；flash 结束自动回亮，再 fade 到暗；LAND 段不编舞（收束动作放 S06）。
- **how to choose**: S06 尾声段的标准收尾。
- **avoid overuse**: 只属于真正的结尾——别在中段用。

```python
flash_group(drones, '#ffffff', times=3, on_ms=200, alt_color='#ffd040')
fade_group(drones, '#ffffff', '#101030', duration_ms=1600)
```

### density-expand-contract

- **uses primitives**: `far_assign()`, `best_assign()`, `ripple_move()`, `breathe_group()`
- **category**: motion
- **role fit**: expand, climax, development
- **music fit**: 能量起伏、张弛对比、呼吸式结构。
- **visual effect**: 队形大幅铺开到边界再收拢回团，密度一张一弛，制造呼吸感的空间叙事。
- **constraints**: 展开用 far_assign 求大路径，收拢用 best_assign 求就近；展/收各占一个 keyframe 填满窗口；高度分层。
- **how to choose**: 音乐有明显张弛/强弱交替时。
- **avoid overuse**: 反复扩张收拢会机械——配合换轮廓避免重复。

```python
prev = ripple_move(drones, far_assign(prev, wide_geo, min_path_cm=active_min_path_cm(2800)), 2800, ripple_delays(prev, mode='center_out', step_ms=140), colors=palette)
prev = ripple_move(drones, best_assign(prev, tight_geo), 2600, ripple_delays(prev, mode='center_out', reverse=True, step_ms=140), colors=palette)
```

### beat-aligned-light-wave

- **uses primitives**: `beat_ms()`, `ripple_delays()`, `light_wave()`
- **category**: lighting
- **role fit**: buildup, development, any
- **music fit**: 节奏明确、律动强的段落。
- **visual effect**: 光波的波间步长贴到节拍，光沿队形逐拍扫过，与鼓点同步。
- **constraints**: step_ms 用 beat_ms(bpm, 0.5或1)；需在有移动的段内做定格点缀，别单独撑满整段。
- **how to choose**: 想让灯光咬住节拍、强化律动时。
- **avoid overuse**: 整段只跟拍闪光而不动→低活动门。

```python
step = beat_ms(bpm, 0.5)
light_wave(drones, ripple_delays(prev, mode='sweep_x', step_ms=step), palette, hold_ticks=6, gradient_to=cool)
```

### orbit-rotate-phrase

- **uses primitives**: `rotate_assign()`, `ripple_delays()`, `ripple_move()`
- **category**: motion
- **role fit**: development, transition, expand
- **music fit**: 回旋、盘旋、连绵的圆周律动。
- **visual effect**: 整个对称队形像星盘一样刚体转动，机间距离恒定、丝滑无碰撞，是大动作里最安全的一种。
- **constraints**: geo 必须与 prev 同构（同半径/对称环）；steps 控转动量；配 spiral delays 让转动更顺；加 Z 个性避免固定高度退化。
- **how to choose**: 已是圆环/对称队形、想要大幅但绝对安全的整体运动时。
- **avoid overuse**: 连续旋转会单调——配合换半径或换轮廓。

```python
geo = custom_points([(280+170*cos(2*pi*i/9), 280+170*sin(2*pi*i/9), 150+30*sin(i)) for i in range(9)], n=9)
prev = ripple_move(drones, rotate_assign(prev, geo, steps=2), 2600, ripple_delays(prev, mode='spiral', step_ms=120), colors=palette, gradient_to=cool)
```

### mirror-cross-phrase

- **uses primitives**: `mirror_assign()`, `ripple_delays()`, `ripple_move()`, `split_groups()`
- **category**: motion
- **role fit**: development, climax
- **music fit**: 戏剧冲突、强烈交叉、对抗式高潮。
- **visual effect**: 两侧无人机依次穿越中心交叉而过，错峰让它们在不同时刻过心——惊险而安全的对穿。
- **constraints**: **必须错峰**（mirror_assign 配非零 delays）；对穿空间要够（密集队形不要对穿）；错峰是安全机制不是可选项。
- **how to choose**: 想要穿越中心的对称张力、戏剧性交叉时。
- **avoid overuse**: 对穿很抓眼但用多了廉价——一场一两次。

```python
geo = custom_points([...关于质心对称的目标阵...], n=9)
delays = [i*150 for i in range(9)]  # 错峰过中心
prev = ripple_move(drones, mirror_assign(prev, geo), 2600, delays, colors=palette)
```

### center-migration

- **uses primitives**: `custom_points()`, `far_assign()`, `ripple_move()`, `light_wave()`
- **category**: motion
- **role fit**: development, expand
- **music fit**: 启程/抵达/迁徙叙事、空间方向感强的段落。
- **visual effect**: 整个队形的质心从场地一侧迁移到另一侧（左→右/聚→散），是方向性空间叙事的核心手法。
- **constraints**: 新 geo 的质心明显偏离 prev 质心（迁移≥120cm 才读得出）；用 far_assign 求大位移；保持队形可读不要散成噪声；光波同向扫强化方向。
- **how to choose**: 音乐有明确的'出发→抵达'或方向推进时（人类作品的'新征程'叙事）。
- **avoid overuse**: 质心来回迁移会晕——一个方向走到底，回归留给后段。

```python
geo = custom_points([...质心右移到 (400,280) 的造型...], n=9)
prev = ripple_move(drones, far_assign(prev, geo, min_path_cm=active_min_path_cm(2800)), 2800, ripple_delays(prev, mode='sweep_x', step_ms=140), colors=palette)
light_wave(drones, ripple_delays(prev, mode='sweep_x', step_ms=120), palette, hold_ticks=6)
```

## User-defined skills (Stage 4)

You can add your own skills without touching `core/skills.py`. Drop a JSON file
and the agent picks them up in the menu, the planner catalog, and this doc:

```json
{
  "primitives": [],
  "composites": [
    {
      "name": "my-spiral-bloom",
      "uses": ["spatial_ranks", "ripple_delays", "ripple_move", "light_wave"],
      "category": "motion",
      "role_fit": ["expand", "climax"],
      "music_fit": "绽放式渐强、华彩展开",
      "visual_effect": "螺旋波次从中心层层绽放，光波同步扫出",
      "constraints": "geo 用 far_assign；spiral delays 非零；填满窗口；Z 分层",
      "how_to_choose": "华彩/绽放段且已是中心聚拢队形时",
      "avoid_overuse": "一场一次",
      "example": "prev = ripple_move(drones, far_assign(prev, geo, min_path_cm=active_min_path_cm(2800)), 2800, ripple_delays(prev, mode='spiral', step_ms=130), colors=palette, gradient_to=cool)"
    }
  ]
}
```

Rules enforced by the loader (`core.skills.load_user_skills` /
`register_user_skills`):

- **Composites** may only `uses` primitive functions that already exist in
  `function.py` — you compose existing kernel pieces, you do not add code.
- **User primitives** may only wrap a function already exported by
  `function.py` (`__all__`). User skills are pure metadata: they cannot
  introduce executables, cannot weaken gates, cannot run arbitrary code.
- Every entry is validated (required fields, valid `category` / `role_fit`,
  known primitives, unique name); a malformed file registers **nothing**
  (atomic), so the built-in catalog is never half-broken.

Place the file at `tools/choreo_agent/user_skills.json` (global) or
`<project>/user_skills.json` (per-project); `run_pipeline.py` loads both at
startup. See `user_skills.example.json` for a template.

## Distilling human works (Stage 3)

`core/distill.py` reads a finished work's trajectory (a `.fii` directory or any
project's `output/`) and extracts a **choreography signature** → **technique
labels** (e.g. *light-clock lighting*, *settled-with-lit-holds*,
*center-migration arc*, *within-frame mirror symmetry*, *layered height*). Run:

```bash
python -m core.distill <fii_or_output_dir> "<name>"
```

The output is a *profile*: principles and measured parameters, **not**
coordinates. A human reviews the profile and curates reusable principle-skills
from it — we never replay a human work's point tables. This automates the
hand-distillation in `doc/human_choreography_distillation.md`.

## Future direction (out of scope for the internal stages)

The internal skill system is the foundation, not the endpoint. The roadmap:

1. **(done)** Internal skillization of `function.py` primitives.
2. **(done)** Build and harden higher-level composite choreography skills.
3. **(done)** Distill human-designed works into reusable principle-skills.
4. **(done)** Support user-defined or user-composed skills.
5. Only after the internal skill system is mature, expose the whole Pyfii
   choreography agent/environment as a tool or skill for external coding agents
   such as Claude Code, Codex, OpenClaw, or Cursor.

External-agent integration is explicitly **not** implemented here. The priority
is first making Pyfii's internal choreography skills explicit, reusable,
documented, and reliably usable by the existing internal AI choreography agent.
