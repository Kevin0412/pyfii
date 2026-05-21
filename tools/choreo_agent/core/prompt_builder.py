"""Prompt Builder — 组装 LLM prompt"""
from pathlib import Path

CONTEXT_DIR = Path(__file__).resolve().parent.parent / "context_packs"

ALL_PACKS = [
    "pyfii_api_minimal.md",
    "pyfii_coding_rules.md",
    "pyfii_segment_protocol.md",
    "pyfii_anti_patterns.md",
    "pyfii_best_assign.md",
    "pyfii_light_patterns.md",
    "pyfii_validation_rules.md",
]


def load_context_pack(name: str) -> str:
    return (CONTEXT_DIR / name).read_text(encoding="utf-8")


def build_system_prompt() -> str:
    return "\n\n".join(load_context_pack(p) for p in ALL_PACKS)


def build_segment_prompt(
    segment_id: str,
    start_time: float,
    end_time: float,
    music_cue: dict,
    intent: str,
    prev_state: list,
    feedback: str = "",
) -> tuple[str, str]:
    system = build_system_prompt()

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
1. 几何定义 (2-4个几何)，几何内部点间距 > 51cm
2. inittime + VelXY/VelZ (两者值必须一致)
3. best_assign 离线调用结果硬编码为 perm = (...)
4. move2 + apply_light + delay
5. 结束更新 prev = targets
6. 生成前先计算飞行时间: 确保 light_ticks*100ms + delay_ms > flight_time(max_distance, speed)

格式:
```python
# === PYFII_AGENT_SEGMENT_START id={segment_id} locked=false ===
# start_time: {start_time}
# end_time: {end_time}
# intent: {intent}

geo = [...]

for i, drone in enumerate(drones):
    drone.inittime({start_time})
    drone.VelXY(200, 400)
    drone.VelZ(200, 400)

prev = [(drone.x, drone.y, drone.z) for drone in drones]
for gi in range(len(geo)):
    perm = (?, ?, ?, ?, ?, ?, ?)  # 用 best_assign 硬编码
    for i, drone in enumerate(drones):
        tx, ty, tz = geo[gi][perm[i]]
        drone.move2(clamp_xy(tx), clamp_xy(ty), clamp_z(tz))
        apply_light(drone, "#xxxxxx", 15)
        drone.delay(1500)
    prev = [(geo[gi][perm[i]][0], geo[gi][perm[i]][1], geo[gi][perm[i]][2]) for i in range(N)]

# === PYFII_AGENT_SEGMENT_END {segment_id} ===
```
"""

    if feedback:
        user += f"\n\n## 人类反馈\n{feedback}\n请根据反馈修改。"

    return system, user
