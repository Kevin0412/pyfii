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
```

修复原则：

- 删除连续 `delay()` / 纯灯光空转。
- 让至少一组无人机在任意 1 秒窗口内有可见 `move2()` 或 Z 变化。
- 如果音乐需要呼吸停顿，把全体静止压到 0.8 秒以内，并用分组错峰承接。

当前段还有运动包络约束：如果段落规划为 `5-13s`，明显运动必须在 `6.0s` 前开始，并在 `12.0s` 后、`13.0s` 前完成收束。通用形式是：

```text
motion_start < segment_start + 1.0s
motion_end   > segment_end - 1.0s
```

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
| action isn't completed | show | 提速或加delay |
