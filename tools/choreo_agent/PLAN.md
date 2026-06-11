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

# 11.5 计算器路线：去 seed、确定性规划检查、音乐证据与节奏层 (2026-06-10)

实测约束修正（来自人工确认，旧文档数字过保守）：XY 0-560，Z 80-250，XY 间距硬下限 51cm（低于 51 触发 pyfii core 碰撞警告）；90 只是开阔队形默认值。preflight 的 `custom_points(min_xy_cm=...)` 门从“固定 90”放宽为“51-90 字面量”，支持密度呼吸（宽阵 ↔ 密集簇）。

方向调整：coordinate seeds（seed_box/slant/asym）下线。`codex_9drone_flash_full_20260605_1` 证明 DeepSeek 手写粗网格点表 + best_assign/far_assign 即可成段；S02 长推理失败是点表自检压力诱导的。正确做法是给模型计算器，不是给模板：

- `planning_pass.evaluate_plan_safety()`：对 JSON plan 逐 keyframe 确定性计算——点表 min_xy（<51 违规，51-90 标记刻意密集）、坐标越界、best_assign 最优分配后的转场路径最小间距（<55 违规）、speed/accel 下最长飞行时间 vs keyframe 时长。
- `Session._refine_plan_with_checker()`：违规时用小轮次（旧 JSON + 数字报告）让模型只改违规项，最多 2 轮；检查报告同时附在预算表后进入编码阶段。
- 规划/编码 prompt 明确“不要手算两两间距/三角函数，检查器回报精确数字”。

节奏与结构层（蒸馏自 doc/human_choreography_distillation.md）：

- keyframe 合同从均匀切片改为短长对比 phrase（accent 短促 / phrase 延展）。
- `core/music_brief.py`：librosa 分析 tempo/beat/能量曲线/onset 密度/结构边界，项目内缓存 music_brief.json；规划 prompt 注入当前窗口的音乐证据（含 beat ≈ N 个 100ms 灯光 tick 换算）。
- composition gate 新增节奏单调门（S01-S05）：全部 keyframe 同 flying_ms + 整段单色 + 无错峰 = 打回；S06 允许平静署名收束。
- prompt 增加编舞词汇：分组错峰、焦点机对比、中心迁移、密度呼吸、灯光渐变。

门校准锚点：`core/test_gold_run_regression.py` 保证 0605 金标准 run 的全部段落通过 preflight 与结构门；任何拒绝金标准的门都是误校准。

# 11.7 蒸馏复盘 II：dntg 设备清单与系统缺口 (2026-06-10 晚)

重读 `doc/pyfii_script_patterns_human.md`、`doc/deepseek_cannon_reflection.md`、`doc/pyfii_script_patterns_ai.md` 与 dntg 源码，对照当前 agent 能力的设备级缺口：

| dntg/人类设备 | 当前状态 | 优先级 |
|---|---|---|
| 共享轨迹表+每机相位（利萨如 24 点表，各机按索引走同一曲线，连续 keyframe 沿曲线推进） | 缺失——每个 keyframe 独立点表，段内连续性只靠 far_assign | 高：连贯性+复杂度免费 |
| 跨段角色重映射（n2gn/n2sg 字典每段重排，同机不同段不同职责） | 段内有 i%3 分组，跨段无角色轮换 | 高：归入 P1 composition plan 生成 |
| 三通道异频正弦 RGB（R/G/B 用 3:4:2 频率驱动 = 连续色环，非单色渐变） | prompt 只示例单通道亮度渐变 | 中：一行 prompt 词汇 |
| TurnOffAll 负空间（段转折黑场再点亮；无人区"留白→爆发"同理） | agent 从不关灯 | 中：一行 prompt 词汇 |
| 同段每机多步异构路径（边机绕行 ±160、中机下潜回中，先动/后动/长短路径） | per-drone if 分支已合法，但无认知 | 已解锁，待自然涌现 |
| 异步时间线（太空电梯各机独立段节点） | inittime 被禁，auto_init 统一切段 | 远期架构级 |

