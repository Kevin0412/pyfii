"""持久会话历史：段级、纯函数风格（对齐 design_memory.py/directive_advisor.py 的既有风格）。

chat() 本身是无状态单轮调用（core/llm_client.py），不带任何历史——这里的 `turns` 列表
（持久在 SegmentState.conversation 上，见 core/state.py）才是让模型看到"自己上一轮实际
写了什么"的唯一渠道。`to_messages()` 把它转成喂给 chat(history=...) 的 role/content 列表；
其余字段（stage/meta）只是段内记录，不发给模型。
"""

from __future__ import annotations


def limit_text(text: str, max_chars: int) -> str:
    text = text or ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... <truncated {len(text) - max_chars} chars>"


def _append(turns: list, role: str, content: str, stage: str, meta: dict | None) -> None:
    if turns and turns[-1].get("role") == role:
        # 严格交替是 Anthropic Messages API 的硬要求（OpenAI 风格更宽松，但共享同一份
        # turns 就要按更严的那个来）。正常路径下 user/assistant 总是成对追加，不会撞上
        # 这一支——只有异常/重试路径漏掉配对调用时才会触发，合并而不是破坏交替或报错
        # 中断一次可能跑了几十分钟的生成。
        turns[-1]["content"] = str(turns[-1].get("content", "")) + "\n\n" + content
        if meta:
            turns[-1].setdefault("meta", {}).update(meta)
        return
    turn: dict = {"role": role, "content": content, "stage": stage}
    if meta:
        turn["meta"] = meta
    turns.append(turn)


def append_user(turns: list, content: str, stage: str, meta: dict | None = None) -> None:
    _append(turns, "user", content, stage, meta)


def append_assistant(turns: list, content: str, stage: str, meta: dict | None = None) -> None:
    _append(turns, "assistant", content, stage, meta)


def to_messages(turns: list) -> list[dict]:
    """喂给 llm_client.chat(history=...) 的 role/content 列表——不带 stage/meta。"""
    return [{"role": t["role"], "content": t["content"]} for t in turns]


def total_chars(turns: list) -> int:
    return sum(len(str(t.get("content", ""))) for t in turns)


def reset(turns: list) -> None:
    """原地清空。只应在段内允许的重置点调用（scheme reset）——段边界重置不需要它，
    新段的 SegmentState.conversation 本来就是空列表。"""
    turns.clear()


def format_debug_transcript(turns: list, max_chars: int = 4000) -> str:
    """人类可读的会话记录 dump，供 REPL 只读命令/调试使用。"""
    if not turns:
        return "(空会话)"
    lines = []
    for i, turn in enumerate(turns, 1):
        role = turn.get("role", "?")
        stage = turn.get("stage", "")
        content = str(turn.get("content", ""))
        lines.append(f"--- turn {i} [{role}/{stage}] ---\n{limit_text(content, 800)}")
    return limit_text("\n\n".join(lines), max_chars)
