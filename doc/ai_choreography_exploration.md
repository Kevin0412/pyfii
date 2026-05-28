# AI 编舞探索

这里记录不适合继续塞进根目录 README 的 AI 编舞实验结论。

## 当前方向

`nl_choreo` AI 编舞探索已经归档到 `archive/nl_choreo_ai_exploration/`。它起点是 Qwen 视频理解闭环，后来也混入了 GPT-5.5/Codex 直接生成编队程序的实验。核心教训是：视频理解模型并不等于连续动作理解。抽帧会丢失无人机表演里最关键的速度变化、错峰启动、路径交叉和节奏。

后续主线改为：

1. 先分析音乐，生成 `music_brief`：tempo、beat grid、段落边界、onset 密度、能量曲线、频谱明暗、情绪代理和 hard/soft cue。
2. 强文本/推理模型基于 `music_brief` 生成 motion brief 或 phrase spec。
3. 将 spec 转成可运行的 PyFii 脚本。
4. 本地读回 `.fii`，做密集轨迹检查。
5. 把 PyFii 的距离 warning 和动作未完成 warning 视为硬失败。
6. 渲染 2D/3D 视频，作为最终观感验收物。

视频仍然有价值，但它应该是验收输出，不应作为第一或唯一反馈闭环。

## 工作流要点

模型应先设计动作，再解决安全衔接。比较合理的生成流程是：

1. 写 music brief：音乐段落、beat/onset、能量曲线、频谱明暗、情绪代理、歌词/主题线索和 hard/soft cue。
2. 写 motion brief：动作意图、空间叙事、能量响应、视觉目标和禁用退化项。
3. 写 phrase/action-score：时间范围、音乐 cue、分组、角色映射、动作原语、节奏说明、灯光同步、风险和修复策略。
4. 生成 PyFii 代码：目标点、中间点、错峰、等待、速度求解和灯光节拍。
5. 本地验证：读回、密采样、越界、最小距离、动作完成、XY/Z 跨度、角色变化、固定车道退化、中途对穿风险和音乐边界对齐。
6. 看 2D/3D 视频；需要修改时尽量只改对应 phrase。

重要约束不是“永远保持扇区顺序”，而是“每次转场在采样后都可解释且安全”。固定中心绕圈、均匀三秒模板格、全局单向旋转和长期静态角色，都应视为退化。

## 最高参考基线

`tests/dntg20220730_v3.py` 是目前最有参考意义的编队脚本。它是当时人工设计的优秀作品，价值不在于某个具体坐标，而在于它展示了成熟编舞应该具备的组织方式：

- 按音乐段落组织动作，每段都有明确起止时间和视觉意图。
- 用数学轨迹表达连续运动，例如复数旋转、三角函数、Lissajous-like 点表和高度相位。
- 通过角色映射和临时分组改变无人机职责，避免固定中心、固定外圈或固定车道。
- 段内动作有等待、错峰、分组差异和节奏缓急，而不是简单从一个关键帧直线飞到下一个关键帧。
- 灯光和运动同步编排，100ms/600ms 级灯光节拍直接参与音乐表现。
- 末尾用 `read_fii(..., fps=60)` 和 `pf.show(..., max_fps=60)` 读回、预览和生成视频，说明最终验收仍应落到 PyFii 本地轨迹和视频。

后续 DeepSeek/GPT agent 工作流要优先学习它的“动作乐谱”结构：motion brief 先描述段落意图，phrase spec 再描述分组、角色、轨迹函数、节奏和灯光，代码生成只负责把这些设计稳定落到 PyFii。

## 人类作品经验池

除 `tests/dntg20220730_v3.py` 外，`output/` 中还有一批人类设计作品值得做知识蒸馏：

- `output/大闹天宫`
- `output/太空电梯`
- `output/开启新征程 加速版715`
- `output/competition_test_62`
- `output/无人区`
- `output/校园作品A`
- `output/1`（校园作品B-Trip）
- `output/d/比赛现场程序（修改版）`（早期设计，补灯光版）
- `output/d/比赛用无人机`（早期设计，极简灯光）

