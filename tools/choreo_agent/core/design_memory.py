"""Design memory — 人类偏好持久化（PLAN 12.2）。

每次 plan 评审意见、段级反馈、session 验收结论都落到 per-project
`design_memory.md`，并作为偏好包注入 planner 与段 prompt——
被否决的方向不再重犯。

反硬编码原则：人类意见只进 per-project（可选 + 全局）偏好文件，
永不进系统 prompt / 模板 / 代码。
"""

from __future__ import annotations

import time
from pathlib import Path

MEMORY_FILENAME = "design_memory.md"
GLOBAL_MEMORY = Path(__file__).resolve().parents[1] / "design_memory.global.md"
MAX_INJECT_CHARS = 900  # 注入 prompt 的偏好包上限（截最近条目）

KINDS = {
    "plan_directive": "章法评审意见",
    "plan_approved": "章法通过",
    "segment_feedback": "段级反馈",
    "segment_approved": "段级通过",
    "session_verdict": "Session 验收",
}


def record(project_root: str | Path, kind: str, content: str, context: str = "") -> Path:
    """追加一条人类评审记录；返回 memory 文件路径。"""
    root = Path(project_root)
    path = root / MEMORY_FILENAME
    label = KINDS.get(kind, kind)
    stamp = time.strftime("%Y-%m-%d %H:%M")
    entry = f"\n## {stamp} [{label}]{f' {context}' if context else ''}\n{content.strip()}\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(entry)
    return path


def load_preferences(project_root: str | Path, max_chars: int = MAX_INJECT_CHARS) -> str:
    """读取偏好包（全局 + 项目，项目优先），截最近内容到 max_chars。"""
    parts: list[str] = []
    if GLOBAL_MEMORY.exists():
        text = GLOBAL_MEMORY.read_text(encoding="utf-8").strip()
        if text:
            parts.append(text)
    project_path = Path(project_root) / MEMORY_FILENAME
    if project_path.exists():
        text = project_path.read_text(encoding="utf-8").strip()
        if text:
            parts.append(text)
    if not parts:
        return ""
    combined = "\n\n".join(parts)
    if len(combined) > max_chars:
        combined = "…(更早记录截断)\n" + combined[-max_chars:]
    return combined


def format_preferences_block(preferences: str) -> str:
    """渲染为 prompt 注入块；空偏好返回空串。"""
    if not preferences.strip():
        return ""
    return (
        "## 人类偏好记忆（历史评审沉淀——遵循；与默认原则冲突时以此为准）\n"
        + preferences.strip()
        + "\n"
    )
