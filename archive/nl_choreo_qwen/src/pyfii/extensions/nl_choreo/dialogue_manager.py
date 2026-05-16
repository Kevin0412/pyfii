# -*- coding: utf-8 -*-
# 该文件负责管理多轮人机对话编辑记录

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DialogueTurn:
    # 对话轮次结构：记录用户自然语言编辑及系统处理结果
    turn_id: int
    user_edit_text: str
    affected_segments: list[str]
    patch_summary: str
    safety_result: str
    render_refs: list[str]


class DialogueManager:
    # 对话管理器：以 jsonl 持久化轮次历史
    def __init__(self, history_path: str | Path):
        self.history_path = Path(history_path)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

    def append_turn(self, turn: DialogueTurn) -> None:
        # 追加单轮记录，便于审计与回溯
        payload = {
            "turn_id": turn.turn_id,
            "user_edit_text": turn.user_edit_text,
            "affected_segments": turn.affected_segments,
            "patch_summary": turn.patch_summary,
            "safety_result": turn.safety_result,
            "render_refs": turn.render_refs,
        }
        with self.history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False))
            f.write("\n")

    def load_turns(self) -> list[dict[str, Any]]:
        # 读取全部历史轮次
        if not self.history_path.exists():
            return []
        turns: list[dict[str, Any]] = []
        with self.history_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    turns.append(json.loads(line))
        return turns
