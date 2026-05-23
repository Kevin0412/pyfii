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


class Settings:
    """Runtime settings for the GUI API."""

    def __init__(self) -> None:
        backend_root = Path(__file__).resolve().parents[2]
        runtime_root = os.environ.get("PYFII_GUI_RUNTIME_DIR")
        default_cors_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

        self.app_title = os.environ.get("PYFII_GUI_APP_TITLE", "Pyfii GUI API")
        self.runtime_dir = Path(runtime_root) if runtime_root else backend_root / ".runtime" / "projects"
        self.cors_origins = _csv_env("PYFII_GUI_CORS_ORIGINS", default_cors_origins)
        self.cors_origin_regex = os.environ.get("PYFII_GUI_CORS_ORIGIN_REGEX") or None
        self.cors_allow_credentials = _bool_env("PYFII_GUI_CORS_ALLOW_CREDENTIALS", True)
        self.max_upload_bytes = 100 * 1024 * 1024
        self.max_zip_files = 5000


settings = Settings()