新退化风险（reflection 文档预言）：**全程绕圈**——math 解锁后所有段都写 `2*pi*i/N` 同心圆是下一个退化形态。"1-2 段绕圈可取，全程绕圈退化"。建议：跨段检测连续 ≥3 段使用同中心圆公式时打回（degradation 家族扩展）。

旁证：reflection 文档早已写明"不要预设固定安全距离（如>100cm）——这是枷锁"与"不额外加安全常量"，与今日 51cm 唯一硬下限的清理方向一致。

音乐对齐量化：模板段窗 vs librosa hard cues，5/7 边界在 1.5s 内（大闹天宫人类标准 8/11）。13.0s 边界偏 1.9s 最差。P1（music_brief 驱动段窗+章法生成）仍是头号工程。

# 11.8 蒸馏复盘 III：带着 agent 失败模式重读原始作品 (2026-06-10 深夜)

旧蒸馏问"作品好在哪"；这轮问"dntg 为什么从来不会犯 agent 烧轮次的那些错"。新发现：

1. **灯光就是时钟（头号发现）**。dntg 每个 keyframe 都是 `move2(d, target, T)` + 恰好 T/100 个 tick 的灯光循环——灯光循环本身就是等待，全片没有一处"delay 补余数"的算术。逐条核对：1000ms↔10 ticks、1500↔15、1600↔16，全部精确吻合。我们的协议 `move2 → apply_light(3-5 ticks) → delay(flying_ms - ticks*100 + 100)` 是三步带算术——S07 日志里模型反复推演 cursor 数学烧掉的轮次，根源就是这个协议设计。dntg 的写法同时消灭算术错误并免费获得 10-16 ticks/keyframe 的灯光密度（2100 条灯光指令不是额外工作量，而是等待结构本身）。**提案**：canonical loop 改为 `move2(drone, target, flying_ms); apply_light(drone, color, flying_ms // 100)`，不写尾部 delay；错峰时 `ticks = (flying_ms - i*stagger_ms) // 100` 自然回正。
2. **大 delay 都是戏剧性定格，不是填充**。仅有的 4000/5000/6000ms delay 全部是符号展示：飞到镰刀/锤子阵型(1000ms)后点亮定格 4-5s 让观众读出形状。**冲突**：我们的悬停硬检测（≥1s 静止即打回）使 dntg 的高潮设备在本系统内非法。需要"声明式定格"豁免方案（如尾段/署名段允许、或角色声明 hold 的段放宽阈值）——待人工决策。
3. **从黑暗点亮**（12 处 `23+a*8` 接近黑场的渐亮坡）：起飞"点火"效果。一行词汇成本。
4. **刚体旋转 keyframe 天然安全**（11 处旋转向量移动）：旋转保持两两距离，无需 assignment 搜索。validator 的刚性圆退化检测正是防它被滥用——定位为"单场 1-2 段的合法设备"。
5. **修正旧蒸馏的误读**：human_choreography_distillation.md 称 dntg"速度范围 50-400"——v3 生成脚本全程走 move2 helper（Vel 上限 200），XML 里的 400 是 `VelXY(v, 2v)` 的加速度。我们的 clamp(20-200 / 50-400) 与 dntg 实际完全一致。
6. **intime() 锚定 vs auto_init 取整**：dntg 每段每机绝对时间重锚（消除漂移+支持异步入场）；我们禁 inittime 用 auto_init 向上取整（漂移累积+异步被锁死）。架构级，配合 11.7 异步时间线条目。

11.8 补充（蒸馏范围扩展）：
- 命令流地面真值：`output/大闹天宫/动作组/动作组1/pyfiiCode.py`（shipped 流水）每机 302 TurnOnAll + 295 delay(100) vs 仅 28 move2——约 11:1 灯光:移动指令比，"灯光就是时钟"是工件的字面结构；VelXY 最大 (200,400) 确认 400 是加速度。
- `output/大闹天宫/大闹天宫.py` 是回放 loader（逐机重放 pyfiiCode.py），`tests/dntg20220730_v3.py` 是生成器——两层工件链。
- 2023 编程挑战赛两份参赛作品（王圣茗/王子昱）首次扫描：均为 2 机 20-24s 学生练习（XY 跨度 ~300，minD 40-60cm），编舞蒸馏价值低，存档即可。

