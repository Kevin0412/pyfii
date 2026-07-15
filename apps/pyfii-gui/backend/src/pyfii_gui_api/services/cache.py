from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional
import time

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
        self._last_accessed: Dict[str, float] = {}
        self._lock = RLock()

    def set(self, record: ProjectRecord) -> None:
        with self._lock:
            self._records[record.project_id] = record
            self._last_accessed[record.project_id] = time.time()

    def get(self, project_id: str) -> Optional[ProjectRecord]:
        with self._lock:
            record = self._records.get(project_id)
            if record is not None:
                self._last_accessed[project_id] = time.time()
            return record

    def require(self, project_id: str) -> ProjectRecord:
        record = self.get(project_id)
        if record is None:
            raise AppError(404, "project_not_found", "Project was not found or has expired.")
        return record

    def delete(self, project_id: str) -> None:
        with self._lock:
            self._records.pop(project_id, None)
            self._last_accessed.pop(project_id, None)

    def project_ids(self) -> List[str]:
        """Return cached IDs without extending their lifetime."""

        with self._lock:
            return list(self._records)

    def expired_project_ids(
        self,
        ttl_seconds: int,
        now: Optional[float] = None,
    ) -> List[str]:
        """Return cached projects that have not been used within the TTL."""

        if ttl_seconds <= 0:
            return []
        cutoff = (time.time() if now is None else now) - ttl_seconds
        with self._lock:
            return [
                project_id
                for project_id, accessed_at in self._last_accessed.items()
                if accessed_at <= cutoff
            ]

    def take_if_expired(
        self,
        project_id: str,
        ttl_seconds: int,
        now: Optional[float] = None,
    ) -> Optional[ProjectRecord]:
        """Atomically remove and return a project only when its TTL elapsed."""

        if ttl_seconds <= 0:
            return None
        cutoff = (time.time() if now is None else now) - ttl_seconds
        with self._lock:
            accessed_at = self._last_accessed.get(project_id)
            if accessed_at is None or accessed_at > cutoff:
                return None
            self._last_accessed.pop(project_id, None)
            return self._records.pop(project_id, None)


project_cache = ProjectCache()
