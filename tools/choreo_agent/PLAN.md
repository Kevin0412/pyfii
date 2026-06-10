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
- 双模型多次生成稳定性测试：DeepSeek / MIMO 各多次 fresh run，按 `STABILITY_TEST_PLAN.md` 统计完整 LAND 成功率和失败原因
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

交给 deepseek-tui 的下一步不是继续改单次样例，而是按
`tools/choreo_agent/STABILITY_TEST_PLAN.md` 做批量 fresh-run 稳定性：

- 每次从 project_template 新建项目，不复用旧 run。
- DeepSeek/MIMO 分别跑多次，至少记录 `S01/S02/S03/最后 LAND` 成功率。
- 失败必须归因：API/网络、preflight、碰撞、动作未完成、低活动/悬停、退化重复、LAND 协议错误、docstring/state 不一致。
- 多次失败才改系统提示或验证器；不要用手工编辑 `design.py` 代替 agent 能力。

# 11.3 Prompt 冻结与缓存成本约束

System prompt / context packs / `prompt_builder.py` 会影响 LLM 输入缓存命中。稳定性实测期间，非硬阻断不要调整这些内容；一轮 full-flow 测试中途改 prompt 会使该轮结果作废。

当前计费用于估算 prompt 改动成本：

- 缓存命中输入：0.025 元 / 1M tokens。
- 缓存未命中输入：3 元 / 1M tokens。
- 输出：6 元 / 1M tokens。

因此 prompt 变更主要风险是把可命中的长 system prompt 变成未命中输入；成本差额按 `(未命中输入tokens - 原本命中输入tokens) / 1M * (3 - 0.025)` 估算，输出另按 6 元 / 1M tokens 估算。

修改 prompt 前必须先给出证据：

- 哪个失败日志证明当前 prompt 缺少必要规则。
- 为什么不能通过 validator、preflight、`function.py` 工具、runner 流程或 per-run feedback 解决。
- 改动会增加或减少多少 prompt 字符。
- 是否会导致缓存未命中，按上面单价估算预计额外输入/输出成本。

优先级：

- 小问题优先改本地工具、验证器反馈或单轮 user feedback。
- API 慢、首包慢、timeout 不是削弱或清空 system prompt 的理由；应记录 stream/heartbeat/首包/timeout 状态。
- 禁止为了让某个模型临时通过而删除 S01、S02+、LAND、动态 S07/S08、高度层、短窗口 `far_assign` 等核心契约。

# 11.4 9机编舞质量复盘：模板不是章法

对比 `codex_9drone_flash_full_20260605_1` 与 `stability_flash_9d_v2`：

- 旧版 `codex_9drone_flash_full_20260605_1` 完成 S01-S06+LAND，且观感更好；它没有使用 `geo_*`，也没有使用 `move_group`，而是手写坐标表后展开 per-drone `move2/apply_light/delay`。
- V2 成功把 `geo_*` 降到 0，但大量使用 `move_group/move_group_staggered`，结果从“几何模板退化”变成“执行模板退化”：坐标安全，但节奏、灯光和每架机差异被抹平。
- 结论：`assign` 是安全路径分配层，`custom_points` 是手写坐标安全检查层，`move_group` 只是低级执行兜底。正式编舞的章法必须来自手写非同构几何、多色灯光、per-drone 执行细节和段落角色。

当前规则：

- S01-S06 纯 `move_group/move_group_staggered` 执行会被 composition gate 打回。
- S02-S05 继续禁止 `geo_wide_v/geo_arrow/geo_box/geo_diagonal/geo_wave/geo_grid`。
- 9机正式段默认写手写坐标表 + `best_assign/far_assign` + per-drone loop。
- S04 可使用 4-5 个短 keyframe 做抒情展开；S05 保持高潮幅度和多色灯光；S06 建议两段式收尾（中继点 + 终点），不能单 keyframe 小挪动。

2026-06-10 追加结论：

- 去掉高层模板后，DeepSeek Flash 在 9 机 S01/S02 上会把“手写安全点表”变成超长现场数学推导，甚至重新质疑 `move2/apply_light/delay` 的 API 语义。
- 这不是要恢复 `geo_*` 或 `move_group`。正确补法是在 user prompt / planning pass 提供低层安全坐标骨架：3x3 起飞格、`seed_box/seed_slant/seed_asym` 等 numeric point seeds，让模型少算间距、多做编舞变奏。
- 低层 seed 的定位是“安全坐标脚手架”，不是可连续复用的队形模板。正式段仍要求每个 keyframe 改变中心偏移、Z 层、左右/前后关系、灯光或节奏；连续原样复制 seed 仍视为退化。
- 本轮改动只调整 `prompt_builder.py` 的 user prompt 与 `planning_pass.py` 的规划提示，`build_system_prompt()` 与 context packs 未改，尽量避免大块 system prompt 缓存失效。
- 实测中断记录：`codex_9d_perdrone_flash_20260610_120551` 在 S01 通过后卡在 S02 规划长推理；`codex_9d_seeded_flash_20260610_122132` 证明 per-drone + 3 keyframes 方向成立，但普通 S01 prompt 也需要同样的安全点表纪律。
- `codex_9d_guided_flash_20260610_122658` 证明 S01 可锁定，但 S02 仍会犯两个便宜错误：在 `custom_points` 后调用 `jitter_points` 绕过点表校验，以及把 `min_xy_cm` 擅自提高到 110/120 导致运行期拒绝。因此 preflight 已新增硬门：final segment 禁止 `jitter_points()`，`custom_points(..., min_xy_cm=...)` 若出现必须是字面量 90。

# 12-13. Token预算

- MVP: 300-600万 tokens
- 可用版: 800-1500万
- 成熟版: 2000-5000万
- 每首歌使用: 100-800万

# 14. 编码风格 (两套)

1. tools/choreo_agent/: 工程化, pathlib, dataclass, 类型标注
2. scripts/design.py: marker清晰, 禁止极限压缩, 人类可读

详见 context_packs/agent_coding_style.md
