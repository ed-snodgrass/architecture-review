"""Objective contracts for iteration 003's optional module-wide details task.

Use real recorded invocations; only diagnostic multiplicity/order is injected.
No production changes or required Markdown heading/layout are prescribed.
"""
from dataclasses import replace
import re
import unittest

from archr.discovery import discover_clients
from archr.module import load_module
from archr.report import render_report
from archr.traversal import trace_usage
from tests import test_untraced_call_coverage as fixtures


class OptionalCoverageDetailsTests(unittest.TestCase):
    setUp = fixtures.UntracedCallCoverageTests.setUp
    put = fixtures.UntracedCallCoverageTests.put
    client = fixtures.UntracedCallCoverageTests.client
    snapshot = fixtures.UntracedCallCoverageTests.snapshot
    run_cli = fixtures.UntracedCallCoverageTests.run_cli
    report = fixtures.UntracedCallCoverageTests.report
    assert_coverage = fixtures.UntracedCallCoverageTests.assert_coverage

    def ordered_sites(self):
        # Create files in reverse path order, and put the first path's calls on
        # a later line. Path, then line, then occurrence must determine order;
        # neither discovery order nor a module-wide line-only sort is enough.
        self.client()
        self.client('BillingClient', 'billing')
        self.put('Zulu', '''package sample;
class Zulu {
    void work(Request request) { request.zuluGap(); }
}
''')
        self.put('Alpha', '''package sample;
class Alpha {
    Client client;
    BillingClient billing;
    void work(Request request) {
        client.get("id");
        billing.get("id");

        request.alphaGap(); request.alphaGap(); request.betaGap();
        request.lastGap();
    }
}
''')
        return [
            ('src/main/java/sample/Alpha.java:9', 'alphaGap'),
            ('src/main/java/sample/Alpha.java:9', 'alphaGap'),
            ('src/main/java/sample/Alpha.java:9', 'betaGap'),
            ('src/main/java/sample/Alpha.java:10', 'lastGap'),
            ('src/main/java/sample/Zulu.java:3', 'zuluGap'),
        ]

    def assert_entries(self, report, expected):
        # All sites are unrelated to either client, so every citation must
        # occur just once in module-wide details, never under each finding.
        rows = [row for row in report.splitlines()
                if any(citation in row for citation, _ in expected)]
        self.assertEqual(len(rows), len(expected), report)
        for row, (citation, call) in zip(rows, expected):
            self.assertIn(citation, row)
            self.assertIn(call, row)
            self.assertRegex(row.lower(),
                             r'not.*(?:field|follow|support|trace)|unsupported')
            self.assertNotIn(str(self.module), row, 'Locations must be relative')
        self.assertNotEqual(rows[0], rows[1],
                            'Identical calls on one line need distinct identities')
        return rows

    def test_cli_both_flag_positions_emit_one_location_ordered_module_wide_list(self):
        expected = self.ordered_sites()
        default = self.report()
        self.assert_coverage(default, 5)
        for citation, call in expected:
            self.assertNotIn(citation, default)
            self.assertNotIn(call, default)
        reports = []
        for before in (True, False):
            with self.subTest(flag_before_path=before):
                detailed = self.report(details=True, before=before)
                self.assert_coverage(detailed, 5)
                self.assert_entries(detailed, expected)
                self.assertEqual(len(re.findall(r'^### Finding ', detailed.split('## Findings\n', 1)[1].split('\n## ', 1)[0], re.M)), 2)
                reports.append(detailed)
        self.assertEqual(*reports)

    def test_details_are_independent_of_diagnostic_order_and_repetition(self):
        expected = self.ordered_sites()
        module = load_module(str(self.module))
        clients = discover_clients(module)
        usage = trace_usage(module)
        self.assertEqual(len(usage.diagnostics), 5)
        extra = 'The receiver type cannot be resolved within supported analysis.'
        records = tuple(item for diagnostic in usage.diagnostics
                        for item in (diagnostic,
                                     replace(diagnostic, message=extra),
                                     diagnostic,
                                     replace(diagnostic, message=extra)))
        # Test report behavior, not a particular internal site representation.
        reports = []
        for diagnostics in (records, tuple(reversed(records)),
                            records[1:] + records[:1]):
            with self.subTest(first_reason=diagnostics[0].message):
                augmented = replace(usage, diagnostics=diagnostics)
                report = render_report(module, clients, augmented,
                                       show_analysis_limitations=True)
                self.assert_coverage(report, 5)
                rows = self.assert_entries(report, expected)
                for row in rows:
                    self.assertEqual(row.count(extra), 1, row)
                    self.assertEqual(row.count(usage.diagnostics[0].message), 1, row)
                reports.append(report)
        self.assertTrue(all(report == reports[0] for report in reports))


if __name__ == '__main__':
    unittest.main()