完整蒸馏记录见 [human_choreography_distillation.md](human_choreography_distillation.md)。

这些作品必须用两个模式一起看：`pf.read_fii(path, fps=60, ignore_acc=True)` 用来还原当时无加速度模拟语境下的视觉设计意图；`pf.read_fii(path, fps=60, ignore_acc=False)` 用来做现代执行验证。轨迹第一个返回值能提供每架机的时间、XYZ、朝向和灯光状态，适合抽取中心移动、队形外接框、高度层、角色顺序变化、最小距离、运动跨度和停顿比例。已有 2D/3D 视频则用于人工确认观感，2D 看平面队形和角色换位，3D 看高度层、纵深、升降和遮挡。

需要注意：这些作品里有不少 `action isn't completed` warning，部分轨迹还会出现过近距离。旧作品的默认加速度 warning 不能直接否定设计价值，因为当时的初始视觉效果以无加速度模式为准；但它们也不能直接作为安全样板。正确用法是先在无加速度模式下提炼设计方法，再让新的 agent 用速度求解、错峰、中间点和安全检查重新实现，并在默认加速度模式下通过硬门。

音乐输入也必须进入经验池。已加入 `tools/analyze_music_motion_alignment.py`，用于把源音乐的 tempo、beat、onset、能量、频谱、结构边界与 `inittime`、灯光密度和轨迹指标对齐。`大闹天宫`、`太空电梯`、`开启新征程 加速版715`、`无人区`、`校园作品A`、`output/1` 已有可解码音乐；`competition_test_62` 当前缺源音频，只能暂作动作压力样本。

初步可学习的设计经验：

- 主题先行：作品名和音乐气质会约束动作语言，例如神话叙事、上升/电梯意象、新征程、无人区、校园队形等。agent 应先写主题动作词，再写坐标。
- 空间幅度要大：优秀作品经常在 60-70 秒内覆盖 300-500cm 级 XY 变化，并配合 200cm 以上高度变化，避免整段挤在中心小范围抖动。
- 高度层是叙事工具，不只是避撞工具。很多段落会同时使用 3-7 个高度层，形成塔、帘、斜坡、上升、坠落和聚焦。
- 队形密度需要呼吸：宽阵、窄阵、竖线、横线、团簇、展开之间要交替出现，不能让所有段落维持同一种密度。
- 中心可以移动：人类作品不会总把重心锁在 `(280, 280)`，而是让中心随段落偏移、回收、再偏移，形成空间叙事。
- 角色顺序要变化：按 X/Y 排序的角色顺序频繁变化，说明编舞里有换位和穿插；但新的工作流必须用中间点和错峰保证这些换位可执行。
- 灯光应是段落的一部分：灯光不是最终装饰，而是和起飞、扩张、压缩、高潮、收束同步的节奏信号。
- 警告要转成修复任务：旧作品里“飞不完”的部分只能说明设计野心，不代表实现方式可取。agent 应把它们翻译成“需要延长时间、提高合法速度、拆段、增加等待或重新分配角色”。

### 人类作品蒸馏方法

后续蒸馏不应只看整段总指标，而应做段落级分析：

1. **先按 `inittime` 切段**
   - `pyfiiCode.py` 里的 `inittime(...)` 和 `webCodeAll.xml` 里的 `block_inittime` 是最直接的段落标志。
   - 例如 `大闹天宫` 的 4s、7s、10s、16s、21s、29s、37s、45s、54s、59s 等段落很清晰，每段都能看到不同的目标点密度、灯光密度和队形外接框。
   - 不是所有作品都干净使用 `inittime`。例如某些作品会把大量动作塞在 0-1s 附近，这时不能机械相信段落标志，需要再用轨迹变化和视频抽帧反推真实段落。

2. **再读坐标和速度**
   - 从 XML 中抽 `Goertek_MoveToCoord` 的目标点，按段统计队形中心、XY 外接框、Z 外接框、高度层数量、目标点数量。
   - 同时抽 `Goertek_HorizontalSpeed` / `Goertek_VerticalSpeed`，判断人类设计是否在某段刻意加速、减速、拉高或压低。
   - 坐标不是为了照抄，而是为了给动作命名：例如“宽阵扩张”“纵向幕布推进”“塔形上升”“中心偏移后回收”“多高度聚焦”。

