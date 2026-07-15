import asyncio
import logging
import re
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from threading import RLock
from typing import AsyncIterator, Optional, Set

from fastapi import FastAPI

from ..config import settings
from .cache import project_cache
from .storage import cleanup_project
from .video_export import video_export_manager


logger = logging.getLogger(__name__)
project_lifecycle_lock = RLock()
_PROJECT_ID = re.compile(r"^(?:local_)?[0-9a-f]{32}$")


def _orphan_project_ids(root: Path, cached_ids: Set[str], cutoff: float) -> Set[str]:
    """Find old runtime directories that no in-memory project owns."""

    mtimes: dict[str, float] = {}
    for parent in (root, root / "_video_exports"):
        if parent.is_symlink() or not parent.is_dir():
            continue
        for path in parent.iterdir():
            if not _PROJECT_ID.fullmatch(path.name) or path.is_symlink() or not path.is_dir():
                continue
            try:
                mtimes[path.name] = max(mtimes.get(path.name, 0.0), path.stat().st_mtime)
            except OSError:
                continue
    return {
        project_id
        for project_id, modified_at in mtimes.items()
        if project_id not in cached_ids and modified_at <= cutoff
    }


def cleanup_expired_runtime(now: Optional[float] = None) -> list[str]:
    """Delete expired projects and stale runtime directories once."""

    ttl = settings.project_ttl_seconds
    if ttl <= 0:
        return []

    current_time = time.time() if now is None else now
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    runtime_root = settings.runtime_dir.resolve()
    removed: list[str] = []

    with project_lifecycle_lock:
        cached_ids = set(project_cache.project_ids())
        candidates = set(project_cache.expired_project_ids(ttl, current_time))
        candidates.update(
            _orphan_project_ids(runtime_root, cached_ids, current_time - ttl)
        )

        for project_id in sorted(candidates):
            if video_export_manager.has_active_project(project_id):
                continue

            cached_record = None
            if project_id in cached_ids:
                cached_record = project_cache.take_if_expired(project_id, ttl, current_time)
                if cached_record is None:
                    continue

            try:
                cleanup_project(project_id)
                video_export_manager.delete_project(project_id)
                removed.append(project_id)
            except (OSError, ValueError):
                if cached_record is not None:
                    project_cache.set(cached_record)
                logger.exception("Failed to clean expired GUI project %s", project_id)

    if removed:
        logger.info("Cleaned %d expired GUI project(s)", len(removed))
    return removed


async def _cleanup_loop() -> None:
    while True:
        await asyncio.sleep(settings.runtime_cleanup_interval_seconds)
        try:
            await asyncio.to_thread(cleanup_expired_runtime)
        except Exception:
            logger.exception("Failed to scan the GUI runtime directory")


@asynccontextmanager
async def runtime_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Clean stale runtime data at startup and periodically while serving."""

    del app
    await asyncio.to_thread(cleanup_expired_runtime)
    cleanup_task = None
    if settings.project_ttl_seconds > 0:
        cleanup_task = asyncio.create_task(_cleanup_loop())
    try:
        yield
    finally:
        if cleanup_task is not None:
            cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup_task
