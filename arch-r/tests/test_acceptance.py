"""Exercise the executable from the caller's directory against real source trees."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from archr.cli import main


ENTRY_POINT = Path(__file__).resolve().parents[1] / "arch-r"
IMPORTS = """import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
"""


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.caller = Path(self.temp.name)
        self.module = self.caller / "modules" / "orders"
        (self.module / "src/main/java").mkdir(parents=True)
        (self.module / "pom.xml").write_text(
            "<project><artifactId>order-service</artifactId></project>", encoding="utf-8")
        self.report = self.caller / "arch-r-report-order-service.md"

    def source(self, name, content):
        path = self.module / "src/main/java" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(IMPORTS + content, encoding="utf-8")
        return path

    def run_cli(self, path=None):
        return subprocess.run(
            [str(ENTRY_POINT), "analyze", str(path or self.module)],
            cwd=self.caller, capture_output=True, text=True)

    def successful_report(self, path=None):
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertFalse(list(self.caller.glob(".arch-r-*.tmp")))
        self.assertFalse(list(self.module.glob("arch-r-report-*.md")))
        return self.report.read_text(encoding="utf-8")

    def test_literal_destination_evidence_and_diagram(self):
        self.source("InventoryClient.java", '''@FeignClient(name = "inventory", url = "https://inventory.example")
public interface InventoryClient {
    @GetMapping("/items/{id}")
    Item getItem(String id);
}
''')
        report = self.successful_report("modules/orders")
        for expected in (
            "order-service makes an outbound HTTP connection to inventory",
            "https://inventory.example", "High confidence", "GET /items/{id}",
            "src/main/java/InventoryClient.java:3", "src/main/java/InventoryClient.java:5",
            'System(module, "order-service"', 'Container(feign_1, "InventoryClient"',
            'System_Ext(external_1, "inventory"', str(self.module),
            "did not inspect callers", "domain-facing port or adapter",
        ):
            self.assertIn(expected, report)
        self.assertNotIn("getItem", report.split("```mermaid")[1].split("```")[0])

    def test_placeholder_is_not_resolved_from_configuration(self):
        self.source("Pricing.java", '''@FeignClient(name = "pricing", url = "${pricing.url}")
interface Pricing {}
''')
        resources = self.module / "src/main/resources"
        resources.mkdir()
        (resources / "application.properties").write_text("pricing.url=https://secret.example")
        report = self.successful_report()
        self.assertIn("${pricing.url}", report)
        self.assertIn("destination unresolved", report)
        self.assertIn("Lower confidence", report)
        self.assertNotIn("https://secret.example", report)

    def test_alias_and_multiple_clients(self):
        self.source("Shipping.java", '''@FeignClient(value = "shipping", url = "https://shipping.example")
interface Shipping {}
''')
        self.source("Inventory.java", '''@FeignClient(name = "inventory", url = "https://inventory.example")
interface Inventory {}
''')
        report = self.successful_report()
        self.assertIn("Found 2 statically declared Feign outbound HTTP dependencies", report)
        self.assertIn("**External system:** shipping", report)
        self.assertIn("https://shipping.example", report)
        self.assertEqual(report.count("```mermaid"), 1)
        self.assertEqual(report.count("System_Ext("), 2)
        self.assertEqual(report.count("Container("), 2)

    def test_no_clients_and_excluded_sources_remain_unchanged(self):
        self.source("Plain.java", "interface Plain {}\n")
        for relative in ("src/test/java/Test.java", "target/generated-sources/Generated.java",
                         "src/main/resources/Configuration.java"):
            path = self.module / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(IMPORTS + '@FeignClient(name="excluded") interface Excluded {}')
        before = {p.relative_to(self.module): p.read_bytes()
                  for p in self.module.rglob("*") if p.is_file()}
        report = self.successful_report()
        self.assertIn("No statically declared Feign outbound HTTP dependencies were found", report)
        self.assertIn("does not mean the module makes no outbound calls", report)
        self.assertNotIn("excluded", report)
        after = {p.relative_to(self.module): p.read_bytes()
                 for p in self.module.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_repeated_analysis_replaces_same_report_with_identical_bytes(self):
        self.source("Client.java", '@FeignClient(name="remote", url="https://remote.example") interface Client {}')
        self.successful_report()
        first = self.report.read_bytes()
        self.report.write_text("stale report")
        self.successful_report()
        self.assertEqual(self.report.read_bytes(), first)
        self.successful_report()
        self.assertEqual(self.report.read_bytes(), first)
        self.assertEqual(list(self.caller.glob("arch-r-report-*.md")), [self.report])

    def test_analysis_failure_preserves_existing_report(self):
        path = self.source("Broken.java", "interface Broken {}")
        path.write_bytes(b"\xff")
        self.report.write_text("previous successful report")
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot read Java sources", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.report.read_text(), "previous successful report")
        self.assertFalse(list(self.caller.glob(".arch-r-*.tmp")))
        self.report.unlink()
        self.assertNotEqual(self.run_cli().returncode, 0)
        self.assertFalse(self.report.exists())

    def test_unreadable_source_fails_without_report(self):
        path = self.source("Private.java", "interface Private {}")
        try:
            path.chmod(0)
            result = self.run_cli()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not readable", result.stderr)
            self.assertFalse(self.report.exists())
        finally:
            path.chmod(0o644)

    def test_output_failure_is_concise_and_cleans_temporary_file(self):
        self.report.mkdir()
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot write report arch-r-report-order-service.md", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(list(self.caller.glob(".arch-r-*.tmp")))

    def test_unwritable_output_directory_is_handled(self):
        with patch("archr.cli.tempfile.NamedTemporaryFile", side_effect=PermissionError("denied")), \
                patch("sys.stderr") as stderr:
            self.assertEqual(main(["analyze", str(self.module)]), 1)
            self.assertIn("Cannot write report", str(stderr.write.call_args_list))


if __name__ == "__main__":
    unittest.main()
