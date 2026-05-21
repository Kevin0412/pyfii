"""Prompt Builder — 组装 LLM prompt"""
from pathlib import Path

CONTEXT_DIR = Path(__file__).resolve().parent.parent / "context_packs"


def load_context_pack(name: str) -> str:
    return (CONTEXT_DIR / name).read_text(encoding="utf-8")


def build_segment_prompt(
    segment_id: str,
    start_time: float,
    end_time: float,
    music_cue: dict,
    intent: str,
    prev_state: list,
    feedback: str = "",
) -> tuple[str, str]:
    """
    返回 (system_prompt, user_prompt)
    """
    system = "\n\n".join([
        load_context_pack("pyfii_api_minimal.md"),
        load_context_pack("pyfii_coding_rules.md"),
        load_context_pack("pyfii_segment_protocol.md"),
        load_context_pack("pyfii_anti_patterns.md"),
    ])

    user = f"""生成 Pyfii 编舞段 {segment_id}。

## 音乐信息
- 时间段: {start_time}s - {end_time}s ({end_time - start_time:.0f}s)
- 能量: {music_cue.get('energy', 'unknown')}
- 情绪: {music_cue.get('emotion', 'unknown')}

## 设计意图
{intent}

## 上一段出口状态 (prev)
```python
prev = {prev_state}
```

## 输出要求
只输出段代码（从 marker start 到 marker end），包含:
1. 几何定义 (2-4个几何)
2. intime + VelXY/VelZ
3. best_assign 离线调用结果硬编码
4. move2 + apply_light + delay
5. 结束更新 prev = targets

格式:
```python
# === PYFII_AGENT_SEGMENT_START id={segment_id} locked=false ===
# start_time: {start_time}
# end_time: {end_time}
# intent: {intent}

geo = [...]

for i, drone in enumerate(drones):
    drone.intime({start_time})
    drone.VelXY(200, 400)
    drone.VelZ(200, 400)

prev = [...]
for gi in range(len(geo)):
    # 硬编码 best_assign 结果
    perm = (?, ?, ?, ?, ?, ?, ?)  # TODO: 用 offline tool 计算
    for i, drone in enumerate(drones):
        tx, ty, tz = geo[gi][perm[i]]
        drone.move2(tx, ty, tz)
        apply_light(drone, "#xxxxxx", 15)
        drone.delay(1500)
    prev = [(geo[gi][perm[i]][0], ...) for i in range(N)]

# === PYFII_AGENT_SEGMENT_END {segment_id} ===
```
"""

    if feedback:
        user += f"\n\n## 人类反馈\n{feedback}\n请根据反馈修改。"

    return system, user
