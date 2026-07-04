"""项目状态定义"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json


@dataclass
class SegmentState:
    id: str
    start_time: float
    end_time: float
    locked: bool = False
    music_cue: dict = field(default_factory=dict)
    intent: str = ""
    attempts: list = field(default_factory=list)
    final_permutation: Optional[tuple] = None
    exit_state: Optional[list] = None
    degradation_signature: Optional[str] = None  # 退化指纹，跨段去重用
    locked_hash: str = ""  # 锁定时段体哈希：检测人工改动锁定段
    last_agent_hash: str = ""  # agent 最后写入的段体哈希：g 覆盖前检测人工修改
    design_card: dict = field(default_factory=dict)  # 锁定时的设计卡：供下一段承接母题


@dataclass
class ProjectState:
    name: str = ""
    music_path: str = ""
    music_duration: float = 0.0
    music_confirmed: bool = False
    mode: str = "manual"  # manual | fast
    provider: str = "deepseek"
    drone_count: int = 7
    composition_plan: dict = field(default_factory=dict)
    last_run: dict = field(default_factory=dict)
    segments: list[SegmentState] = field(default_factory=list)
    current_segment_index: int = 0
    locked_segment_ids: list[str] = field(default_factory=list)

    @property
    def current_segment(self) -> Optional[SegmentState]:
        if 0 <= self.current_segment_index < len(self.segments):
            return self.segments[self.current_segment_index]
        return None

    def save(self, project_root: Path) -> None:
        data = {
            "name": self.name,
            "music_path": self.music_path,
            "music_duration": self.music_duration,
            "music_confirmed": self.music_confirmed,
            "mode": self.mode,
            "provider": self.provider,
            "drone_count": self.drone_count,
            "composition_plan": self.composition_plan,
            "last_run": self.last_run,
            "segments": [
                {
                    "id": s.id,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "locked": s.locked,
                    "music_cue": s.music_cue,
                    "intent": s.intent,
                    "attempts": s.attempts,
                    "exit_state": s.exit_state,
                    "degradation_signature": s.degradation_signature,
                    "locked_hash": s.locked_hash,
                    "last_agent_hash": s.last_agent_hash,
                    "design_card": s.design_card,
                }
                for s in self.segments
            ],
            "current_segment_index": self.current_segment_index,
            "locked_segment_ids": self.locked_segment_ids,
        }
        path = project_root / "state.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    @classmethod
    def load(cls, project_root: Path) -> "ProjectState":
        path = project_root / "state.json"
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        segments = [
            SegmentState(
                id=s["id"],
                start_time=s["start_time"],
                end_time=s["end_time"],
                locked=s.get("locked", False),
                music_cue=s.get("music_cue", {}),
                intent=s.get("intent", ""),
                attempts=s.get("attempts", []),
                exit_state=s.get("exit_state"),
                degradation_signature=s.get("degradation_signature"),
                locked_hash=s.get("locked_hash", ""),
                last_agent_hash=s.get("last_agent_hash", ""),
                design_card=s.get("design_card") or {},
            )
            for s in data.get("segments", [])
        ]
        return cls(
            name=data.get("name", ""),
            music_path=data.get("music_path", ""),
            music_duration=data.get("music_duration", 0.0),
            music_confirmed=data.get("music_confirmed", False),
            mode=_normalize_mode(data.get("mode", "manual")),
            provider=data.get("provider", "deepseek"),
            drone_count=_normalize_drone_count(data.get("drone_count", 7)),
            composition_plan=_normalize_composition_plan(data.get("composition_plan", {})),
            last_run=_normalize_dict(data.get("last_run", {})),
            segments=segments,
            current_segment_index=data.get("current_segment_index", 0),
            locked_segment_ids=data.get("locked_segment_ids", []),
        )


def _normalize_mode(mode: str) -> str:
    value = str(mode).strip().lower()
    if value in {"fast", "quick", "auto", "快速", "快速模式"}:
        return "fast"
    return "manual"


def _normalize_drone_count(value) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 7
    return max(1, count)


def _normalize_composition_plan(value) -> dict:
    return _normalize_dict(value)


def _normalize_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    return {}
