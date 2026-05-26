# Validation Rules

## 验证四层

每次生成/修改后必须通过四层验证：

```text
1. 语法层: compile(code)
2. 执行层: run script → check exit code
3. 读回层: pf.read_fii → check ValueError
4. 验收层: pf.show(show=False) → capture warnings
```

## 验收标准

```python
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    pf.show(data, t0, [MUSIC_PATH], field=field, device=dev, max_fps=60, show=False)

dist_w = [x for x in caught if 'distance between' in str(x.message)]
act_w  = [x for x in caught if 'completed' in str(x.message)]

assert len(dist_w) == 0, f"distance warnings: {len(dist_w)}"
assert len(act_w) == 0,  f"action warnings: {len(act_w)}"
```

## 额外检查

```python
# 全场覆盖
all_x = [p[1] for d in data for p in d if p[1] > 0]
all_y = [p[2] for d in data for p in d if p[1] > 0]
xy_span = (max(all_x)-min(all_x), max(all_y)-min(all_y))
# 期望 > (350, 350)

# 最小距离
md = 9999
for t in range(0, min(len(d) for d in data), 60):
    ...
# 期望 > 51cm
```

## 连贯性硬门

正式编舞段中，全队整体悬停超过 1 秒视为验证失败，不能进入下一步。起飞和降落段不计入这个审美硬门，但仍要通过安全和执行验证。灯光可以按 beat 闪烁，但不能替代运动连续性。

```text
global_hover_segments must be empty
max_global_hover <= 1.0s
low_activity_segments must be empty
effective_motion_end > segment_end - 1.0s
```

修复原则：

- 删除连续 `delay()` / 纯灯光空转。
- 让至少一组无人机在任意 1 秒窗口内有可见 `move2()` 或 Z 变化；单机慢挪、小幅 Z 抖动不算有效群体运动。
- 如果音乐需要呼吸停顿，把全体静止压到 0.8 秒以内，并用分组错峰承接。

当前段还有运动包络约束：如果段落规划为 `5-13s`，明显运动必须在 `6.0s` 前开始，并在 `12.0s` 后、`13.0s` 前完成收束。通用形式是：

```text
motion_start < segment_start + 1.0s
motion_end   > segment_end - 1.0s
effective_motion_start < segment_start + 1.0s
effective_motion_end   > segment_end - 1.0s
```

如果 motion_end 明显早于 `segment_end - 1s`，通常不是视觉问题，而是时间线写法问题：

- Python 循环不是全局时间轴；每架机的命令链可能已经在前半段执行完。
- `move2()` 不推进时间；必须用后续短灯光/`delay()` 给这次移动留执行时间，再进入下一个 `move2()`。
- 合理的 `delay()` 是某次移动的执行预算；不合理的是没有运动覆盖的长时间填尾。
- 修复时应重排每架机的 keyframe interval，按距离选择速度/加速度，让真实 `move2()` / Z/XY 变化持续覆盖到段尾。
- 最后一段收束移动必须在 `segment_end - 1s` 后仍在执行，并在 `segment_end` 前完成。
- 段尾动作必须是有效群体运动：至少一组无人机共同参与，有足够位移；不能靠一两架慢挪、10-20cm 小波动或错峰 delay 把 `motion_end` 拖到段尾。

## 有效动作质量门

连续性不是小范围抖动。validator 会在正式段内统计每架机路径长度、最大离入口位移、有效运动无人机数量：

```text
moving_drones: 离入口位置超过 30cm 的无人机数量
median_path_cm: 各机路径长度中位数
median_excursion_cm: 各机最大离入口位移中位数
max_excursion_cm: 全队最大离入口位移
```

修复原则：

- 小 Z/XY 呼吸只能用于衔接，不可作为主体动作。
- 主体动作必须包含跨区域展开、收缩、交换或分组推进。
- 如果为了安全减少交叉，也要用同侧大弧线、扇区展开、前后景深变化扩大有效位移。

## 结构性退化门

validator 会额外检测明显车道退化、刚性圆退化和固定高度退化：

```text
degradation_ok: true
lane_x_locked_drones / lane_y_locked_drones 不应接近全队
circle_like_fraction + order_stable_fraction 不能长期接近 1 且半径变化很小
fixed_height_drones 不应接近全队
window_z_range 应体现 low/mid/high 层次
```

修复原则：

- 不要让多数无人机长期固定 X 或固定 Y 只在一条车道里滑动。
- 不要整段保持同一圆形排序，只靠半径/高度小变化撑时间。
- 如果需要环形意象，必须穿插非圆几何、分组交换、波浪错层或明显的方向性推进。
- 不要全段固定高度；至少一半无人机应有明显 Z 变化，且高度变化要和横向路线合成真实 3D 构图。
- 不要用最后几下小幅 Z 波动凑时长；应重做 keyframe interval 和速度/加速度预算。

## 验证报告格式

```markdown
# Validation S03

compile: OK
run: OK
read_fii: OK

distance warnings: 0
action warnings: 0
minD: 57cm
XY span: 490 x 502
Z range: 80-220
global hover: none
motion envelope: OK
motion quality: OK
degradation: OK

退化检测:
- lane: no
- circle rigid: no
- center anchor: no
```

## 常见验证失败

| 症状 | 位置 | 修复 |
|------|------|------|
| SyntaxError | compile | 检查缩进/括号 |
| ModuleNotFoundError | import | 确保 `sys.path.insert(0,'src')` |
| Out of range | move2 | clamp 坐标 (10,550) / (80,240) |
| Time arrangement error | inittime | 推后 inittime，确保段间 >0.5s |
| ValueError: invalid literal | read_fii | 坐标 int(round(x)) |
| distance between | show | 增间距或提搜索权重 |
| action isn't completed | show | 计算 move2 飞行时间，提速/缩短距离/增加该移动后的执行预算 |
