from pathlib import Path
from typing import Any, Iterable, List, Optional
import mimetypes
import uuid

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from ..config import settings
from ..errors import AppError
from ..schemas import (
    DeleteResponse,
    ProjectCreateResponse,
    ProjectMeta,
    SafetyResponse,
    TracksResponse,
)
from ..services.archive_importer import safe_extract_zip
from ..services.cache import ProjectRecord, project_cache
from ..services.pyfii_adapter import parse_fii_project
from ..services.safety import analyze_safety
from ..services.serializer import (
    compute_duration_ms,
    compute_frame_count,
    serialize_project_meta,
    serialize_tracks,
)
from ..services.storage import cleanup_project, create_project_workspace


router = APIRouter()

ALLOWED_TRACK_FPS = {30, 60, 100, 200}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"}


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _music_roots(record: ProjectRecord) -> Iterable[Path]:
    music = record.music
    if isinstance(music, (list, tuple)) and music:
        root = Path(str(music[0]))
        if root.exists() and _is_relative_to(root, record.extract_dir):
            yield root
    yield record.project_dir / "动作组"
    yield record.project_dir


def _music_names(music: Any) -> List[str]:
    if isinstance(music, (list, tuple)):
        return [str(item) for item in music[1:] if str(item)]
    if music:
        return [str(music)]
    return []


def _find_music_file(record: ProjectRecord) -> Optional[Path]:
    names = _music_names(record.music)
    if not names:
        return None

    for name in names:
        direct = Path(name)
        if direct.exists() and direct.is_file() and _is_relative_to(direct, record.extract_dir):
            return direct

    for root in _music_roots(record):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            if not _is_relative_to(path, record.extract_dir):
                continue
            for name in names:
                if path.name == name or path.stem == Path(name).stem:
                    return path
    return None


@router.post("", response_model=ProjectCreateResponse)
async def create_project(
    file: UploadFile = File(...),
    fps: int = Form(settings.default_import_fps),
    ignore_acc: bool = Form(False),
) -> ProjectCreateResponse:
    if fps <= 0:
        raise AppError(400, "invalid_fps", "fps must be a positive integer.")
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise AppError(400, "invalid_archive", "Only .zip Fii project archives are supported.")

    project_id = uuid.uuid4().hex
    workspace = create_project_workspace(project_id)
    upload_path = workspace.upload_dir / Path(file.filename).name
    extract_dir = workspace.extract_dir

    try:
        with upload_path.open("wb") as target:
            uploaded_bytes = 0
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                uploaded_bytes += len(chunk)
                if uploaded_bytes > settings.max_upload_bytes:
                    raise AppError(
                        413,
                        "upload_too_large",
                        "Uploaded zip exceeds the configured size limit.",
                    )
                target.write(chunk)

        project_dir = safe_extract_zip(upload_path, extract_dir)
        parsed = parse_fii_project(project_dir, fps=fps, ignore_acc=ignore_acc)
        duration_ms = compute_duration_ms(parsed.data)
        frame_count = compute_frame_count(parsed.data)
        safety = analyze_safety(
            parsed.data,
            warnings=parsed.warnings,
            source_fps=fps,
            field=parsed.field,
            device=parsed.device,
        )
        meta = serialize_project_meta(
            project_id=project_id,
            name=Path(file.filename).stem,
            data=parsed.data,
            music=parsed.music,
            field=parsed.field,
            device=parsed.device,
            source_fps=fps,
            duration_ms=duration_ms,
            frame_count=frame_count,
            safety_summary=safety["summary"],
        )

        record = ProjectRecord(
            project_id=project_id,
            name=meta["name"],
            workspace_dir=workspace.root,
            upload_path=upload_path,
            extract_dir=extract_dir,
            project_dir=project_dir,
            data=parsed.data,
            t0=parsed.t0,
            music=parsed.music,
            field=parsed.field,
            device=parsed.device,
            warnings=parsed.warnings,
            stdout=parsed.stdout,
            source_fps=fps,
            duration_ms=duration_ms,
            frame_count=frame_count,
            meta=meta,
            safety_summary=safety["summary"],
            safety_events=safety["events"],
        )
        project_cache.set(record)
        return ProjectCreateResponse(**meta, warnings=parsed.warnings)
    except AppError:
        cleanup_project(project_id)
        raise
    except Exception as exc:
        cleanup_project(project_id)
        raise AppError(500, "project_import_failed", str(exc)) from exc
    finally:
        await file.close()


@router.get("/{project_id}", response_model=ProjectMeta)
async def get_project(project_id: str) -> ProjectMeta:
    record = project_cache.require(project_id)
    return ProjectMeta(**record.meta)


@router.get("/{project_id}/tracks", response_model=TracksResponse)
async def get_tracks(
    project_id: str,
    fps: int = Query(60),
) -> TracksResponse:
    if fps not in ALLOWED_TRACK_FPS:
        raise AppError(400, "invalid_track_fps", "fps must be one of 30, 60, 100, or 200.")
    record = project_cache.require(project_id)
    payload = serialize_tracks(
        record.data,
        project_id=project_id,
        fps=fps,
        source_fps=record.source_fps,
        duration_ms=record.duration_ms,
        field=record.field,
        device=record.device,
    )
    return TracksResponse(**payload)


@router.get("/{project_id}/safety", response_model=SafetyResponse)
async def get_safety(project_id: str) -> SafetyResponse:
    record = project_cache.require(project_id)
    return SafetyResponse(summary=record.safety_summary, events=record.safety_events)


@router.get("/{project_id}/music")
async def get_music(project_id: str) -> FileResponse:
    record = project_cache.require(project_id)
    music_path = _find_music_file(record)
    if music_path is None:
        raise AppError(404, "music_not_found", "Project music file was not found.")

    media_type = mimetypes.guess_type(music_path.name)[0] or "application/octet-stream"
    return FileResponse(music_path, media_type=media_type, filename=music_path.name)


@router.delete("/{project_id}", response_model=DeleteResponse)
async def delete_project(project_id: str) -> DeleteResponse:
    project_cache.delete(project_id)
    cleanup_project(project_id)
    return DeleteResponse(ok=True)
