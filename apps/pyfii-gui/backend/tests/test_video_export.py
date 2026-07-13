from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from unittest.mock import patch
import unittest

from pyfii_gui_api.schemas import VideoExportRequest
from pyfii_gui_api.services.cache import ProjectRecord
from pyfii_gui_api.services.video_export import VideoExportManager


def project_record() -> ProjectRecord:
    path = Path("/tmp/project")
    return ProjectRecord(
        project_id="project-1",
        name="测试 project",
        workspace_dir=path,
        upload_path=path,
        extract_dir=path,
        project_dir=path,
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


def wait_until_finished(manager: VideoExportManager, export_id: str):
    deadline = monotonic() + 3
    while monotonic() < deadline:
        record = manager.require("project-1", export_id)
        if record.status in {"completed", "failed"}:
            return record
        sleep(0.01)
    raise AssertionError("video export did not finish")


class VideoExportManagerTests(unittest.TestCase):
    def test_completes_export_and_exposes_download(self):
        with TemporaryDirectory() as temporary_dir:
            output_root = Path(temporary_dir)

            def render(_project, _options, output_path):
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(b"mp4")
                return output_path

            manager = VideoExportManager(max_workers=1, render_video=render)
            with patch(
                "pyfii_gui_api.services.video_export.video_export_root",
                return_value=output_root,
            ):
                export = manager.create(project_record(), VideoExportRequest())
                finished = wait_until_finished(manager, export.export_id)

            response = finished.as_response()
            self.assertEqual(finished.status, "completed")
            self.assertEqual(finished.progress_percent, 100.0)
            self.assertTrue(finished.output_path.is_file())
            self.assertEqual(
                response["download_url"],
                f"/api/projects/project-1/video-exports/{export.export_id}/download",
            )

    def test_failed_render_is_reported_without_download(self):
        def render(_project, _options, _output_path):
            raise RuntimeError("codec unavailable")

        manager = VideoExportManager(max_workers=1, render_video=render)
        export = manager.create(project_record(), VideoExportRequest())
        finished = wait_until_finished(manager, export.export_id)

        self.assertEqual(finished.status, "failed")
        self.assertEqual(finished.error, "codec unavailable")
        self.assertIsNone(finished.as_response()["download_url"])


if __name__ == "__main__":
    unittest.main()
