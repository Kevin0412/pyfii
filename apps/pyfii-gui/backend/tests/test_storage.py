from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from pyfii_gui_api.config import settings
from pyfii_gui_api.services.storage import cleanup_project, project_root


class ProjectStorageTests(unittest.TestCase):
    def test_rejects_paths_outside_runtime_directory(self):
        with TemporaryDirectory() as temporary_dir:
            parent = Path(temporary_dir)
            runtime = parent / "runtime"
            sentinel = parent / "sentinel.txt"
            runtime.mkdir()
            sentinel.write_text("keep", encoding="utf-8")

            with patch.object(settings, "runtime_dir", runtime):
                with self.assertRaises(ValueError):
                    cleanup_project("..")

            self.assertTrue(runtime.is_dir())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_allows_direct_project_child(self):
        with TemporaryDirectory() as temporary_dir:
            runtime = Path(temporary_dir) / "runtime"
            project_id = "a" * 32

            with patch.object(settings, "runtime_dir", runtime):
                root = project_root(project_id)

            self.assertEqual(root, runtime / project_id)


if __name__ == "__main__":
    unittest.main()
