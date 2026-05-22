from pathlib import Path
import os


class Settings:
    """Runtime settings for the local GUI API."""

    def __init__(self) -> None:
        backend_root = Path(__file__).resolve().parents[2]
        runtime_root = os.environ.get("PYFII_GUI_RUNTIME_DIR")
        self.runtime_dir = Path(runtime_root) if runtime_root else backend_root / ".runtime" / "projects"
        self.max_upload_bytes = 100 * 1024 * 1024
        self.max_zip_files = 5000


settings = Settings()
