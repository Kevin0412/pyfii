# Choreo Agent 踩坑记录

## 设计哲学
- **别替 agent 写规则，教它选模式**：强制 breathe 规则导致僵化，safe_geo(mode) 让 agent 自由选模式
- **minD 是门槛不是目标**：安全通过 ≠ 好编舞。人类蒸馏文档（doc/human_choreography_distillation.md）有丰富的 motion_primitives
- **guide < 60 行**：超过则 prompt 太大，API 超时。当前 40 行安全
- **prompt 和 guide 必须一致**：guide 写 move2=(x,y,z,t)，prompt 别说 VelXY

## API 稳定性
- **Retry 必须全面**：ConnectTimeout, ReadTimeout, ConnectError, RemoteProtocolError
- **连接超时 ≥ 60s**：DeepSeek API SSL 握手长期 30s+
- **单轮耗时 ~60s**：3 温度 × 5s 生成 + 3 × 3s 验证 = 24s 理想，实际带重试 ~60s

## 代码提取
- **只用 fenced markdown**：CoT 格式（"代码："段）提取不稳定，统一 ` ```python ``` `
- **禁止空段**：agent 输出非代码文本时，提取为空，导致 SEGMENT_END 间无代码

## 时序
- **auto_init 不是万能的**：agent 段出口时间不精确，后续段 inittime 可能冲突
- **ignore_acc=True 出视频**：False 模式 process.mp4 只有 3 秒

## 状态管理
- **单进程跑 agent**：多后台任务互相覆盖 state.json
- **每个测试前重置 state**：残留 locked 标记导致跳过实际生成

## safe_geo
- **算法保几何，agent 选模式**：4 种模式（expand/rotate/breathe/contract），泊松圆盘 + 随机环
- **geo 间距预检**：代码插入前检查坐标间距 < 80cm，精确定位哪两点过近

## 统计规律
- S02 平均 2-4 轮通过（61cm）
- S03 需 8-12 轮（同逻辑，收敛慢）
- S04+ 手工 fallback 最可靠
