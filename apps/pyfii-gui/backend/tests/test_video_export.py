from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch
import unittest

from pyfii_gui_api.errors import AppError
from pyfii_gui_api.schemas import VideoExportRequest
from pyfii_gui_api.services.cache import ProjectRecord
from pyfii_gui_api.services.video_export import VideoExportManager, render_project_video


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
    def test_maps_ssaa_to_core_supersampling(self):
        with TemporaryDirectory() as temporary_dir:
            output_path = Path(temporary_dir) / "render.mp4"

            with (
                patch("pyfii.fiiRead.DroneTrack"),
                patch("pyfii.fiiRead.FiiRender2D") as render_class,
                patch("pyfii.fiiRead.FiiRender3D"),
            ):
                renderer = render_class.return_value
                renderer.save.side_effect = lambda stem: Path(stem + ".mp4").write_bytes(b"mp4")
                render_project_video(
                    project_record(),
                    VideoExportRequest(ssaa=4),
                    output_path,
                    lambda _completed, _total: None,
                )

            config = render_class.call_args.args[1]
            self.assertEqual(config["size"], 4)
            self.assertEqual(config["ssaa"], 4)

    def test_legacy_render_scale_is_accepted_as_ssaa(self):
        options = VideoExportRequest.model_validate({"render_scale": 2})
        self.assertEqual(options.ssaa, 2)
        self.assertEqual(options.model_dump()["ssaa"], 2)
        self.assertNotIn("render_scale", options.model_dump())

    def test_completes_export_and_exposes_download(self):
        with TemporaryDirectory() as temporary_dir:
            output_root = Path(temporary_dir)

            def render(_project, _options, output_path, _progress):
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
        def render(_project, _options, _output_path, _progress):
            raise RuntimeError("codec unavailable")

        manager = VideoExportManager(max_workers=1, render_video=render)
        export = manager.create(project_record(), VideoExportRequest())
        finished = wait_until_finished(manager, export.export_id)

        self.assertEqual(finished.status, "failed")
        self.assertEqual(finished.error, "codec unavailable")
        self.assertIsNone(finished.as_response()["download_url"])

    def test_reports_real_frame_progress_before_finalizing(self):
        progress_reported = Event()
        allow_completion = Event()

        def render(_project, _options, output_path, progress):
            progress(1, 2)
            progress_reported.set()
            allow_completion.wait(timeout=1)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"mp4")
            return output_path

        manager = VideoExportManager(max_workers=1, render_video=render)
        export = manager.create(project_record(), VideoExportRequest())

        self.assertTrue(progress_reported.wait(timeout=1))
        running = manager.require("project-1", export.export_id)
        self.assertEqual(running.status, "running")
        self.assertEqual(running.progress_percent, 47.5)

        allow_completion.set()
        finished = wait_until_finished(manager, export.export_id)
        self.assertEqual(finished.progress_percent, 100.0)

    def test_rejects_export_when_configured_capacity_is_full(self):
        started = Event()
        allow_completion = Event()

        def render(_project, _options, output_path, _progress):
            started.set()
            allow_completion.wait(timeout=2)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"mp4")
            return output_path

        with TemporaryDirectory() as temporary_dir:
            manager = VideoExportManager(
                max_workers=1,
                max_queue_size=0,
                render_video=render,
            )
            with patch(
                "pyfii_gui_api.services.video_export.video_export_root",
                return_value=Path(temporary_dir),
            ):
                first = manager.create(project_record(), VideoExportRequest())
                self.assertTrue(started.wait(timeout=1))

                try:
                    with self.assertRaises(AppError) as raised:
                        manager.create(project_record(), VideoExportRequest())
                    self.assertEqual(raised.exception.status_code, 429)
                    self.assertEqual(raised.exception.code, "video_export_busy")
                    self.assertEqual(
                        raised.exception.details,
                        {"max_running": 1, "max_queued": 0},
                    )
                finally:
                    allow_completion.set()

                self.assertEqual(
                    wait_until_finished(manager, first.export_id).status,
                    "completed",
                )

    def test_rejects_project_deletion_while_export_is_running(self):
        started = Event()
        allow_completion = Event()

        def render(_project, _options, output_path, _progress):
            started.set()
            allow_completion.wait(timeout=2)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"mp4")
            return output_path

        with TemporaryDirectory() as temporary_dir:
            manager = VideoExportManager(max_workers=1, render_video=render)
            with patch(
                "pyfii_gui_api.services.video_export.video_export_root",
                return_value=Path(temporary_dir),
            ):
                export = manager.create(project_record(), VideoExportRequest())
                self.assertTrue(started.wait(timeout=1))

                try:
                    with self.assertRaises(AppError) as raised:
                        manager.delete_project("project-1")
                    self.assertEqual(raised.exception.status_code, 409)
                    self.assertEqual(raised.exception.code, "video_export_active")
                finally:
                    allow_completion.set()

                self.assertEqual(
                    wait_until_finished(manager, export.export_id).status,
                    "completed",
                )


if __name__ == "__main__":
    unittest.main()
