from pathlib import Path
import json
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


def _deployment_value(config: dict, env_name: str, key: str, default: str = "") -> str:
    value = os.environ.get(env_name)
    if value is not None:
        return value.strip()
    raw = config.get(key, default)
    return str(raw).strip() if raw is not None else default


class Settings:
    """Runtime settings for the GUI API."""

    def __init__(self) -> None:
        backend_root = Path(__file__).resolve().parents[2]
        gui_root = backend_root.parent
        repo_root = backend_root.parents[2]
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
        self.repo_root = repo_root
        self.runtime_dir = Path(runtime_root) if runtime_root else backend_root / ".runtime" / "projects"
        self.cors_origins = _csv_env("PYFII_GUI_CORS_ORIGINS", default_cors_origins)
        self.cors_origin_regex = (
            default_cors_origin_regex if cors_origin_regex is None else cors_origin_regex or None
        )
        self.cors_allow_credentials = _bool_env("PYFII_GUI_CORS_ALLOW_CREDENTIALS", True)
        self.default_import_fps = _int_env("PYFII_GUI_DEFAULT_IMPORT_FPS", 60)
        self.trajectory_workers = max(
            1,
            _int_env("PYFII_GUI_TRAJECTORY_WORKERS", max(1, (os.cpu_count() or 1) // 2)),
        )
        self.video_export_jobs = max(1, _int_env("PYFII_GUI_VIDEO_EXPORT_JOBS", 1))
        self.video_render_workers = max(
            1,
            _int_env("PYFII_GUI_VIDEO_RENDER_WORKERS", max(1, (os.cpu_count() or 1) // 2)),
        )
        self.max_upload_bytes = _int_env("PYFII_GUI_MAX_UPLOAD_BYTES", 100 * 1024 * 1024)
        self.max_uncompressed_bytes = _int_env(
            "PYFII_GUI_MAX_UNCOMPRESSED_BYTES",
            500 * 1024 * 1024,
        )
        self.max_zip_files = _int_env("PYFII_GUI_MAX_ZIP_FILES", 5000)
        self.enable_local_project_import = _bool_env("PYFII_GUI_ENABLE_LOCAL_PROJECT_IMPORT", False)
        self.local_project_roots = [
            (repo_root / item).resolve() if not Path(item).is_absolute() else Path(item).resolve()
            for item in _csv_env(
                "PYFII_GUI_LOCAL_PROJECT_ROOTS",
                [str(repo_root / "tools" / "choreo_agent" / "agent_projects")],
            )
        ]

        deploy_config_path = Path(
            os.environ.get("PYFII_GUI_DEPLOY_CONFIG", str(gui_root / "deploy.local.json"))
        )
        if not deploy_config_path.is_absolute():
            deploy_config_path = repo_root / deploy_config_path
        self.deploy_config_path = deploy_config_path.resolve()
        deploy_config = {}
        if self.deploy_config_path.exists():
            try:
                deploy_config = json.loads(self.deploy_config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                deploy_config = {}

        self.icp_beian = _deployment_value(deploy_config, "PYFII_GUI_ICP_BEIAN", "icp_beian")
        self.icp_url = _deployment_value(
            deploy_config,
            "PYFII_GUI_ICP_URL",
            "icp_url",
            "https://beian.miit.gov.cn/",
        )
        self.gongan_beian = _deployment_value(deploy_config, "PYFII_GUI_GONGAN_BEIAN", "gongan_beian")
        self.gongan_url = _deployment_value(deploy_config, "PYFII_GUI_GONGAN_URL", "gongan_url")


settings = Settings()
