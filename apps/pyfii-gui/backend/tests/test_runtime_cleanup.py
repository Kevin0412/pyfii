import asyncio
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pyfii_gui_api.services.cache import ProjectCache, ProjectRecord, project_cache
from pyfii_gui_api.services.runtime_cleanup import cleanup_expired_runtime, runtime_lifespan
from pyfii_gui_api.config import settings


def project_record(project_id: str, root: Path) -> ProjectRecord:
    return ProjectRecord(
        project_id=project_id,
        name="runtime project",
        workspace_dir=root,
        upload_path=root,
        extract_dir=root,
        project_dir=root,
        data=[],
        t0=0,
        music=[],
        field=6,
        device="F400",
        warnings=[],
        stdout="",
        source_fps=60,
        duration_ms=0,
        frame_count=0,
        meta={},
        safety_summary={},
        safety_events=[],
    )


class ProjectCacheExpiryTests(unittest.TestCase):
    def test_access_extends_project_lifetime(self):
        cache = ProjectCache()
        record = project_record("a" * 32, Path("/tmp/cache-project"))

        with patch("pyfii_gui_api.services.cache.time.time", return_value=100.0):
            cache.set(record)
        with patch("pyfii_gui_api.services.cache.time.time", return_value=105.0):
            self.assertIs(cache.require(record.project_id), record)

        self.assertEqual(cache.expired_project_ids(10, now=114.0), [])
        self.assertEqual(cache.expired_project_ids(10, now=115.0), [record.project_id])


class RuntimeCleanupTests(unittest.TestCase):
    def test_removes_only_old_orphan_directories(self):
        old_id = "1" * 32
        fresh_id = "2" * 32
        with TemporaryDirectory() as temporary_dir:
            runtime = Path(temporary_dir) / "projects"
            old_root = runtime / old_id
            old_export = runtime / "_video_exports" / old_id
            fresh_root = runtime / fresh_id
            old_root.mkdir(parents=True)
            old_export.mkdir(parents=True)
            fresh_root.mkdir()
            os.utime(old_root, (100.0, 100.0))
            os.utime(old_export, (100.0, 100.0))
            os.utime(fresh_root, (195.0, 195.0))

            with (
                patch.object(settings, "runtime_dir", runtime),
                patch.object(settings, "project_ttl_seconds", 50),
            ):
                removed = cleanup_expired_runtime(now=200.0)

            self.assertEqual(removed, [old_id])
            self.assertFalse(old_root.exists())
            self.assertFalse(old_export.exists())
            self.assertTrue(fresh_root.is_dir())

    def test_skips_expired_project_while_video_export_is_active(self):
        project_id = "3" * 32
        with TemporaryDirectory() as temporary_dir:
            runtime = Path(temporary_dir) / "projects"
            root = runtime / project_id
            root.mkdir(parents=True)
            os.utime(root, (100.0, 100.0))
            with patch("pyfii_gui_api.services.cache.time.time", return_value=100.0):
                project_cache.set(project_record(project_id, root))

            try:
                with (
                    patch.object(settings, "runtime_dir", runtime),
                    patch.object(settings, "project_ttl_seconds", 50),
                    patch(
                        "pyfii_gui_api.services.runtime_cleanup."
                        "video_export_manager.has_active_project",
                        return_value=True,
                    ),
                ):
                    removed = cleanup_expired_runtime(now=200.0)

                self.assertEqual(removed, [])
                self.assertTrue(root.is_dir())
                self.assertIsNotNone(project_cache.get(project_id))
            finally:
                project_cache.delete(project_id)

    def test_removes_expired_cached_project(self):
        project_id = "4" * 32
        with TemporaryDirectory() as temporary_dir:
            runtime = Path(temporary_dir) / "projects"
            root = runtime / project_id
            root.mkdir(parents=True)
            with patch("pyfii_gui_api.services.cache.time.time", return_value=100.0):
                project_cache.set(project_record(project_id, root))

            try:
                with (
                    patch.object(settings, "runtime_dir", runtime),
                    patch.object(settings, "project_ttl_seconds", 50),
                ):
                    removed = cleanup_expired_runtime(now=200.0)

                self.assertEqual(removed, [project_id])
                self.assertIsNone(project_cache.get(project_id))
                self.assertFalse(root.exists())
            finally:
                project_cache.delete(project_id)

    def test_lifespan_runs_startup_cleanup_in_a_worker_thread(self):
        async def exercise() -> None:
            with (
                patch.object(settings, "project_ttl_seconds", 0),
                patch(
                    "pyfii_gui_api.services.runtime_cleanup.cleanup_expired_runtime"
                ) as cleanup,
            ):
                async with runtime_lifespan(object()):
                    pass
                cleanup.assert_called_once_with()

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
