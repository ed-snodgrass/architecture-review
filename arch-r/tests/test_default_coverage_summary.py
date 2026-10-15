"""Objective contracts for iteration 003's default coverage-rendering task.

Exercise real module analysis and the public renderer, without prescribing
section headings or implementing report behavior.
"""
import re
import unittest

from archr.discovery import discover_clients
from archr.module import load_module
from archr.report import render_report
from archr.traversal import trace_usage
from tests import test_untraced_call_coverage as fixtures


class DefaultCoverageSummaryTests(unittest.TestCase):
    setUp = fixtures.UntracedCallCoverageTests.setUp
    put = fixtures.UntracedCallCoverageTests.put
    client = fixtures.UntracedCallCoverageTests.client

    def render(self):
        module = load_module(str(self.module))
        usage = trace_usage(module)
        return render_report(module, discover_clients(module), usage), usage

    def summary_paragraph(self, report, count):
        paragraphs = re.split(r'\n\s*\n', report)
        matches = [p for p in paragraphs if re.search(
            rf'\b{count} call sites? (?:was|were) not traced\b', p)]
        self.assertEqual(len(matches), 1, report)
        paragraph = matches[0]
        self.assertIn('--show-analysis-limitations', paragraph)
        self.assertRegex(paragraph.lower(),
                         r'external effects.*(?:cannot|can.t|not).*ruled out')
        # Require prose, not a bullet list or extra diagnostic paragraphs.
        self.assertNotRegex(paragraph, r'(?m)^\s*(?:[-*]|\d+\.)\s')
        sentences = re.split(r'[.!?]+(?:\s+|$)', paragraph.strip())
        self.assertLessEqual(len([s for s in sentences if s.strip()]), 2)
        self.assertLessEqual(len(paragraph.split()), 55)
        return paragraph

    def test_default_summary_is_module_wide_not_repeated_per_client(self):
        self.client()
        self.client('BillingClient', 'billing')
        self.put('Alpha', '''package sample;
class Alpha {
    Client client;
    void work(Request request) { client.get("id"); request.alphaGap(); }
}
''')
        self.put('Zulu', '''package sample;
class Zulu {
    BillingClient client;
    void work(Request request) { client.get("id"); request.zuluGap(); }
}
''')
        report, usage = self.render()
        self.assertEqual(len(usage.untraced_sites), 2)
        self.summary_paragraph(report, 2)
        from tests.report_sections import findings
        self.assertEqual(len(findings(report)), 2)
        for diagnostic in usage.diagnostics:
            self.assertNotIn(diagnostic.code, report)
            self.assertNotIn(diagnostic.message, report)
            self.assertNotIn(diagnostic.invocation.method_name, report)
        # Compact paths replace call-step citations, not analysis evidence.
        self.assertIn('sample.Alpha.work → sample.Client.get', report)
        self.assertIn('sample.Zulu.work → sample.BillingClient.get', report)
        from tests.analysis_evidence import locations
        self.assertIn('src/main/java/sample/Alpha.java:4', locations(self.module))
        self.assertIn('src/main/java/sample/Zulu.java:4', locations(self.module))

    def test_no_findings_still_gets_summary_without_individual_evidence(self):
        self.put('Plain', '''package sample;
class Plain {
    void work(Request request) { request.firstGap(); request.secondGap(); }
}
''')
        report, usage = self.render()
        self.assertEqual(len(usage.untraced_sites), 2)
        self.summary_paragraph(report, 2)
        self.assertIn('No statically declared Feign outbound HTTP dependencies were found.', report)
        for hidden in ('Plain.java:3', 'firstGap', 'secondGap', 'unsupported-receiver'):
            self.assertNotIn(hidden, report)
        for diagnostic in usage.diagnostics:
            self.assertNotIn(diagnostic.message, report)
        self.assertNotIn('## Finding ', report)

    def test_zero_gaps_uses_exact_bounded_statement_with_and_without_findings(self):
        self.put('Plain', 'package sample; class Plain {}\n')
        for with_client in (False, True):
            with self.subTest(with_client=with_client):
                if with_client:
                    self.client(url='${products.url}')
                report, usage = self.render()
                self.assertEqual(usage.untraced_sites, ())
                paragraphs = [p.strip() for p in re.split(r'\n\s*\n', report)]
                self.assertEqual(paragraphs.count(fixtures.ZERO), 1, report)
                self.assertNotRegex(report.lower(), r'\b(?:full|complete) (?:java )?coverage\b')
                self.assertNotRegex(report.lower(), r'\b(?:no|without) external effects\b')
                self.assertNotRegex(report, r'\b0 call sites? (?:was|were) not traced\b')
                if with_client:
                    self.assertIn('destination unresolved', report)

    def test_scope_note_distinguishes_recorded_gaps_from_all_unsupported_syntax(self):
        self.put('Plain', 'package sample; class Plain {}\n')
        report, _ = self.render()
        self.assertIn(fixtures.ZERO, report)
        # Empty recorded diagnostics do not erase the general source boundary
        # or imply that other dependency mechanisms have been analyzed.
        for boundary in ('src/main/java', 'source only', 'runtime', 'outside'):
            self.assertIn(boundary, report)
        self.assertRegex(report.lower(), r'(?:other|outside).*http|http.*(?:other|outside)')
        self.assertNotRegex(report.lower(), r'\b(?:all calls traced|no external dependencies)\b')


if __name__ == '__main__':
    unittest.main()
