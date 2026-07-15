from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient

from pyfii_gui_api.main import app
from pyfii_gui_api.errors import AppError
from pyfii_gui_api.services.bounded_executor import ExecutorBusy
from pyfii_gui_api.services.cache import ProjectRecord, project_cache
from pyfii_gui_api.services.storage import ProjectWorkspace
from pyfii_gui_api.services.video_export import VideoExportRecord


def project_record() -> ProjectRecord:
    path = Path("/tmp/project")
    return ProjectRecord(
        project_id="api-project",
        name="API project",
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
        duration_ms=1000,
        frame_count=60,
        meta={},
        safety_summary={},
        safety_events=[],
    )


class GuiApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        project_cache.set(project_record())

    def tearDown(self):
        project_cache.delete("api-project")

    def test_invalid_archive_is_a_fatal_api_error(self):
        response = self.client.post(
            "/api/projects",
            files={"file": ("not-a-project.txt", b"invalid", "text/plain")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_archive")

    def test_delete_requires_an_existing_project(self):
        with patch("pyfii_gui_api.routers.projects.cleanup_project") as cleanup:
            response = self.client.delete("/api/projects/not-a-project")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "project_not_found")
        cleanup.assert_not_called()

    def test_delete_rejects_encoded_parent_path(self):
        with patch("pyfii_gui_api.routers.projects.cleanup_project") as cleanup:
            response = self.client.delete("/api/projects/%2e%2e")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "project_not_found")
        cleanup.assert_not_called()

    def test_creates_asynchronous_video_export(self):
        export = VideoExportRecord(
            export_id="export-1",
            project_id="api-project",
            filename="API_project.mp4",
            output_path=Path("/tmp/API_project.mp4"),
        )
        with patch(
            "pyfii_gui_api.routers.projects.video_export_manager.create",
            return_value=export,
        ):
            response = self.client.post(
                "/api/projects/api-project/video-exports",
                json={"render_mode": "three3d", "fps": 30},
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "queued")
        self.assertIsNone(response.json()["download_url"])

    def test_project_import_returns_structured_429_when_busy(self):
        with TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir) / "project"
            workspace = ProjectWorkspace(
                root=root,
                upload_dir=root / "upload",
                extract_dir=root / "extracted",
            )
            workspace.upload_dir.mkdir(parents=True)
            workspace.extract_dir.mkdir()
            with (
                patch(
                    "pyfii_gui_api.routers.projects.create_project_workspace",
                    return_value=workspace,
                ),
                patch("pyfii_gui_api.routers.projects.cleanup_project") as cleanup,
                patch(
                    "pyfii_gui_api.routers.projects.project_executor.submit",
                    side_effect=ExecutorBusy,
                ),
            ):
                response = self.client.post(
                    "/api/projects",
                    files={"file": ("project.zip", b"zip", "application/zip")},
                )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "project_import_busy")
        self.assertIn("max_running", response.json()["error"]["details"])
        self.assertIn("max_queued", response.json()["error"]["details"])
        cleanup.assert_called_once()

    def test_track_serialization_returns_structured_429_when_busy(self):
        with patch(
            "pyfii_gui_api.routers.projects.project_executor.submit",
            side_effect=ExecutorBusy,
        ):
            response = self.client.get("/api/projects/api-project/tracks?fps=60")

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "project_processing_busy")
        self.assertIn("max_running", response.json()["error"]["details"])
        self.assertIn("max_queued", response.json()["error"]["details"])

    def test_video_export_returns_structured_429_when_busy(self):
        busy = AppError(
            429,
            "video_export_busy",
            "Video export capacity is full. Try again later.",
            {"max_running": 1, "max_queued": 0},
        )
        with patch(
            "pyfii_gui_api.routers.projects.video_export_manager.create",
            side_effect=busy,
        ):
            response = self.client.post(
                "/api/projects/api-project/video-exports",
                json={"render_mode": "three3d", "fps": 30},
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "video_export_busy")
        self.assertEqual(
            response.json()["error"]["details"],
            {"max_running": 1, "max_queued": 0},
        )

    def test_rejects_download_before_export_is_complete(self):
        export = VideoExportRecord(
            export_id="export-1",
            project_id="api-project",
            filename="API_project.mp4",
            output_path=Path("/tmp/API_project.mp4"),
            status="running",
            progress_percent=None,
        )
        with patch(
            "pyfii_gui_api.routers.projects.video_export_manager.require",
            return_value=export,
        ):
            response = self.client.get(
                "/api/projects/api-project/video-exports/export-1/download"
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "video_export_not_ready")

    def test_validates_video_export_parameters(self):
        response = self.client.post(
            "/api/projects/api-project/video-exports",
            json={"fps": 120},
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
