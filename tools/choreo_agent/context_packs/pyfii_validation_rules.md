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
| Time arrangement error | intime | 推后 intime，确保段间 >0.5s |
| ValueError: invalid literal | read_fii | 坐标 int(round(x)) |
| distance between | show | 增间距或提搜索权重 |
| action isn't completed | show | 提速或加delay |
