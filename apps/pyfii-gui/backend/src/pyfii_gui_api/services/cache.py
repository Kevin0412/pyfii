from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

from ..errors import AppError


@dataclass
class ProjectRecord:
    project_id: str
    name: str
    workspace_dir: Path
    upload_path: Path
    extract_dir: Path
    project_dir: Path
    data: Any
    t0: Any
    music: Any
    field: Optional[int]
    device: Optional[str]
    warnings: List[str]
    stdout: str
    source_fps: int
    duration_ms: float
    frame_count: int
    meta: Dict[str, Any]
    safety_summary: Dict[str, Any]
    safety_events: List[Dict[str, Any]]


class ProjectCache:
    def __init__(self) -> None:
        self._records: Dict[str, ProjectRecord] = {}
        self._lock = RLock()

    def set(self, record: ProjectRecord) -> None:
        with self._lock:
            self._records[record.project_id] = record

    def get(self, project_id: str) -> Optional[ProjectRecord]:
        with self._lock:
            return self._records.get(project_id)

    def require(self, project_id: str) -> ProjectRecord:
        record = self.get(project_id)
        if record is None:
            raise AppError(404, "project_not_found", "Project was not found or has expired.")
        return record

    def delete(self, project_id: str) -> None:
        with self._lock:
            self._records.pop(project_id, None)


project_cache = ProjectCache()
