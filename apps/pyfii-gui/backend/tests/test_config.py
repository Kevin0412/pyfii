from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import os
import unittest

from pyfii_gui_api.config import Settings


class DeploymentConfigTests(unittest.TestCase):
    def test_compliance_is_disabled_when_config_is_absent(self):
        with TemporaryDirectory() as temporary_dir:
            missing = Path(temporary_dir) / "missing.json"
            with patch.dict(
                os.environ,
                {"PYFII_GUI_DEPLOY_CONFIG": str(missing)},
                clear=True,
            ):
                settings = Settings()

        self.assertEqual(settings.icp_beian, "")
        self.assertEqual(settings.gongan_beian, "")

    def test_compliance_is_loaded_only_from_explicit_config(self):
        with TemporaryDirectory() as temporary_dir:
            config_path = Path(temporary_dir) / "deploy.json"
            config_path.write_text(
                json.dumps(
                    {
                        "icp_beian": "示例 ICP",
                        "icp_url": "https://beian.miit.gov.cn/",
                        "gongan_beian": "示例公安备案",
                        "gongan_url": "https://example.invalid/record",
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"PYFII_GUI_DEPLOY_CONFIG": str(config_path)},
                clear=True,
            ):
                settings = Settings()

        self.assertEqual(settings.icp_beian, "示例 ICP")
        self.assertEqual(settings.gongan_beian, "示例公安备案")


class SettingsTests(unittest.TestCase):
    def test_cors_credentials_are_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            configured = Settings()

        self.assertFalse(configured.cors_allow_credentials)

    def test_resource_limit_environment_variables(self):
        values = {
            "PYFII_GUI_PROJECT_IMPORT_JOBS": "3",
            "PYFII_GUI_PROJECT_IMPORT_QUEUE_SIZE": "4",
            "PYFII_GUI_VIDEO_EXPORT_JOBS": "2",
            "PYFII_GUI_VIDEO_EXPORT_QUEUE_SIZE": "5",
            "PYFII_GUI_PROJECT_TTL_SECONDS": "7200",
            "PYFII_GUI_RUNTIME_CLEANUP_INTERVAL_SECONDS": "120",
        }
        with patch.dict(os.environ, values):
            configured = Settings()

        self.assertEqual(configured.project_import_jobs, 3)
        self.assertEqual(configured.project_import_queue_size, 4)
        self.assertEqual(configured.video_export_jobs, 2)
        self.assertEqual(configured.video_export_queue_size, 5)
        self.assertEqual(configured.project_ttl_seconds, 7200)
        self.assertEqual(configured.runtime_cleanup_interval_seconds, 120)

    def test_resource_limits_cannot_be_negative(self):
        values = {
            "PYFII_GUI_PROJECT_IMPORT_JOBS": "0",
            "PYFII_GUI_PROJECT_IMPORT_QUEUE_SIZE": "-1",
            "PYFII_GUI_VIDEO_EXPORT_JOBS": "0",
            "PYFII_GUI_VIDEO_EXPORT_QUEUE_SIZE": "-1",
            "PYFII_GUI_PROJECT_TTL_SECONDS": "-1",
            "PYFII_GUI_RUNTIME_CLEANUP_INTERVAL_SECONDS": "0",
        }
        with patch.dict(os.environ, values):
            configured = Settings()

        self.assertEqual(configured.project_import_jobs, 1)
        self.assertEqual(configured.project_import_queue_size, 0)
        self.assertEqual(configured.video_export_jobs, 1)
        self.assertEqual(configured.video_export_queue_size, 0)
        self.assertEqual(configured.project_ttl_seconds, 0)
        self.assertEqual(configured.runtime_cleanup_interval_seconds, 1)


if __name__ == "__main__":
    unittest.main()
