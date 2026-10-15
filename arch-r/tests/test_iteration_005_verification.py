"""Read-only and failure verification for the mixed iteration 005 module."""
import json
from pathlib import Path
import subprocess
import unittest

from archr.discovery import discover_clients
from archr.findings import discover_findings
from archr.module import load_module
from archr.report import render_report
from archr.traversal import trace_usage
from tests import test_iteration_005_acceptance as fixtures


class Iteration005VerificationTests(unittest.TestCase):
    setUp = fixtures.Iteration005AcceptanceTests.setUp
    report = fixtures.Iteration005AcceptanceTests.report

    def test_analysis_matches_independently_captured_iteration_004_baseline(self):
        from tests.preservation_snapshot import snapshot
        baseline = json.loads(Path(__file__).with_name(
            'iteration_004_preservation.json').read_text())
        actual = snapshot(str(self.module))
        self.assertEqual(actual.keys(), baseline.keys())
        for dimension, expected in baseline.items():
            with self.subTest(dimension=dimension):
                self.assertEqual(actual[dimension], expected)

    def snapshot(self):
        return {str(path.relative_to(self.module)):
                (path.stat().st_mode, path.stat().st_mtime_ns,
                 path.read_bytes() if path.is_file() else None)
                for path in self.module.rglob('*')}

    def test_rendering_preserves_analysis_and_diagram_in_both_modes(self):
        before = self.snapshot()
        module = load_module(str(self.module))
        clients = discover_clients(module)
        findings = discover_findings(module)
        usage = trace_usage(module)
        original = repr((clients, findings, usage))
        reports = [render_report(module, clients, usage, findings=findings,
                                 show_analysis_limitations=details)
                   for details in (False, True, False)]
        self.assertEqual(original, repr((clients, findings, usage)))
        self.assertEqual(clients, discover_clients(module))
        self.assertEqual(findings, discover_findings(module))
        self.assertEqual(usage, trace_usage(module))
        self.assertEqual(reports[0], reports[2])
        self.assertEqual(reports[0].rstrip(),
                         reports[1].split('\n### Untraced call sites\n', 1)[0].rstrip())
        diagrams = [report.split('```mermaid\n', 1)[1].split('```', 1)[0]
                    for report in reports]
        self.assertEqual(diagrams[0], diagrams[1])
        self.assertEqual(before, self.snapshot())

    def test_invalid_inputs_preserve_successful_report_and_input_metadata(self):
        self.report()
        successful = self.output.read_bytes()
        for corrupt in (False, True):
            if corrupt:
                (self.module / 'src/main/java/Broken.java').write_bytes(b'\xff')
            before = self.snapshot()
            for details in (False, True):
                with self.subTest(corrupt_source=corrupt, details=details):
                    arguments = [str(fixtures.ENTRY_POINT), 'analyze',
                                 str(self.module if corrupt else self.work / 'missing')]
                    if details:
                        arguments.append('--show-analysis-limitations')
                    result = subprocess.run(arguments, cwd=self.work,
                                            capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, '')
                    self.assertIn('arch-r:', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
                    if corrupt:
                        self.assertIn('Cannot read Java sources', result.stderr)
                    self.assertEqual(successful, self.output.read_bytes())
                    self.assertEqual(before, self.snapshot())
                    self.assertEqual(set(self.work.iterdir()), {self.module, self.output})


if __name__ == '__main__':
    unittest.main()
