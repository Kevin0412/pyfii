# Choreo Agent 后续计划

> 状态：2026-07-14 路线图。原先“本周重跑 S02-S06、S04+ 手工 fallback、修复无加速度视频”的计划已经完成或被当前架构取代；详细实验记录见 `tools/choreo_agent/PLAN.md` 和 `tools/choreo_agent/STABILITY_TEST_PLAN.md`。

## 已完成的基础能力

- [x] 分段生成、验证、锁定、checkpoint/resume 和自动修复闭环。
- [x] DeepSeek/custom provider 接入及本地模型测试路径。
- [x] 物理安全、演出完整性、审美建议三层门和交互 override。
- [x] 导演反馈 grounding、显式坐标可行性预检和失败解释。
- [x] 2D/3D 默认加速度视频验收。
- [x] 双模型矩阵、导演指令用例和调用次数保险丝。
- [x] 基础车道、刚性圆环、低活动和 composition 检测。

## 当前优先事项

- [ ] 完成 Textual TUI；目前只有三面板最小壳和 CLI REPL。
- [ ] 自动生成 BPM、能量、段落和 cue，接入 `music_brief`，减少人工准备音乐分析。
- [ ] 把 `best_assign` 和 planning tools 的候选结果更细粒度地反馈给规划阶段。
- [ ] 自动维护 `design_memory.md`、`handoff.md` 和 segment cards。
- [ ] 扩展跨段重复/退化检测，不只判断单段车道或圆环。
- [ ] 统一 planning prompt 的字面 keyframe 合同与数据化 requirements，避免 prompt 比验证门更严格。
- [ ] 专项修复压缩质量窗口后下一段名义时间窗未同步的问题；行为改动后必须重新跑稳定性矩阵。

## 持续验证

- [ ] 对 DeepSeek 与对照模型持续重复运行 `run_matrix.py`，记录完成率、轮次、成本和失败类别。
- [ ] 扩展机数、音乐主题和导演指令覆盖，避免只在 7 机卡农样本上成立。
- [ ] 对模型黑洞、组合指令上限和人工改码后的状态恢复保留回归用例。
- [ ] 所有功能变更继续要求 Tier 0 不退化，并通过最终 2D/3D 人工观感验收。
