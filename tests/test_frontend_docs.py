import re
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCUMENTATION_SOURCE = (
    REPO_ROOT / "apps/pyfii-gui/frontend/src/content/documentation.ts"
)
DOCUMENT_ROUTE_SOURCE = (
    REPO_ROOT / "apps/pyfii-gui/frontend/src/content/documentRoutes.ts"
)
def frontend_documents():
    source = DOCUMENTATION_SOURCE.read_text(encoding="utf-8")
    imports = re.findall(r'from "([^"]+\.md)\?raw"', source)
    return [(DOCUMENTATION_SOURCE.parent / item).resolve() for item in imports]


class FrontendDocumentationTest(unittest.TestCase):
    def test_all_repository_markdown_is_bundled(self):
        repository_documents = set((REPO_ROOT / "doc").rglob("*.md"))
        self.assertEqual(set(frontend_documents()), repository_documents)

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

    def test_every_document_has_an_application_route(self):
        documentation = DOCUMENTATION_SOURCE.read_text(encoding="utf-8")
        application_routes = DOCUMENT_ROUTE_SOURCE.read_text(encoding="utf-8")
        document_paths = set(
            re.findall(r'^\s+route: "(/docs[^"]*)",$', documentation, re.MULTILINE)
        )
        route_table = re.search(
            r"const routeDocuments:[^{]+\{(.*?)\n\};",
            application_routes,
            re.DOTALL,
        )
        self.assertIsNotNone(route_table)
        routed_paths = set(
            re.findall(
                r'^\s+"(/docs[^"]*)": "[^"]+",$',
                route_table.group(1),
                re.MULTILINE,
            )
        )
        self.assertEqual(document_paths, routed_paths)

    def test_relative_markdown_links_resolve(self):
        documents = frontend_documents()
        bundled = set(documents)
        for document in documents:
            markdown = document.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^]]*\]\(([^)]+)\)", markdown):
                path = target.split("#", 1)[0]
                if not path or "://" in path or path.startswith("mailto:"):
                    continue
                resolved = (document.parent / path).resolve()
                if resolved.suffix == ".md":
                    self.assertIn(
                        resolved,
                        bundled,
                        f"{document.relative_to(REPO_ROOT)} links to an unbundled document: {target}",
                    )
                else:
                    self.assertTrue(
                        resolved.exists(),
                        f"{document.relative_to(REPO_ROOT)} links to a missing path: {target}",
                    )

    def test_python_examples_have_valid_syntax(self):
        for document in frontend_documents():
            markdown = document.read_text(encoding="utf-8")
            blocks = re.findall(r"```python\s*\n(.*?)```", markdown, re.DOTALL)
            for index, block in enumerate(blocks, 1):
                source = textwrap.dedent(block)
                compile(source, f"{document} python block {index}", "exec")

    def test_fenced_code_blocks_are_balanced(self):
        for document in frontend_documents():
            markdown = document.read_text(encoding="utf-8")
            fences = re.findall(r"^\s*```", markdown, re.MULTILINE)
            self.assertEqual(
                len(fences) % 2,
                0,
                f"{document.relative_to(REPO_ROOT)} has an unclosed code fence",
            )


if __name__ == "__main__":
    unittest.main()
