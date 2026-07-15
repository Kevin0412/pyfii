from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Callable, Dict, List, Optional
import contextlib
import io
import re
import uuid
import warnings

from ..config import settings
from ..errors import AppError
from ..schemas import VideoExportRequest
from .cache import ProjectRecord
from .storage import video_export_root


RenderProgress = Callable[[int, int], None]
RenderVideo = Callable[[ProjectRecord, VideoExportRequest, Path, RenderProgress], Path]


@dataclass
class VideoExportRecord:
    export_id: str
    project_id: str
    filename: str
    output_path: Path
    status: str = "queued"
    progress_percent: Optional[float] = 0.0
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def as_response(self) -> Dict[str, object]:
        download_url = None
        if self.status == "completed":
            download_url = (
                f"/api/projects/{self.project_id}/video-exports/"
                f"{self.export_id}/download"
            )
        return {
            "export_id": self.export_id,
            "project_id": self.project_id,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "filename": self.filename,
            "download_url": download_url,
            "warnings": list(self.warnings),
            "error": self.error,
        }


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\-.\u4e00-\u9fff]+", "_", name, flags=re.UNICODE).strip("._")
    return (cleaned or "pyfii-video") + ".mp4"


def render_project_video(
    project: ProjectRecord,
    options: VideoExportRequest,
    output_path: Path,
    progress_callback: RenderProgress,
) -> Path:
    """Adapt a GUI project record to the current PyFii core renderers."""

    from pyfii.fiiRead import DroneTrack, FiiRender2D, FiiRender3D

    track = DroneTrack(
        project.data,
        project.t0,
        project.music,
        project.field,
        project.device,
    )

    projection = (
        (1, 0)
        if options.projection == "orthographic"
        else (options.observer_distance, options.projection_distance)
    )
    ssaa = options.ssaa if options.render_mode == "classic2d" else 1
    config = {
        "FPS": options.fps,
        "max_fps": project.source_fps,
        "size": ssaa,
        "ssaa": ssaa,
        "imshow": [options.view_angle_a, options.view_angle_b],
        "d": projection,
        "progress": False,
        "workers": settings.video_render_workers,
    }
    renderer = (
        FiiRender3D(track, config, progress_callback=progress_callback)
        if options.render_mode == "three3d"
        else FiiRender2D(track, config, progress_callback=progress_callback)
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_stem = output_path.with_suffix("")
    renderer.save(str(output_stem))
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("PyFii renderer did not produce an MP4 file.")
    return output_path


class VideoExportManager:
    def __init__(
        self,
        max_workers: int,
        render_video: RenderVideo = render_project_video,
    ) -> None:
        self._records: Dict[str, VideoExportRecord] = {}
        self._lock = RLock()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="pyfii-video",
        )
        self._render_video = render_video

    def create(
        self,
        project: ProjectRecord,
        options: VideoExportRequest,
    ) -> VideoExportRecord:
        export_id = uuid.uuid4().hex
        filename = _safe_filename(project.name)
        output_path = video_export_root(project.project_id) / export_id / filename
        record = VideoExportRecord(
            export_id=export_id,
            project_id=project.project_id,
            filename=filename,
            output_path=output_path,
        )
        with self._lock:
            self._records[export_id] = record
        self._executor.submit(self._run, export_id, project, options)
        return record

    def _run(
        self,
        export_id: str,
        project: ProjectRecord,
        options: VideoExportRequest,
    ) -> None:
        record = self.require(project.project_id, export_id)
        with self._lock:
            record.status = "running"
            record.progress_percent = 0.0

        def report_progress(completed: int, total: int) -> None:
            frame_fraction = completed / total if total > 0 else 0.0
            with self._lock:
                record.progress_percent = round(max(0.0, min(1.0, frame_fraction)) * 95, 1)

        captured_stdout = io.StringIO()
        try:
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                with contextlib.redirect_stdout(captured_stdout):
                    self._render_video(
                        project,
                        options,
                        record.output_path,
                        report_progress,
                    )
            unique_warnings = list(dict.fromkeys(str(item.message) for item in captured))
            with self._lock:
                record.status = "completed"
                record.progress_percent = 100.0
                record.warnings = unique_warnings
        except Exception as exc:
            for path in (record.output_path, record.output_path.with_name(record.output_path.stem + "_process.mp4")):
                path.unlink(missing_ok=True)
            with self._lock:
                record.status = "failed"
                record.progress_percent = None
                record.error = str(exc) or type(exc).__name__

    def require(self, project_id: str, export_id: str) -> VideoExportRecord:
        with self._lock:
            record = self._records.get(export_id)
        if record is None or record.project_id != project_id:
            raise AppError(404, "video_export_not_found", "Video export was not found or has expired.")
        return record

    def delete_project(self, project_id: str) -> None:
        with self._lock:
            export_ids = [
                export_id
                for export_id, record in self._records.items()
                if record.project_id == project_id
            ]
            for export_id in export_ids:
                self._records.pop(export_id, None)


video_export_manager = VideoExportManager(settings.video_export_jobs)
