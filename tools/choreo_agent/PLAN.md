# Choreo Agent 完整方案

> 暂时不拆仓库，直接在 Pyfii 仓库内做一个 `tools/choreo_agent/` TUI 编舞 agent
> 核心重点："逐段生成 + 人类确认 + Pyfii 自定义库上下文包 + 安全修改 .py + checkpoint/resume"

## 当前进度

| Phase | 内容 | 状态 |
|-------|------|------|
| 0 | context_packs (含蒸馏编舞样例) | ✅ |
| 1 | core state system | ✅ |
| 2 | script_editor | ✅ |
| 3 | validator (四层+hover+dense_collision+motion/degradation+repair_feedback) | ✅ |
| 4 | TUI | CLI REPL 可用，Textual 待做 |
| 5 | LLM 接入 (DeepSeek / custom_gpt) | ✅ |
| 6 | 自动修复闭环 | ✅ generate_until_safe_with_llm |
| 7 | 试跑 cannon_in_d | ✅ DeepSeek `S01-S08 + LAND` 全流程锁定，已生成视频验收文件 |
| 8 | agent-side planning tools | ✅ timeline_cues / assign_targets / budget_layers |

## 待做
- Textual TUI
- 音乐分析自动化 (BPM/能量/段落检测)
- Safe/Fast 模式切换 ✅ 已有 manual/fast CLI；仍需更好 UI
- best_assign / planning_tools 的候选结果更细粒度注入到 prompt feedback
- 双模型多次生成稳定性测试：DeepSeek / MIMO 各多次 fresh run，统计 S02、S03、LAND 成功率和失败原因
- Context 文件自动更新 (design_memory.md, handoff.md, segment_cards)
- 退化检测集成到验证流水线 ✅ 已有基础车道/刚性圆检测；仍需跨段重复检测

---

# 1. 项目定位

Pyfii TUI 编舞工作台 = 常驻进程 + 当前段上下文内存 + 人类多轮反馈 + AI 修改当前段 + Pyfii 验证闭环 + 视频验收 + 段落锁定 + 退出恢复

核心目标：音乐分段确认 → 逐段生成 → 当前段反复修改 → warning=0 → 导出视频 → 人类验收 → 锁定 → 下一段

# 2. 仓库内目录设计

```
tools/choreo_agent/
  main.py
  tui/           # Textual TUI
  core/          # 核心模块: state/session/editor/validator/llm/motion/planning
  context_packs/ # 9个静态文档 + system prompt 动态工具说明
  project_template/
agent_projects/
  cannon_in_d/   # 测试项目
```

# 3. 总体工作流

## 3.1 初始化: 创建项目 → 复制模板 → 导入音乐 → 初始化state
## 3.2 音乐分析: AI分析 → 输出music_analysis.json → TUI展示 → 人类确认
## 3.3 当前段生成+自动修复: 构造prompt → LLM先做段落规划层(geometry/keyframe/height/speed budget) → 输出final当前段代码 → 提取代码 → 写入marker → compile → run → read_fii → 密采样碰撞检测 → 当前段运动包络+整体悬停硬检测 → 失败则格式化repair_feedback回灌LLM (最多5轮) → 通过或放弃
## 3.4 人类反馈: 只能改当前段，不能改locked段；可在 g 命令后追加自定义反馈
## 3.5 锁定: locked=true → 写segment_card → 更新memory → checkpoint → 下一段
## 3.6 状态同步: `sync` 命令从 design.py marker 恢复 locked/current 状态

# 4. TUI (Textual待实现)

主界面包含: 项目信息、当前段面板、验证面板、操作按钮(G/V/E/A/R/D/M/S/Q)
内存上下文: ActiveSegmentContext 保存当前段所有状态

# 5. Manual / Fast 模式

- Manual: 音乐分析+意图+视频+锁定 全部人类确认；人工 `a` 最高优先级，并记录 override
- Fast: 验证硬门通过后进入 AI 自审流程，由 AI 判断是否 lock 并进入下一段；验证不跳过，AI 自审不通过则停在当前段
- 永远不能自动: 改locked段、改结束位置、删checkpoint

# 6. Context Packs (已就绪)

pyfii_api_minimal / coding_rules / segment_protocol / anti_patterns / best_assign / light_patterns / validation_rules / design_patterns / agent_coding_style

# 7. Prompt Builder (已实现)

9个context_packs全量加载为system prompt，user prompt包含音乐+意图+prev+feedback+design.py参考
system prompt 还会追加 motion_math / planning_tools 的动态说明，要求 agent 在规划层使用工具，在 final `design.py` 中只留下硬编码表。
LLM输出自动提取: 支持fenced markdown代码块 (```python ... ```)