# 11.9 蒸馏复盘 IV：三部主要作品命令流+轨迹级蒸馏 (2026-06-10 深夜)

按 human_choreography_distillation.md 双模式方法，对太空电梯/无人区/开启新征程做命令流统计与逐帧轨迹分析（编程挑战赛作品按人工指示移出蒸馏范围）。

**1. 悬停门与整个人类语料库矛盾（铁证）。** 全队同时静止区间（≥1s，0.2cm/frame 同阈值）：大闹天宫 7 个共 15.1s（占全片 24%！最长 4.0s）、无人区 7 个 9.0s、太空电梯 3 个 6.0s、开启新征程 2 个 3.6s。**现行悬停硬门会打回全部四部 shipped 人类作品，包括金标准 dntg。** 关键区分：dntg 定格期间灯光持续编舞（302 条灯光指令覆盖定格窗口）——静止+灯光活跃=合法定格，静止+灯光静默=真空洞。建议门改造：全队静止 ≥1s 仅当窗口内无灯光变化时才违规。

**2. dntg 的 11:1 灯光比是孤例不是规范。** 语料库灯光:移动指令比：dntg 11:1、太空电梯 0.4、无人区 0.2、开启新征程 0.1——两种合法语体：灯光编舞型（dntg）与运动驱动型（其余）。"灯光就是时钟"应作为可选语体（register）供 composition plan 按段选择，而非强制协议——修正 11.8 提案 1 的定位。

**3. 异步入场实测。** 太空电梯各机首动齐发（1.0s）——其"异步"在段节点不在入场；无人区才有真异步入场（1.0→4.5s 散开），配合留白开场。异步入场用现有 per-drone delay 即可实现，无需解禁 inittime。

**4. 质心轨迹是叙事指纹。** 开启新征程：最大漂移 153cm、净位移 74cm、起点偏左 (206,280)——"左→右启程"在质心曲线上直接可读；无人区：漂移 96cm 净 0（出走-回归弧线）；太空电梯：漂移仅 37cm（垂直主题，质心钉死）。建议 quality_report 增加质心最大/净漂移指标。

**5. 动作密度谱。** 每机移动指令/66s：无人区 52-68、太空电梯 55-58、开启新征程 21-30、dntg 28——短切型作品移动频率是我们 keyframe 节奏的 2-4 倍；我们的 2600-3600ms 节奏接近 dntg 端，密集短切语体未覆盖。

# 11.10 蒸馏复盘 V：视觉帧级蒸馏——之前全部蒸馏都没用眼睛 (2026-06-11)

按蒸馏方法论"按段中点抽帧确认观感"，首次对 dntg 视频与我们 staticgeo run 视频做帧级目视对比（dntg 7 帧 / 我们 6 帧）。数字分析完全看不到的两条视觉语法：

**1. 帧内可读性来自镜像/点对称，而我们的 prompt 在主动破坏它。** dntg 每一帧都是可读图形：t=13 的 3-1-3 点阵（每架机都有穿过中心 (280,280) 的镜像伙伴，坐标逐对验证 (520,465)↔(40,95) 等，Z 也对称）；t=25 斜对称 = 三对镜像 + 中心锚；t=33 双子结构（下方三机等距横线 + 上方四机旋转簇，各自内部可读）；t=56 镰刀轮廓一眼可辨。dntg 的"非对称"全部发生在**段与段之间**，帧内永远是高度组织的。我们的帧：S01 对角线可读、S06 楔形尚可，但 S02-S05（恰恰是 prompt 写着"非对称几何"的段）全是无结构散点——7-9 机规模下，眼睛对无对称散布的解读就是噪声。**"非对称几何"这条 prompt 规则是视觉噪声的直接来源**：本意防模板退化，实际禁掉了可读构图。改法：帧内要求可读构图（镜像对/点对称/可辨轮廓：线、V、弧、点阵），变化与非对称放在 keyframe 之间。
**2. 每机色彩身份 vs 整队同色刷。** dntg 群舞段每架机有自己的颜色（7 色同屏），交叉换位时观众能跟踪个体表演者；整队同色只用于宣言时刻（镰刀全红）。我们所有帧都是整队单色——换位在视觉上不存在。改法：灯光语体补充"个体色彩身份"（群舞段每机/每对独立色相；宣言 keyframe 才统一色）。
**3. 可读性可度量。** 镜像对称分数：每点对质心反射后到最近邻点的平均距离（dntg t=13 ≈ 0，我们的散点帧很大）→ 进 quality_report。

