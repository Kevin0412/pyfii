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


@dataclass
class ProjectState:
    name: str = ""
    music_path: str = ""
    music_duration: float = 0.0
    music_confirmed: bool = False
    mode: str = "safe"  # safe | fast
    provider: str = "deepseek"
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
            )
            for s in data.get("segments", [])
        ]
        return cls(
            name=data.get("name", ""),
            music_path=data.get("music_path", ""),
            music_duration=data.get("music_duration", 0.0),
            music_confirmed=data.get("music_confirmed", False),
            mode=data.get("mode", "safe"),
            provider=data.get("provider", "deepseek"),
            segments=segments,
            current_segment_index=data.get("current_segment_index", 0),
            locked_segment_ids=data.get("locked_segment_ids", []),
        )