3. **再读灯光和 delay**
   - 统计每段 `TurnOnAll` / `TurnOffAll` / `delay` 密度，识别灯光是否在 100ms、500ms、1000ms 等节奏上配合动作。
   - 灯光密集段通常对应起飞亮相、高潮铺陈、快速闪断或收束，不应在 codegen 阶段随便丢掉。

4. **再用双模式 `read_fii(..., fps=60)` 读回轨迹**
   - `ignore_acc=True` 是历史视觉模式，用来判断当时设计想看到的队形、节奏和空间构图。
   - `ignore_acc=False` 是现代验证模式，用来检查刹停重规划、动作未完成和近距离风险。
   - 第一个返回值是每架机的离散轨迹，可按段计算实际中心、外接框、高度层、最小距离、角色顺序变化、停顿比例和是否飞完。
   - 这一层用来分辨“设计想法”和“执行问题”：动作句法可以学习，`action isn't completed` 必须作为修复任务。

5. **最后用视频抽帧确认观感**
   - 对已有 2D/3D 视频按 `inittime`、段中点、强变化点抽帧，生成 keyframe sheet。
   - 2D 帧用于确认平面图案、角色换位、横切和展开；3D 帧用于确认高度层、纵深、升降、遮挡和空间叙事。
   - 视觉帧用于给段落命名和判断观感：是否像幕布、塔、蛇形、横切、聚合、爆开、上升、坠落、换位。
   - 视频抽帧不是重新走 Qwen 视频理解闭环；它是辅助人和未来视觉模型定位“这段到底好不好看”的轻量证据。

每个蒸馏出的段落最好落成结构化记录：

```json
{
  "source": "output/大闹天宫",
  "visual_mode": "ignore_acc=True",
  "validation_mode": "ignore_acc=False",
  "time_range": [21, 29],
  "intent": "宽阵多步换位，灯光高密度推进",
  "formation_notes_2d": "XY 外接框接近全场，角色横向交换明显",
  "spatial_notes_3d": "Z 层次较少，主要依赖平面张力",
  "motion_primitives": ["wide_expand", "role_exchange", "staggered_steps"],
  "light_notes": "100ms 级颜色推进，灯光是节奏主体",
  "execution_risk": ["action_unfinished"],
  "repair_strategy": ["延长段落", "按距离求解速度", "拆中间点", "错峰启动"]
}
```

未来系统提示词只应吸收这种结构化经验，而不是原始 `.fii`、`webCodeAll.xml` 或 `.py` 文件。

## 高参考价值 AI 归档脚本

归档脚本位于 `archive/nl_choreo_ai_exploration/examples/`。

这些脚本里的 `gpt55_` 和 `original_` 都是 GPT-5.5/Codex 直接设计出来的编队飞行程序。它们的价值不是“复用某套固定模板”，而是展示强模型在充分约束下已经能直接提出可运行、可读回、可渲染的动作设计。

文件名只作为维护者回看和经验溯源索引。后续 agent 不应把这些 `.py` 文件原文塞进系统提示词，也不要求用户显式引用某个版本名。

### gpt55 系列

- `gpt55_phrase_vibe_v3_60s.py`：最有参考价值的 GPT-5.5 版本。有 phrase durations、phrase designs、动作原语、group modes、非均匀时间、局部 offset 和验证逻辑，是后续 phrase-spec 生成器的最佳桥。
- `gpt55_template_motion_v2_60s.py`：适合作为动作词汇表和调试基线。里面的模板可以当原语参考，但最终工作流不应退化成固定模板库排列组合。
- `gpt55_action_score_v2_60s.py`：有参考价值的中间形态，比纯关键帧更接近 action-score，但重要性低于 `phrase_vibe_v3` 和 `template_motion_v2`。
- `gpt55_burst_recompose_60s.py`：参考价值较低，适合保留为 seed/baseline，不适合作为目标架构。

