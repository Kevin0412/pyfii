# 文档索引

这里是仓库文档的总索引。项目文档完全公开，`doc/` 下的全部 Markdown 都直接进入 GUI 文档中心，并按基础使用与维护、编舞与 Agent、工程研究分组。分组表示主题，不表示公开级别或文档价值。

## 基础使用与维护文档

| 文档 | 用途 |
|------|------|
| [pyfii_docs.md](pyfii_docs.md) | 前端文档中心总览 |
| [pyfii_gui_guide.md](pyfii_gui_guide.md) | GUI 使用引导与常见问题 |
| [doc_zh_CN.md](doc_zh_CN.md) | PyFii core 使用文档 |
| [pyfii_gui.md](pyfii_gui.md) | GUI 架构、配置、部署与限制 |
| [tutorial/contents.md](tutorial/contents.md) | 教程目录 |
| [tutorial/install.md](tutorial/install.md) | 安装与开发启动 |
| [tutorial/group_flight.md](tutorial/group_flight.md) | 编队飞行示例 |
| [tutorial/script_mode.md](tutorial/script_mode.md) | 脚本模式 |
| [tutorial/light.md](tutorial/light.md) | 灯光编写 |
| [tutorial/principle.md](tutorial/principle.md) | 内部实现原理 |

这些文件由 GUI 在构建时直接读取，不要在前端复制第二份正文。网站中的总索引入口是 `/docs/index`。

## 编舞与 Agent

| 文档 | 用途 |
|------|------|
| [human_choreography_distillation.md](human_choreography_distillation.md) | 人类编舞作品蒸馏 |
| [pyfii_script_patterns_human.md](pyfii_script_patterns_human.md) | 人类作品编码模式 |
| [choreo_agent_lessons.md](choreo_agent_lessons.md) | 编舞 agent 开发经验 |
| [choreo_agent_roadmap.md](choreo_agent_roadmap.md) | 编舞 agent 后续计划 |
| [ai_choreography_exploration.md](ai_choreography_exploration.md) | AI 编舞路线、知识库和 Agent 演进 |
| [ai_generated_distillation.md](ai_generated_distillation.md) | AI 产物指标、退化样本与对照结论 |
| [pyfii_script_patterns_ai.md](pyfii_script_patterns_ai.md) | AI 编码模式和反例 |
| [cannon_design_lessons.md](cannon_design_lessons.md) | Cannon 编舞设计与验证经验 |
| [deepseek_cannon_reflection.md](deepseek_cannon_reflection.md) | Cannon 开发复盘和 Agent 启示 |

这些资料包含不同阶段的实验数据，但共同构成当前 Choreo Agent 的知识来源、反例库和设计依据。阶段性数据会注明时间与口径，不因此归入“历史归档”。

## 工程研究

| 文档 | 用途 |
|------|------|
| [flight_log_trajectory_analysis.md](flight_log_trajectory_analysis.md) | 真实飞行与模拟轨迹分析 |
| [fwfii_merge_plan.md](fwfii_merge_plan.md) | fwfii 集成调研，尚未实操 |

工程研究可能包含实验性结论或尚未实施的方案，使用前应结合当前代码和数据复核。
