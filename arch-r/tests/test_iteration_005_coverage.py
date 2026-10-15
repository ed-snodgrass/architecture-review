"""Iteration 005: the coverage flag only appends details within Limitations."""
from dataclasses import replace
import unittest

from archr.discovery import discover_clients
from archr.module import load_module
from archr.report import render_report
from archr.traversal import trace_usage
from tests import test_optional_coverage_details as fixtures


class LimitationsCoverageTests(unittest.TestCase):
    setUp = fixtures.OptionalCoverageDetailsTests.setUp
    put = fixtures.OptionalCoverageDetailsTests.put
    client = fixtures.OptionalCoverageDetailsTests.client
    snapshot = fixtures.OptionalCoverageDetailsTests.snapshot
    run_cli = fixtures.OptionalCoverageDetailsTests.run_cli
    report = fixtures.OptionalCoverageDetailsTests.report
    assert_coverage = fixtures.OptionalCoverageDetailsTests.assert_coverage
    ordered_sites = fixtures.OptionalCoverageDetailsTests.ordered_sites
    assert_entries = fixtures.OptionalCoverageDetailsTests.assert_entries

    def assert_append_only(self, default, detailed):
        prefix, details = detailed.split('\n### Untraced call sites\n', 1)
        self.assertEqual(prefix.rstrip(), default.rstrip())
        self.assertEqual(detailed.count('### Untraced call sites\n'), 1)
        self.assertIn('## Limitations\n', prefix)
        self.assertNotIn('\n## ', details)
        self.assertNotIn('\n## Analysis coverage', detailed)
        return details

    def test_both_cli_flag_positions_only_append_source_ordered_details(self):
        expected = self.ordered_sites()
        default = self.report()
        self.assert_coverage(default, 5)
        reports = []
        for before in (False, True):
            detailed = self.report(details=True, before=before)
            details = self.assert_append_only(default, detailed)
            self.assert_entries(details, expected)
            self.assert_coverage(detailed, 5)
            reports.append(detailed)
        self.assertEqual(*reports)
        self.assertEqual(default, self.report())

    def test_repeated_diagnostics_do_not_change_sites_or_reason_order(self):
        expected = self.ordered_sites()
        module = load_module(str(self.module))
        clients = discover_clients(module)
        usage = trace_usage(module)
        extra = 'Additional unresolved source evidence.'
        records = tuple(item for diagnostic in usage.diagnostics
                        for item in (diagnostic, diagnostic,
                                     replace(diagnostic, message=extra)))
        reports = []
        for diagnostics in (records, tuple(reversed(records))):
            augmented = replace(usage, diagnostics=diagnostics)
            default = render_report(module, clients, augmented)
            detailed = render_report(module, clients, augmented,
                                     show_analysis_limitations=True)
            details = self.assert_append_only(default, detailed)
            rows = self.assert_entries(details, expected)
            for row in rows:
                self.assertEqual(row.count(extra), 1)
            reports.append(detailed)
        self.assertEqual(*reports)

    def test_no_sites_produces_identical_modes(self):
        self.client()
        default = self.report()
        self.assert_coverage(default, 0)
        for before in (False, True):
            self.assertEqual(default, self.report(details=True, before=before))
        self.assertNotIn('### Untraced call sites', default)


if __name__ == '__main__':
    unittest.main()