### original 系列

`gpt55_` 和 `original_` 都是 GPT-5.5/Codex 直接设计出来的编队程序；`original_` 只是实验线命名，不代表作者归属。

- `original_crosscut_v9_60s.py`：最高价值 original 基线。它展示了 phrase-like 设计、确定性角色交换、PyFii 硬检查和 3D 视频验收。
- `original_phrase_motion_v4_70s.py`：很清晰的 phrase 骨架。有 formations、phrase durations、phrase 函数、planned keypoints、验证和灯光，适合参考 spec-to-code 的结构。
- `original_kinetic_ribbon_v8_60s.py`：连续动作参考价值高，尤其适合看 timing、速度求解、ribbon field 和 readback metrics。
- `original_flow_field_v5_70s.py`：flow-field 方向的有效迭代，研究这条路时优先看 v5 而不是 v4。
- `original_continuous_ribbon_v6_75s.py`、`original_kinetic_ribbon_v7_60s.py`、`original_flow_field_v4_70s.py`：主要是历史迭代，用于追踪 v8/v5 的演化即可。

## Codex 设计经验

从 `dntg20220730_v3.py`、`original_crosscut_v9_60s.py` 和这些 GPT-5.5/Codex 归档脚本里，可以总结出几条后续必须继承的经验：

- 好编舞先有动作意图，再有坐标。模型输出应先描述"交叉切入、压缩爆开、错层换位、反向切割、收束"等动作句法，再落到点位。
- phrase 比 keyframe 更重要。单纯关键帧直连会变成点位切换；phrase 需要包含段内节奏、分组分工、角色映射、等待、错峰和灯光。
- `original_crosscut_v9_60s.py` 是当前 AI 生成线里最满意的基线：它不靠 random 决定动作，不靠固定模板拼接，也没有退化成单一全局旋转，而是用确定性换位、cross energy、路径验证和 3D 视频验收形成闭环。
- `gpt55_phrase_vibe_v3_60s.py` 说明模型可以生成非均匀时间和动作原语组合；`gpt55_template_motion_v2_60s.py` 说明模板适合做动作词汇表，但不能成为最终编排方式。
- `original_phrase_motion_v4_70s.py`、`original_kinetic_ribbon_v8_60s.py`、`original_flow_field_v5_70s.py` 分别代表三类有用结构：phrase 骨架、连续 ribbon 场、flow-field 状态规划。
- 安全检查不能反过来支配动作设计。安全层负责指出哪里飞不完、哪里距离危险、哪里可能对穿；修复时优先调整衔接、中间点、等待、速度和角色分配，而不是把动作整体压成保守固定车道。
- 视频理解不是主反馈。真正可靠的反馈链是 PyFii 读回、密采样、warning 捕获、指标报告和 2D/3D 视频；模型可以读报告、改 spec、再生成代码。

完整的脚本设计模式分析见：
- 人类设计编码模式：[pyfii_script_patterns_human.md](pyfii_script_patterns_human.md)
- AI 生成编码模式：[pyfii_script_patterns_ai.md](pyfii_script_patterns_ai.md)

AI 产物轨迹蒸馏见：[ai_generated_distillation.md](ai_generated_distillation.md)

## 未来设计规划

下一阶段目标是做一个 DeepSeek/GPT 可切换、多轮对话式、可局部修改的 agent 编队工作流。它不再复活旧的视频理解闭环，而是围绕 motion brief、phrase spec、PyFii 代码和本地验收构建。

### 系统提示词与知识库

未来 agent 需要一个轻量知识库或系统提示词包，但内容应是从优秀脚本中归纳出的设计方法，而不是原始 `.py` 文件：