方法论结论：补足"音乐-数字-代码-视觉"四链路中缺失的视觉链路；前四轮蒸馏（I-IV）全部是数字/代码链路。

# 11.11 音乐工作流测试矩阵 (2026-06-11)

跨音乐验收材料（人工提供）+ 语料库音乐，各自暴露一个设计问题：

| 音乐 | 时长/BPM/能量 | 考验点 |
|---|---|---|
| cannon_in_D.mp3 | 68s / 103 / 渐进 | 基线（现模板手工调过） |
| 云宫迅音_缩混3.mp3 | **174.5s** / 123 / 低重+高潮爆发 | 选窗：演出 ~65s，plan 必须自己决定用哪一段（dntg 先例：用前 1/3） |
| cjxq.mp3 | 72s / **143.6** / 只有 low+mid **无 high 段** | 无高潮音乐不得伪造爆发段——直接考"渐强≠幅度"原则 |
| 阿鲲-太空电梯.mp3 | 70.7s / 112 / 渐升 | 垂直主题、异步入场语体 |
| 无人区.mp3 | 70.1s / 136 / 留白→爆发 | 负空间/亮灯定格语体 |
| 蜂群耶_缩混.mp3 | 67.8s / 117 / 高 onset 4.4/s | phrase 切分 vs 逐拍跟随 |

验收标准：换音乐零手工编辑，产出连贯且**彼此不同**的演出；任何跨音乐雷同段落即未除尽的 hardcode。

11.11 补充：已验证可解码的音乐路径（music workstream 直接可用）——
云宫迅音_缩混3.mp3 与 cjxq.mp3（仓库根，人工指定）；
output/太空电梯/动作组/阿鲲-太空电梯.mp3 (70.7s/86BPM)、output/无人区/动作组/无人区.mp3 (70.1s/103BPM)、output/开启新征程 加速版715/动作组/蜂群耶_缩混.mp3 (67.8s/118BPM)；
另有备选：output/校园作品A/动作组/周深-向光而行.mp3、output/1/动作组/TRIP_01.mp3、output/d/2021比赛/Positive Outlook。
注：cjxq.mp3 即 output/大闹天宫已摆烂/ 的音乐——一个被放弃的 dntg 项目，无高潮段可能正是当年难做的原因，反而是好测试。
（2026-06-11：以上音乐已全部复制到仓库根目录，music workstream 直接用根路径即可：阿鲲-太空电梯.mp3 / 无人区.mp3 / 蜂群耶_缩混.mp3 / 周深 - 向光而行 （赵-孟）2.mp3 / TRIP_01.mp3 / Diavid Hoffner - Positive Outlook [mqms].mp3；mp3 按 .gitignore 策略不入库。）

# 11.12 新金标准：codex_9d_dwell_flash_20260611_051115 (2026-06-11 人工目检认定)

人工视觉验收认定为迄今最佳。档案：全流程 S01→LAND 每段 1 cycle，0 警告，¥0.53/52min；
readable_ratio 0.55 / settled readable 66% / mean_err 37cm（=dntg 水平）/ centroid 120/79cm；
自由起飞 + 错峰启动 + math 几何 + 灯光时钟 + 帧内可读构图。
记录为历史最佳的人工评价（文档记录，不入 fixture——把"最佳 run"钉进测试就是 hardcode：
最佳会持续轮换，质量参照活在指标与文档里，不冻结在代码里）。
