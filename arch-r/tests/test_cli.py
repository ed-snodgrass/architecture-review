from pathlib import Path
import subprocess
import tempfile
import unittest

from archr.module import load_module


ENTRY_POINT = Path(__file__).resolve().parents[1] / "arch-r"


class ModuleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.module = self.base / "order-service"
        (self.module / "src/main/java").mkdir(parents=True)

    def pom(self, content):
        (self.module / "pom.xml").write_text(content, encoding="utf-8")

    def run_cli(self, *args):
        return subprocess.run(
            [str(ENTRY_POINT), *args], cwd=self.base,
            text=True, capture_output=True,
        )

    def test_reads_own_namespaced_artifact_not_parent(self):
        self.pom('''<project xmlns="http://maven.apache.org/POM/4.0.0">
          <parent><artifactId>parent</artifactId></parent>
          <artifactId> order-service-api </artifactId></project>''')
        module = load_module(str(self.module))
        self.assertEqual(module.name, "order-service-api")
        self.assertEqual(module.path, self.module.resolve())
        self.assertEqual(module.source_root, self.module / "src/main/java")

    def test_unnamespaced_artifact_and_filename_sanitization(self):
        self.pom('<project><artifactId>Order / API: α!?._-9</artifactId></project>')
        module = load_module(str(self.module))
        self.assertEqual(module.name, "Order / API: α!?._-9")
        self.assertEqual(module.report_filename, "arch-r-report-Order-API-._-9.md")

    def test_fallback_when_no_project_artifact_can_be_read(self):
        for content in (None, "<broken", "<project/>",
                        "<project><parent><artifactId>parent</artifactId></parent></project>",
                        "<project><artifactId> </artifactId></project>"):
            with self.subTest(content=content):
                if content is not None:
                    self.pom(content)
                self.assertEqual(load_module(str(self.module)).name, "order-service")

    def test_relative_and_absolute_cli_paths(self):
        for path in ("order-service", str(self.module)):
            with self.subTest(path=path):
                result = self.run_cli("analyze", path)
                self.assertEqual(result.returncode, 0, result.stderr)

    def assert_rejected(self, path):
        result = self.run_cli("analyze", str(path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("arch-r:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(list(self.base.glob("arch-r-report-*.md")), [])

    def test_missing_path(self):
        self.assert_rejected(self.base / "missing")

    def test_file_instead_of_directory(self):
        file = self.base / "file"
        file.write_text("not a directory")
        self.assert_rejected(file)

    def test_missing_conventional_source_tree(self):
        empty = self.base / "empty"
        empty.mkdir()
        self.assert_rejected(empty)

    def test_source_root_must_be_directory(self):
        source = self.module / "src/main/java"
        source.rmdir()
        source.write_text("not a directory")
        self.assert_rejected(self.module)

    def test_unreadable_directories(self):
        for path in (self.module, self.module / "src/main/java"):
            with self.subTest(path=path):
                original = path.stat().st_mode
                try:
                    path.chmod(0)
                    self.assert_rejected(self.module)
                finally:
                    path.chmod(original)

    def test_unreadable_pom_falls_back(self):
        from unittest.mock import patch
        with patch("archr.module.ET.parse", side_effect=PermissionError):
            self.assertEqual(load_module(str(self.module)).name, "order-service")

    def test_cli_usage_errors_and_help(self):
        for args in ((), ("analyze",), ("unknown",)):
            self.assertNotEqual(self.run_cli(*args).returncode, 0)
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("analyze", result.stdout)


if __name__ == "__main__":
    unittest.main()
