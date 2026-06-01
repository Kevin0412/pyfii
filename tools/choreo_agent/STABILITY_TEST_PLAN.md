# Choreo Agent Stability Test Plan

目标：验证 agent 能从空模板 fresh run 到完整 LAND，而不是验证某个旧项目能被局部续跑。

## 已发现并修复的测试前缺陷

1. 旧 pipeline 固定 `S02-S06+LAND`，无法覆盖动态追加 `S07/S08`。
2. 旧 pipeline 失败后会 force advance / human override，稳定性数据会被污染。
3. 旧 hybrid pipeline 会拼接手工 fallback 段，不属于 agent 能力。
4. DeepSeek 提议把 `S07/S08` 写死进模板，这是错误方向；追加段必须由 session 在 LAND 前按实际 motion end 动态插入。
5. 最小 TUI 曾直接改 `state.json` 锁段/跳段，已改为调用 `Session.approve_and_lock()`，并禁止直接跳段。

## 测试前置条件

- 工作区使用最新提交后的代码。
- `project_template` 只能包含 `S01-S06 + LAND`，不得静态预置 `S07/S08`。
- 使用 `tools/choreo_agent/run_pipeline.py` 创建 fresh project 并跑完整流程。
- 每次测试必须保留：
  - `agent_interaction.log`
  - `state.json`
  - `scripts/design.py`
  - `stability_result.json`
  - 如完整 LAND，导出 `output/*.fii` 和验收视频

## 推荐命令

```bash
python tools/choreo_agent/run_pipeline.py \
  --fresh-name stability_ds_01 \
  --provider deepseek_pro \
  --max-cycles-per-segment 3 \
  --max-attempts-per-cycle 5

python tools/choreo_agent/run_pipeline.py \
  --fresh-name stability_mi_01 \
  --provider mimo \
  --max-cycles-per-segment 3 \
  --max-attempts-per-cycle 5
```

如果需要复测，创建新的 `--fresh-name`。不要覆盖旧 run。

## 测试矩阵

| Model | Runs | Requirement |
| --- | ---: | --- |
| `deepseek_pro` | 3 | 每轮从 S01 跑到 LAND 或明确失败 |
| `mimo` | 3 | 每轮从 S01 跑到 LAND 或明确失败 |

若 API/网络失败，记录为 `api_network`，不要归咎于编舞逻辑。

## 单轮通过标准

- `current_segment is None`
- `locked_segment_ids` 包含从 `S01` 到 `LAND` 的完整序列；如果有 `S07/S08`，它们必须是在 LAND 前动态插入。
- 最终验证：
  - `compile_ok=True`
  - `run_ok=True`
  - `read_fii_ok=True`
  - `distance_warnings=0`
  - `action_warnings=0`
  - `minD > 51cm`
- LAND 段必须是 `auto_init` + 全机短灯光 + `d.land()`；不得用 `move2` 凑动作。
- 动态窗口通过后，`state.json` 与 `design.py` docstring 必须一致。

## 记录字段

每轮记录：

- `run_id`
- `provider`
- `completed`
- `locked_segment_ids`
- 每段 attempts / cycles
- 每段最终 validation：
  - `dist`
  - `act`
  - `minD`
  - `motion`
  - `effective`
  - `motion_quality_ok`
  - `degradation_ok`
  - `code_quality_ok`
- 是否动态追加 `S07/S08`
- 是否生成视频
- 失败类别

## 失败分类

- `api_network`
- `empty_or_unwritten`
- `compile`
- `code_quality`
- `runtime_or_read`
- `action_incomplete`
- `collision`
- `hover_or_low_activity`
- `motion_quality`
- `degradation`
- `lock_failed`
- `docstring_state_mismatch`
- `land_protocol`

## 稳定性判断

- 完整 LAND 成功率是主指标，不只看 S02/S03。
- S02/S03 是早期稳定性哨兵：已有 7 坐标后仍频繁失败，说明上下文/续写策略有问题。
- 动作未完成是硬失败，不能人工放过。
- 连续两段相同退化是硬失败；单段轻微退化可以记录但不一定阻断。
- 如果同类失败在同一模型多次出现，才修改 prompt/validator/session，并重新 fresh run 复测。

## 报告格式

1. DeepSeek 三轮表格
2. MIMO 三轮表格
3. 模型横向比较：
   - 完整 LAND 成功率
   - 平均 attempts
   - 常见失败类别
   - 视觉退化倾向
4. 系统修改记录：
   - 修改点
   - 修改原因
   - 修改后 fresh-run 结果
5. 下一步建议
