# Choreo Agent 完整方案

> 暂时不拆仓库，直接在 Pyfii 仓库内做一个 `tools/choreo_agent/` TUI 编舞 agent
> 核心重点："逐段生成 + 人类确认 + Pyfii 自定义库上下文包 + 安全修改 .py + checkpoint/resume"

## 当前进度

| Phase | 内容 | 状态 |
|-------|------|------|
| 0 | context_packs (8个) | ✅ |
| 1 | core state system | ✅ |
| 2 | script_editor | ✅ |
| 3 | validator (四层+hover+dense_collision+repair_feedback) | ✅ |
| 4 | TUI | CLI REPL 可用，Textual 待做 |
| 5 | LLM 接入 (DeepSeek / custom_gpt) | ✅ |
| 6 | 自动修复闭环 | ✅ generate_until_safe_with_llm |
| 7 | 试跑 cannon_in_d | S01 locked, S02 验证中 |

## 待做
- Textual TUI
- 音乐分析自动化 (BPM/能量/段落检测)
- Safe/Fast 模式切换
- best_assign 结果自动注入到 prompt feedback
- S02-S08 全部通过
- Context 文件自动更新 (design_memory.md, handoff.md)
- 退化检测集成到验证流水线

---

# 1. 项目定位

Pyfii TUI 编舞工作台 = 常驻进程 + 当前段上下文内存 + 人类多轮反馈 + AI 修改当前段 + Pyfii 验证闭环 + 视频验收 + 段落锁定 + 退出恢复

核心目标：音乐分段确认 → 逐段生成 → 当前段反复修改 → warning=0 → 导出视频 → 人类验收 → 锁定 → 下一段

# 2. 仓库内目录设计

```
tools/choreo_agent/
  main.py
  tui/           # Textual TUI
  core/          # 核心模块(已实现7个)
  context_packs/ # 8个文档
  project_template/
agent_projects/
  cannon_in_d/   # 测试项目
```

# 3. 总体工作流

## 3.1 初始化: 创建项目 → 复制模板 → 导入音乐 → 初始化state
## 3.2 音乐分析: AI分析 → 输出music_analysis.json → TUI展示 → 人类确认
## 3.3 当前段生成+自动修复: 构造prompt → 调用LLM → 提取代码 → 写入marker → compile → run → read_fii → 密采样碰撞检测 → 悬停检测 → 失败则格式化repair_feedback回灌LLM (最多5轮) → 通过或放弃
## 3.4 人类反馈: 只能改当前段，不能改locked段；可在 g 命令后追加自定义反馈
## 3.5 锁定: locked=true → 写segment_card → 更新memory → checkpoint → 下一段
## 3.6 状态同步: `sync` 命令从 design.py marker 恢复 locked/current 状态

# 4. TUI (Textual待实现)

主界面包含: 项目信息、当前段面板、验证面板、操作按钮(G/V/E/A/R/D/M/S/Q)
内存上下文: ActiveSegmentContext 保存当前段所有状态

# 5. Safe / Fast 模式

- Safe: 音乐分析+意图+视频+锁定 全部人类确认
- Fast: AI自动推进，但验证不跳过，修改locked段必须问人
- 永远不能自动: 改locked段、改结束位置、删checkpoint

# 6. Context Packs (8个, 已就绪)

pyfii_api_minimal / coding_rules / segment_protocol / anti_patterns / best_assign / light_patterns / validation_rules / agent_coding_style

# 7. Prompt Builder (已实现)

8个context_packs全量加载为system prompt，user prompt包含音乐+意图+prev+feedback+design.py参考
LLM输出自动提取: 支持fenced markdown代码块 (```python ... ```)

# 8. Script Editor (已实现)

marker机制: # === PYFII_AGENT_SEGMENT_START id=S01 locked=false ===
操作: replace_active_segment, lock_segment, locked hash检查
修改前必须checkpoint

# 9. Validator (已实现)

四层: 语法(compile) → 执行(run) → 读回(read_fii) → 验收(show)
+ 密采样碰撞检测 (60fps逐帧, 输出collision_intervals)
+ 悬停检测 (threshold=0.2cm, 持续>2s)
+ repair_feedback(): 验证失败自动格式化为LLM修复提示
+ compute_assign_feedback(): 离线计算best_assign排列建议
+ 输出目录新鲜度检查 (_output_updated)
+ PYFII_AGENT_PYTHON 环境变量支持

# 10. Context 文件设计

- design_memory.md: 全局风格、人类偏好、已用视觉语言、被否决方案
- handoff.md: 当前状态、锁定段、视频路径、下次步骤
- segment_cards/Sxx.md: 每段的音乐、意图、反馈历史、验证结果、出口状态

# 11. 开发阶段

Phase 0-6 已完成，Phase 7(多段试跑 cannon_in_d) 进行中

# 12-13. Token预算

- MVP: 300-600万 tokens
- 可用版: 800-1500万
- 成熟版: 2000-5000万
- 每首歌使用: 100-800万

# 14. 编码风格 (两套)

1. tools/choreo_agent/: 工程化, pathlib, dataclass, 类型标注
2. scripts/design.py: marker清晰, 禁止极限压缩, 人类可读

详见 context_packs/agent_coding_style.md
