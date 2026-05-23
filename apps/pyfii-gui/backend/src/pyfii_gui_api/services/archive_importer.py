from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile

from ..config import settings
from ..errors import AppError


def _is_zip_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0o170000
    return stat.S_ISLNK(mode)


def _member_name(info: zipfile.ZipInfo) -> str:
    if info.flag_bits & 0x800:
        return info.filename

    try:
        raw_name = info.filename.encode("cp437")
    except UnicodeEncodeError:
        return info.filename

    for encoding in ("utf-8", "gbk"):
        try:
            return raw_name.decode(encoding)
        except UnicodeDecodeError:
            continue
    return info.filename


def _target_for_member(destination: Path, member_name: str) -> Path:
    if "\\" in member_name:
        raise AppError(400, "unsafe_zip_member", "Zip entries may not contain backslash paths.")

    posix_path = PurePosixPath(member_name)
    if posix_path.is_absolute() or any(part in ("", ".", "..") for part in posix_path.parts):
        raise AppError(400, "unsafe_zip_member", "Zip archive contains an unsafe path.")

    target = destination.joinpath(*posix_path.parts)
    destination_root = destination.resolve(strict=False)
    target_path = target.resolve(strict=False)
    try:
        target_path.relative_to(destination_root)
    except ValueError as exc:
        raise AppError(400, "unsafe_zip_member", "Zip archive attempts to write outside runtime.") from exc
    return target


def safe_extract_zip(zip_path: Path, destination: Path) -> Path:
    if zip_path.suffix.lower() != ".zip":
        raise AppError(400, "invalid_archive", "Only .zip Fii project archives are supported.")

    destination.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = archive.infolist()
            file_count = sum(1 for item in members if not item.is_dir())
            if file_count > settings.max_zip_files:
                raise AppError(400, "too_many_files", "Zip archive contains too many files.")

            total_uncompressed_size = 0
            for info in members:
                if _is_zip_symlink(info):
                    raise AppError(400, "unsafe_zip_member", "Zip archive may not contain symlinks.")
                if not info.is_dir():
                    if info.file_size > settings.max_upload_bytes:
                        raise AppError(
                            400,
                            "file_too_large",
                            "A file inside the archive exceeds the configured size limit.",
                        )
                    total_uncompressed_size += info.file_size
                    if total_uncompressed_size > settings.max_uncompressed_bytes:
                        raise AppError(
                            400,
                            "archive_too_large",
                            "Zip archive uncompressed size exceeds the configured limit.",
                        )

                target = _target_for_member(destination, _member_name(info))
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue

                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    except zipfile.BadZipFile as exc:
        raise AppError(400, "invalid_archive", "Uploaded file is not a valid zip archive.") from exc

    fii_files = sorted(destination.rglob("*.fii"))
    if not fii_files:
        raise AppError(400, "missing_fii", "No .fii file was found in the uploaded project.")
    return fii_files[0].parent