## 7.1 Agent-side Planning Layer (已实现)

目标：把"理解音乐/几何/高度/速度"放在 agent 规划层完成，避免 final `design.py` 里塞入 `best_assign()`、飞行时间公式、排列搜索或通用 helper。

已提供：

- `motion_math.py`: 3D distance、梯形/三角速度曲线、速度/加速度/灯光/等待预算。
- `best_assign.py`: 离线路径分配搜索，结果硬编码进当前段。
- `planning_tools.py`: `timeline_cues()`、`assign_targets()`、`budget_layer()`、`budget_layers()`，把 keyframe interval 转成每机 target/speed/accel/light_ticks/delay_ms 表。

约束：

- agent 可以在草图阶段写临时 helper 来生成候选几何、排除退化形态、估算预算。
- final segment 只能包含 concrete tables 和 PyFii 命令链。
- validator 会拒绝 `best_assign`、`dist3`、`flight_time_ms`、`speed_for_interval`、`move_interval`、`timeline_cues`、`budget_layers` 等规划层 helper 泄漏到 final `design.py`。

# 8. Script Editor (已实现)

marker机制: # === PYFII_AGENT_SEGMENT_START id=S01 locked=false ===
操作: replace_active_segment, lock_segment, locked hash检查
修改前必须checkpoint

# 9. Validator (已实现)

四层: 语法(compile) → 执行(run) → 读回(read_fii) → 验收(show)
+ 密采样碰撞检测 (60fps逐帧, 输出collision_intervals)
+ 当前正式编舞段运动包络检测 (start+1s 前开始, end-1s 后收束; 起飞/降落不计入)
+ 当前正式编舞段整体悬停硬检测 (threshold=0.2cm/frame, 持续>=1s; 起飞/降落不计入)
+ repair_feedback(): 验证失败自动格式化为LLM修复提示
+ compute_assign_feedback(): 离线计算best_assign排列建议
+ 禁止 agent-side helper 泄漏到 final segment
+ 输出目录新鲜度检查 (_output_updated)
+ PYFII_AGENT_PYTHON 环境变量支持

# 10. Context 文件设计

- design_memory.md: 全局风格、人类偏好、已用视觉语言、被否决方案
- handoff.md: 当前状态、锁定段、视频路径、下次步骤
- segment_cards/Sxx.md: 每段的音乐、意图、反馈历史、验证结果、出口状态

# 11. 开发阶段

Phase 0-8 已完成第一轮闭环。`codex_operate3_deepseek_20260601_010516` 已从
S01 推进到 LAND，并通过 `dist=0 / act=0 / minD=70.7cm` 的最终回放检查。

# 11.1 阶段性实测结论

- Agent 可以从空模板逐段生成、验证、锁定，并在压缩时间线不足 60s 时自动追加 S07/S08。
- `auto_init()` 会压缩段尾空白；因此实际质量窗口可能从 nominal window 平移到更晚/更短的位置。系统会把通过验证后的有效窗口写回 `state.json`，并同步更新 `design.py` 函数 docstring，例如 `S06: 58-63s` 会修正为实际窗口。
- LAND 必须走专用降落协议：不再写 keyframe / move2，只做短灯光提示和 `d.land()`。
- 4-5s 的追加正式段不能靠拉长 `flying_ms` 凑时长；如果路径太短，底层最小速度会提前完成。短段需要边界/角点目标和 `far_assign(..., min_path_cm=220)`，让多数无人机有足够长的真实运动。
- 验收视频已能由 `pf.show(..., save=...)` 导出；必要时再用 ffmpeg 转 H.264 兼容版。

# 11.2 下一阶段：稳定性测试

交给 deepseek-tui 的下一步不是继续改单次样例，而是做批量 fresh-run 稳定性：

- 每次从 project_template 新建项目，不复用旧 run。
- DeepSeek/MIMO 分别跑多次，至少记录 `S01/S02/S03/最后 LAND` 成功率。
- 失败必须归因：API/网络、preflight、碰撞、动作未完成、低活动/悬停、退化重复、LAND 协议错误、docstring/state 不一致。
- 多次失败才改系统提示或验证器；不要用手工编辑 `design.py` 代替 agent 能力。

# 12-13. Token预算

- MVP: 300-600万 tokens
- 可用版: 800-1500万
- 成熟版: 2000-5000万
- 每首歌使用: 100-800万

# 14. 编码风格 (两套)

1. tools/choreo_agent/: 工程化, pathlib, dataclass, 类型标注
2. scripts/design.py: marker清晰, 禁止极限压缩, 人类可读

详见 context_packs/agent_coding_style.md