- 方法：段落化编舞、phrase/action-score、分组分工、角色映射、非均匀时间、错峰、等待、速度求解、灯光节拍。
- 音乐理解：tempo、beat grid、onset 密度、结构边界、能量曲线、频谱明暗、歌词/主题线索、hard/soft cue 和动作边界容差。
- 设计思路：先写音乐理解，再写动作意图，再写衔接，再落到 PyFii；先保证动作有观感目标，再用验证报告修安全和执行性。
- 避免项：固定中心绕圈、全局单向旋转、固定车道、均匀模板格、为了安全牺牲所有动作变化、用 random 直接决定最终动作。
- 验收规则：PyFii 读回、warning 捕获、密采样指标、角色变化、XY/Z 跨度、2D/3D 视频输出。
- 参考来源：维护者可以追溯到 `tests/dntg20220730_v3.py`、人类作品输出目录和 AI 归档脚本，但模型运行时只接收蒸馏后的原则、schema、示例 spec 和失败修复策略。

### 工作流形态

1. 用户提供音乐和自然语言任务，或继续给修改意见，例如“30-45 秒更狠一点，多一些交叉切入和确定性换位”“不要全局单向旋转”“结尾不要排直线”。
2. agent 先分析音乐并生成或修改 `music_brief`，明确 tempo、beat/onset、结构边界、情绪曲线、hard/soft cue 和证据缺口。
3. agent 再生成或修改 `motion_brief`，明确动作目标、空间叙事、音乐响应、禁用退化模式和验收重点。
4. agent 再生成 `phrase_spec`，每段包含 `time_range`、`music_cue`、`beat_policy`、`intent`、`groups`、`role_mapping`、`motion_primitives`、`timing_notes`、`light_notes`、`risk`、`repair_strategy`。
5. codegen 把 `phrase_spec` 转成 PyFii 脚本，自动处理目标点、中间点、速度/加速度、错峰、等待和灯光节拍。
6. validator 运行脚本、保存 `.fii`、读回轨迹、捕获 PyFii warning、密采样并生成指标报告。
7. renderer 输出 2D/3D 视频和关键帧，供用户验收。
8. 用户继续用自然语言反馈，agent 只修改相关 phrase，除非结构性失败才重写全片。

### 模型切换

模型配置继续走根目录 `ai_providers.example.json` / 本地 `ai_providers.local.json`。工作流应支持在同一会话里切换 provider：

- `custom_gpt`：用于自定义 OpenAI-compatible 服务。
- `deepseek` / `deepseek_pro`：用于强文本推理和低成本多候选。
- 后续 GPT 模型：用于高质量 phrase spec、复杂修复和最终代码生成。

切换模型时不丢会话状态。`motion_brief`、`phrase_spec`、生成脚本、验证报告和用户反馈都作为上下文资产保存，换模型只是换下一轮执行者。

### Agent 状态文件

每次任务应生成一个独立工作目录，例如 `output/ai_choreo_sessions/<session_id>/`，至少包含：

- `music_source.*`
- `music_analysis.json`
- `music_brief.md`
- `motion_brief.md`
- `phrase_spec.json`
- `generated.py`
- `validation_report.json`
- `repair_log.md`
- `render_2d.mp4`
- `render_3d.mp4`
- `keyframes/`

这样用户和模型都可以围绕同一份状态反复修改，而不是每次从零开始猜。

### 验收硬门

每轮候选必须通过这些硬门才进入人工观感验收：

- Python 脚本可执行。
- `pf.Fii(...).save()` 成功。
- `pf.read_fii(..., fps=60, ignore_acc=False)` 可读回并作为执行验证。
- `pf.read_fii(..., fps=60, ignore_acc=True)` 可作为视觉意图对照，但不能替代执行验证。
- `pf.show(..., show=False)` 或等价检查不出现 `distance between`、`action isn't completed` 等硬失败。
- 密采样报告包含最小距离、最大单段位移、平均位移、XY/Z 跨度、最长停顿、角色变化、全局旋转倾向和固定车道风险。
- 音乐报告包含 tempo、beat/onset、段落边界、能量曲线和 hard/soft cue；`phrase_spec` 的每段必须说明对应音乐 cue 和 beat/light 策略。
- 必须产出可观看的 2D/3D 视频。

### 实现顺序

