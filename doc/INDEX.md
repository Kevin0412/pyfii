# 全部文档索引

`doc/` 是用户文档与专题研究的正文来源。GitHub 和 Web 文档中心使用同一份 Markdown；分类按照阅读目的，而不是文件创建时间。实验记录保留原始数据口径及日期，不等同于当前实现状态。

## 文档入口

| 文档 | 用途 |
| --- | --- |
| [文档中心](pyfii_docs.md) | 按任务选择阅读路径 |
| [全部文档索引](INDEX.md) | 当前页，完整导航与维护规则 |

<a id="tutorial"></a>

## 一、入门与使用教程

| 文档 | 用途 |
| --- | --- |
| [教程目录](tutorial/contents.md) | 学习顺序 |
| [安装](tutorial/install.md) | Python 环境、安装与本地开发 |
| [GUI 使用引导](pyfii_gui_guide.md) | 上传、warning、预览与导出 |
| [编队飞行](tutorial/group_flight.md) | 多机项目示例 |
| [脚本模式](tutorial/script_mode.md) | 脚本组织与工程生成 |
| [灯光编写](tutorial/light.md) | F400/F600 灯光 |

<a id="api"></a>

## 二、API 参考

| 文档 | 用途 |
| --- | --- |
| [Core API 参考](doc_zh_CN.md) | 无人机、动作、灯光、工程、轨迹、渲染接口索引 |

<a id="choreo"></a>

## 三、编舞设计与作品

| 文档 | 用途 |
| --- | --- |
| [大闹天宫（DNTG）](pyfii_script_patterns_human.md) | 原始七机作品、数学轨迹、角色映射与渲染截图 |
| [人类作品比较与蒸馏](human_choreography_distillation.md) | 跨作品分析、音乐对齐、双模式验证及设计经验 |

<a id="ai"></a>

## 四、AI 编舞与 Agent

| 文档 | 类型与用途 |
| --- | --- |
| [Agent 设计与经验](choreo_agent_lessons.md) | 设计总结：产品、验证层和生成修复 |
| [Agent 路线图](choreo_agent_roadmap.md) | 带日期的计划与进度 |
| [AI 编舞探索](ai_choreography_exploration.md) | 实验演进与方法来源 |
| [AI 编码模式](pyfii_script_patterns_ai.md) | 生成脚本设计模式与反例 |
| [AI 产物比较与蒸馏](ai_generated_distillation.md) | 实验样本指标、退化和对照 |
| [Cannon 设计经验](cannon_design_lessons.md) | 案例：完整设计过程与验证方法 |
| [DeepSeek Cannon 复盘](deepseek_cannon_reflection.md) | 案例：迭代记录与 Agent 启示 |

Agent 最新实现、配置与开发进度以 [tools/choreo_agent/PLAN.md](https://github.com/Kevin0412/pyfii/blob/pyfii-dev/tools/choreo_agent/PLAN.md) 和对应代码为准。历史实验和当前设计总结相互链接，不将旧实验指标当作当前系统指标。

<a id="maintenance"></a>

## 五、开发维护与工程研究

| 文档 | 用途 |
| --- | --- |
| [GUI 架构与部署](pyfii_gui.md) | 架构、配置、部署与限制 |
| [内部原理](tutorial/principle.md) | Fii/Blockly 格式、轨迹与渲染 |
| [渲染回归与截图 CI](rendering_ci.md) | 截图生成、自动发布与复现 |
| [真实飞行轨迹分析](flight_log_trajectory_analysis.md) | 真实飞行与模拟轨迹比较 |
| [fwfii 集成调研](fwfii_merge_plan.md) | 集成研究，尚未实操 |

## 维护规则

- 正文统一维护在 `doc/`，`docs/` 中旧链接保留跳转说明，已有静态资产不因整理而迁移。
- 新文档加入此索引和 Web 文档导航；已有关联文件尽量交叉引用，不重复复制正文。
- 文档用途分清使用说明、设计案例、现行方案与带日期的实验记录。研究资料不因旧而删除。
- 现有 Markdown 文件名和 Web URL 保持兼容；生成截图通过独立分支更新，不提交到源码文档目录。
- 修改文档后运行 `python -m unittest discover -s tests -p test_frontend_docs.py`，涉及 Web 文档中心时另运行前端 typecheck 与 build。
