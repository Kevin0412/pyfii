import re
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCUMENTATION_SOURCE = (
    REPO_ROOT / "apps/pyfii-gui/frontend/src/content/documentation.ts"
)


def frontend_documents():
    source = DOCUMENTATION_SOURCE.read_text(encoding="utf-8")
    imports = re.findall(r'from "([^"]+\.md)\?raw"', source)
    return [(DOCUMENTATION_SOURCE.parent / item).resolve() for item in imports]


class FrontendDocumentationTest(unittest.TestCase):
    def test_imported_documents_exist_and_are_unique(self):
        documents = frontend_documents()
        self.assertTrue(documents)
        self.assertEqual(len(documents), len(set(documents)))
        for document in documents:
            self.assertTrue(document.is_file(), document)

        source = DOCUMENTATION_SOURCE.read_text(encoding="utf-8")
        routed_filenames = set(
            re.findall(r'^\s*"([^"]+\.md)":\s*"/docs', source, re.MULTILINE)
        )
        self.assertEqual(routed_filenames, {document.name for document in documents})

    def test_markdown_links_only_target_bundled_documents(self):
        documents = frontend_documents()
        bundled = set(documents)
        for document in documents:
            markdown = document.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^]]*\]\(([^)]+)\)", markdown):
                path = target.split("#", 1)[0]
                if not path or "://" in path or path.startswith("mailto:"):
                    continue
                resolved = (document.parent / path).resolve()
                self.assertIn(
                    resolved,
                    bundled,
                    f"{document.relative_to(REPO_ROOT)} links to an unbundled path: {target}",
                )

    def test_python_examples_have_valid_syntax(self):
        for document in frontend_documents():
            markdown = document.read_text(encoding="utf-8")
            blocks = re.findall(r"```python\s*\n(.*?)```", markdown, re.DOTALL)
            for index, block in enumerate(blocks, 1):
                source = textwrap.dedent(block)
                compile(source, f"{document} python block {index}", "exec")


if __name__ == "__main__":
    unittest.main()
