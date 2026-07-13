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


if __name__ == "__main__":
    unittest.main()
