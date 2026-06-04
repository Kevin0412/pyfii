#!/usr/bin/env python3
"""Print token usage and CNY price estimates for a choreo_agent project."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_ROOT))

from core.token_usage import summarize_usage


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    project_root = _resolve_project(args.project)
    items = _usage_items(project_root)
    summary = summarize_usage(items)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _usage_items(project_root: Path) -> list[dict]:
    state_items = _items_from_state(project_root / "state.json")
    if state_items:
        return state_items
    return _items_from_stability_result(project_root / "stability_result.json")


def _items_from_state(path: Path) -> list[dict]:
    if not path.exists():
        return []
    state = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for segment in state.get("segments", []):
        for attempt in segment.get("attempts", []):
            if not _looks_like_llm_attempt(attempt):
                continue
            item = dict(attempt)
            item["segment"] = segment.get("id")
            items.append(item)
    return items


def _items_from_stability_result(path: Path) -> list[dict]:
    if not path.exists():
        return []
    result = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for segment in result.get("summary", {}).get("records", []):
        for cycle in segment.get("cycles", []):
            for round_item in cycle.get("rounds", []):
                items.append(round_item)
    return items


def _looks_like_llm_attempt(attempt: dict) -> bool:
    fields = {
        "input_tokens",
        "output_tokens",
        "estimated_input_tokens",
        "estimated_output_tokens",
        "response_chars",
        "reasoning_chars",
    }
    return bool(fields & set(attempt))


def _resolve_project(project: str) -> Path:
    path = Path(project)
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="Path to an agent project directory")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
