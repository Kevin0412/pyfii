# Choreo Agent 后续计划

## 短期（本周）
- [ ] 全流程 agent 测试：用 safe_geo 重跑 S02-S06，记录每段通过轮数
- [ ] S04+ 修复：排查 agent S03 出口位置，确保后续段 prev 友好
- [ ] 视频输出修复：ignore_acc=True 出 2D 视频

## 中期
- [ ] 图片模态理解：给 agent 看 2D 轨迹图，直观看到碰撞
- [ ] 思维链嵌入：两阶段生成——先分析 prev 间距分布，再选 mode 出代码
- [ ] 音乐对齐：agent 先生成 music_brief，再生成 motion_brief
- [ ] 设计质量指标：速度变化率、空间密度呼吸、Z 轴分层——不只 minD

## 长期
- [ ] 超越 dntg：role mapping + math trajectory + continuous lights
- [ ] 从 7 部人类作品自动蒸馏模式