1. 先定义 `music_brief` / `motion_brief` / `phrase_spec` schema 和 session 目录结构。
2. 抽象音乐分析入口，复用 `tools/analyze_music_motion_alignment.py` 的 tempo、beat、onset、结构边界和音乐-动作对齐指标。
3. 抽象 OpenAI-compatible provider client，支持 `custom_gpt`、`deepseek`、`deepseek_pro`，并允许按轮次切换。
4. 做知识库蒸馏：从 `tests/dntg20220730_v3.py`、人类作品输出目录和高价值归档脚本里提取方法、设计思路、音乐响应方式、应避免情况、验收规则和少量结构化 spec 示例，不把原始 `.py` 代码作为系统提示词。
5. 实现三阶段生成：先 music brief，再 motion/phrase spec，后 PyFii codegen。
6. 接入本地 validator 和 renderer，失败报告回灌给模型做 repair。
7. 做多轮修改入口：用户可以指定“改第几段/某个时间范围/某种音乐问题”，agent 保留原 session 只改局部。
8. 最后再做多模型对比：同一 music brief 让 DeepSeek/GPT 各出一版 spec 或代码，用同一套 validator 和视频产物比较。

这条线的最终验收不是“模型说它理解了视频”，而是用户能连续给反馈，agent 能保留上下文、切换模型、局部修改、稳定生成 `.fii` 和视频，并且结果具备成熟作品里的段落组织能力，同时吸收 Codex 生成版本中已经验证过的闭环经验。

## Provider 配置

根目录 `ai_providers.example.json` 只保留强模型路径需要的 provider scaffold。本地密钥写在被忽略的 `ai_providers.local.json`。

## Agent 自动生成进展 (2026-05-28)

基于 `tools/choreo_agent/` 框架的自动化编舞 agent 实验结果。

### 核心突破：非对称几何安全模式

经过大量试错，发现唯一稳定通过安全验证（minD > 51cm, d=0, a=0）的非对称几何模式：

1. **breathe + expand**：先小幅度呼吸展开（从 prev 偏移 30-40cm），让 best_assign 正确排列，再大跳至非对称目标
2. **显式 `prev` 更新**：每段尾必须 `prev = [(d.x,d.y,d.z) for d in drones]`
3. **flight_time_ms** 动态计算 delay，避免动作未完成和时间溢出
4. **动态 keyframe 数**：段长 < 10s 用 1 kf，否则 2 kf

### 全流程基准

手工编写 breathe+expand 模式的全流程（S01-S06+LAND，68s）达到 zero-warning：
- dist=0, act=0, minD=61.2cm
- 文件：`tools/choreo_agent/agent_projects/_archive/20260528_full_asymmetric/design.py`
- 2D/3D 视频已导出

### Agent 表现

- **S02 (13-23s, 10s)**：agent 稳定生成通过代码，~60% hit rate（10 轮内）
- **S03 (23-31s, 8s)**：agent 卡在局部最优（minD=5.4cm），收敛失败
- **S04-LAND**：agent 未收敛，需手工代码

### Agent 基础设施

- 3 温度顺序采样（0.9/0.5/0.1 → 0.5/0.2/0.05）
- 自然语言碰撞反馈（"d4和d6在14.2s仅5.6cm"）
- 时间预算静态检查 + double-delay 检测
- 前段通过代码注入 system prompt
- checkpoint 跨段持久（已修复竞态 bug）
- TUI 交互界面 (`tui.py`)
- 混合模式一键脚本 (`run_hybrid_pipeline.py`)：agent S02 + 手工 S03-LAND

### 关键发现

1. **best_assign 不充分**：在非对称几何中，best_assign 的 2D 距离优化不足以避免 3D 轨迹交叉。cannon_choreo.py 的成功依赖手工设计的几何配合 best_assign。
2. **窄段（<10s）是瓶颈**：8s 窗口的空间+时间约束超出 LLM 优化能力。
3. **代码持久化是基础**：早期并发采样的竞态条件导致设计文件被回退，修复后 agent 稳定性大幅提升。
4. **LLM 需要具体代码示例**：抽象模式描述不如一个通过的完整代码段有效。

### 待解决

- S03+ 窄段自动收敛（需离线排列优化或更强模型）
- 多 keyframe 的安全性保证
- 灯光节奏与音乐节拍同步
