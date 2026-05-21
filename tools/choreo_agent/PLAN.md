# Choreo Agent 方案

## 当前进度

| Phase | 内容 | 状态 |
|-------|------|------|
| 0 | context_packs (8个) | ✅ 完成 |
| 1 | core state system | ✅ 完成 |
| 2 | script_editor (marker+lock+hash) | ✅ 完成 |
| 3 | validator (四层验证+hover+assign_feedback) | ✅ 完成 |
| 4 | TUI | ⏳ CLI原型可用，Textual待做 |
| 5 | LLM 接入 (deepseek-v4-flash) | ✅ 完成 |
| 6 | 真实项目试跑 | ⏳ S01通过，S02待注入 |

## 待做

### 核心缺失
- **Safe/Fast 模式切换** (approval.py)
- **Context 文件自动更新** (design_memory.md, handoff.md)
- **音乐分析自动化** (music_analysis.json 生成)
- **视频导出器** (video_exporter.py)
- **Segment Cards 生成** (segment_cards/Sxx.md)
- **退化检测** (detect_degradation 集成)
- **恢复机制** (recovery.py, 从 handoff 恢复)

### TUI (Textual)
- dashboard, segment_workspace, validation_panel, diff_panel

### 生成闭环
- best_assign 自动注入 → validator.compute_assign_feedback 已就绪
- 多段自动推进 (S02-S08)
- hover 检测 fix

## 关键决策

1. **best_assign 离线工具**: AI 不运行时调用，validator bridge 计算 perm 反馈
2. **marker 机制**: 安全替换，locked hash 检查
3. **7 context_packs 全量加载**: 每次调用上下文一致
4. **起飞由 agent 定义**: 不硬编码模板
5. **VelXY(speed, acc)**: 不是 min/max，VelXY/VelZ 必须一致

## 编码风格约束

两套独立风格，不能混用：

1. **`tools/choreo_agent/` 工具代码** → 加载 `agent_coding_style.md`
   - 工程化、可维护、pathlib、dataclass、类型标注
   - 单文件200-400行，单函数20-80行
   - TUI只展示不写业务逻辑

2. **`scripts/design.py` 编舞脚本** → 加载 `pyfii_*` context packs
   - 结构稳定、marker清晰、局部可替换
   - 禁止DeepSeek式极限压缩（一行多语句、分号连写）
   - 每段必须有marker、必须更新prev

详见: `context_packs/agent_coding_style.md`
