# AI 编舞探索

这里记录不适合继续塞进根目录 README 的 AI 编舞实验结论。

## 当前方向

`nl_choreo` / Qwen 视频理解闭环已经归档到 `archive/nl_choreo_qwen/`。核心教训是：视频理解模型并不等于连续动作理解。抽帧会丢失无人机表演里最关键的速度变化、错峰启动、路径交叉和节奏。

后续主线改为：

1. 强文本/推理模型生成 motion brief 或 phrase spec。
2. 将 spec 转成可运行的 PyFii 脚本。
3. 本地读回 `.fii`，做密集轨迹检查。
4. 把 PyFii 的距离 warning 和动作未完成 warning 视为硬失败。
5. 渲染 2D/3D 视频，作为最终观感验收物。

视频仍然有价值，但它应该是验收输出，不应作为第一或唯一反馈闭环。

## 工作流要点

模型应先设计动作，再解决安全衔接。比较合理的生成流程是：

1. 写 motion brief：音乐段落、动作意图、能量曲线、视觉目标。
2. 写 phrase/action-score：时间范围、分组、角色映射、动作原语、节奏说明、风险和修复策略。
3. 生成 PyFii 代码：目标点、中间点、错峰、等待、速度求解和灯光节拍。
4. 本地验证：读回、密采样、越界、最小距离、动作完成、XY/Z 跨度、角色变化、固定车道退化和中途对穿风险。
5. 看 2D/3D 视频；需要修改时尽量只改对应 phrase。

重要约束不是“永远保持扇区顺序”，而是“每次转场在采样后都可解释且安全”。固定中心绕圈、均匀三秒模板格、全局单向旋转和长期静态角色，都应视为退化。

## 高参考价值归档脚本

归档脚本位于 `archive/nl_choreo_qwen/examples/`。

### GPT-5.5 生成脚本

- `gpt55_phrase_vibe_v3_60s.py`：最有参考价值的 GPT-5.5 版本。有 phrase durations、phrase designs、动作原语、group modes、非均匀时间、局部 offset 和验证逻辑，是后续 phrase-spec 生成器的最佳桥。
- `gpt55_template_motion_v2_60s.py`：适合作为动作词汇表和调试基线。里面的模板可以当原语参考，但最终工作流不应退化成固定模板库排列组合。
- `gpt55_action_score_v2_60s.py`：有参考价值的中间形态，比纯关键帧更接近 action-score，但重要性低于 `phrase_vibe_v3` 和 `template_motion_v2`。
- `gpt55_burst_recompose_60s.py`：参考价值较低，适合保留为 seed/baseline，不适合作为目标架构。

### Original / 手写脚本

- `original_crosscut_v9_60s.py`：最高价值手写基线。它展示了 phrase-like 设计、确定性角色交换、PyFii 硬检查和 3D 视频验收。
- `original_phrase_motion_v4_70s.py`：很清晰的 phrase 骨架。有 formations、phrase durations、phrase 函数、planned keypoints、验证和灯光，适合参考 spec-to-code 的结构。
- `original_kinetic_ribbon_v8_60s.py`：连续动作参考价值高，尤其适合看 timing、速度求解、ribbon field 和 readback metrics。
- `original_flow_field_v5_70s.py`：flow-field 方向的有效迭代，研究这条路时优先看 v5 而不是 v4。
- `original_continuous_ribbon_v6_75s.py`、`original_kinetic_ribbon_v7_60s.py`、`original_flow_field_v4_70s.py`：主要是历史迭代，用于追踪 v8/v5 的演化即可。

## Provider 配置

根目录 `ai_providers.example.json` 只保留强模型路径需要的 provider scaffold。本地密钥写在被忽略的 `ai_providers.local.json`。
