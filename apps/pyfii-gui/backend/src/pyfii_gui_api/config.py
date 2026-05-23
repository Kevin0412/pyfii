from pathlib import Path
import os


def _csv_env(name: str, default: list[str]) -> list[str]:
    value = os.environ.get(name)
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class Settings:
    """Runtime settings for the GUI API."""

    def __init__(self) -> None:
        backend_root = Path(__file__).resolve().parents[2]
        runtime_root = os.environ.get("PYFII_GUI_RUNTIME_DIR")
        default_cors_origins = [
            "http://localhost:5173",
        ]
        default_cors_origin_regex = (
            r"^http://("
            r"localhost|"
            r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
            r"192\.168\.\d{1,3}\.\d{1,3}|"
            r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
            r"):5173$"
        )
        cors_origin_regex = os.environ.get("PYFII_GUI_CORS_ORIGIN_REGEX")

        self.app_title = os.environ.get("PYFII_GUI_APP_TITLE", "Pyfii GUI API")
        self.runtime_dir = Path(runtime_root) if runtime_root else backend_root / ".runtime" / "projects"
        self.cors_origins = _csv_env("PYFII_GUI_CORS_ORIGINS", default_cors_origins)
        self.cors_origin_regex = (
            default_cors_origin_regex if cors_origin_regex is None else cors_origin_regex or None
        )
        self.cors_allow_credentials = _bool_env("PYFII_GUI_CORS_ALLOW_CREDENTIALS", True)
        self.default_import_fps = _int_env("PYFII_GUI_DEFAULT_IMPORT_FPS", 60)
        self.max_upload_bytes = 100 * 1024 * 1024
        self.max_zip_files = 5000


settings = Settings()
