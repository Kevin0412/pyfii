"""Prompt Builder — minimal for stability testing."""

from pathlib import Path
from typing import Sequence

CONTEXT_DIR = Path(__file__).resolve().parent.parent / "context_packs"

PACK_ORDER = [
    "pyfii_guide.md",
]


def _load_context_pack(name: str) -> str:
    path = CONTEXT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def build_system_prompt() -> str:
    parts = []
    for name in PACK_ORDER:
        content = _load_context_pack(name)
        if content:
            parts.append(content)
    parts.append("""
## Output
Write Python choreography code for the current segment.
use move2(d,(x,y,z),t_ms) + apply_light + drone.delay pattern.
4-space indent, no markdown, no import, no inittime.
""")
    return "\n\n".join(parts)


def build_segment_prompt(
    segment_id: str,
    start_time: float,
    end_time: float,
    intent: str,
    prev_state: Sequence[Sequence[float]] | None,
    feedback: str,
) -> tuple[str, str]:

    system = build_system_prompt()

    prev_lines = []
    if prev_state and len(prev_state) == 7 and any(float(p[2]) > 0 for p in prev_state):
        prev_lines.append(f"Prev exit coords ({segment_id} start):")
        for i, p in enumerate(prev_state):
            prev_lines.append(f"  d{i}: ({float(p[0]):.0f},{float(p[1]):.0f},{float(p[2]):.0f})")
        prev_text = "\n".join(prev_lines)
    else:
        prev_text = "First segment: design start_positions, takeoff to Z=110"

    seg_len = end_time - start_time
    total_ms = (seg_len - 1) * 1000

    user = f"""## {segment_id} ({start_time}-{end_time}s, {seg_len}s)
{prev_text}

Write {2 if seg_len < 10 else 3} keyframes, XY spacing>=200cm.
Use: move2(d,(x,y,z),flying_ms) + apply_light(d,c,ticks) + drone.delay(flying_ms-ticks*100)
Total flying_ms >= {total_ms:.0f}ms (1s light margin).
End with: prev = [(t[0],t[1],t[2]) for t in targets]
Only Python code, 4-space indent.
"""

    if feedback:
        user += f"\n## Feedback\n{feedback}\nFix accordingly."

    return system, user
