"""Regression contracts for iteration 003's first unfinished plan task.

Analyze disposable Java sources. Inject repeated retained records only where
real source cannot produce multiple diagnostic reasons for one invocation.
"""
from dataclasses import replace
import re
import unittest

from archr.discovery import discover_clients
from archr.module import load_module
from archr.report import render_report
from archr.resolution import Diagnostic
from archr.traversal import trace_usage
from tests import test_untraced_call_coverage as fixtures


class Iteration003RegressionTests(unittest.TestCase):
    setUp = fixtures.UntracedCallCoverageTests.setUp
    put = fixtures.UntracedCallCoverageTests.put
    client = fixtures.UntracedCallCoverageTests.client
    snapshot = fixtures.UntracedCallCoverageTests.snapshot
    run_cli = fixtures.UntracedCallCoverageTests.run_cli
    report = fixtures.UntracedCallCoverageTests.report
    assert_coverage = fixtures.UntracedCallCoverageTests.assert_coverage

    def outside_coverage(self, report, count):
        # Identify coverage by its required summary, not a prescribed heading.
        sections = re.split(r'(?=^## )', report, flags=re.M)
        coverage = [s for s in sections if f'{count} call sites' in s]
        self.assertEqual(len(coverage), 1, report)
        return ''.join(s for s in sections if s not in coverage)

    def test_seven_shared_gaps_are_not_multiplied_by_clients_or_call_paths(self):
        self.client()
        self.client('BillingClient', 'billing')
        self.put('Shared', '''package sample;
class Shared {
    Client products;
    BillingClient billing;
    void work(Request request) {
        products.get("id");
        billing.get("id");
        request.firstGap(); request.secondGap();
        request.thirdGap();
        request.fourthGap();
        request.fifthGap();
        request.sixthGap();
        request.seventhGap();
    }
}
''')
        for name in ('FirstCaller', 'SecondCaller'):
            self.put(name, f'''package sample;
class {name} {{
    Shared shared;
    void run(Request request) {{ shared.work(request); }}
}}
''')
        usage = trace_usage(load_module(str(self.module)))
        self.assertEqual(len(usage.chains), 4, 'Two callers reach each of two clients')
        self.assertEqual({c.client_type for c in usage.chains},
                         {'sample.Client', 'sample.BillingClient'})
        self.assertEqual(len(usage.diagnostics), 7)
        self.assertEqual({d.code for d in usage.diagnostics}, {'unsupported-receiver'})
        default = self.report()
        self.assert_coverage(default, 7)
        calls = ('firstGap', 'secondGap', 'thirdGap', 'fourthGap',
                 'fifthGap', 'sixthGap', 'seventhGap')
        for call in calls:
            self.assertNotIn(call, default)
        self.assertNotIn('unsupported-receiver', default)
        from tests.report_sections import findings
        self.assertEqual(len(findings(default)), 2)
        expected_lines = (8, 8, 9, 10, 11, 12, 13)
        for before in (False, True):
            with self.subTest(flag_before_path=before):
                detailed = self.report(details=True, before=before)
                self.assert_coverage(detailed, 7)
                self.assertEqual(self.outside_coverage(default, 7),
                                 self.outside_coverage(detailed, 7))
                rows = [row for row in detailed.splitlines()
                        if any(call in row for call in calls)]
                self.assertEqual(len(rows), 7, detailed)
                for row, call, line in zip(rows, calls, expected_lines):
                    self.assertIn(call, row)
                    self.assertIn(f'src/main/java/sample/Shared.java:{line}', row)
                    self.assertRegex(row.lower(), r'not.*(?:field|follow|trace|support)')
                self.assertNotEqual(rows[0], rows[1])

    def interface_gap(self):
        self.put('Port', 'package sample; interface Port { String lookup(String id); }\n')
        self.put('Order', '''package sample;
class Order {
    Port port;
    void work(Request request) { port.lookup("id"); request.getId(); }
}
''')
        return load_module(str(self.module))

    def test_no_findings_still_reports_both_interface_and_receiver_gaps(self):
        module = self.interface_gap()
        usage = trace_usage(module)
        self.assertFalse(usage.chains)
        self.assertEqual([d.code for d in usage.diagnostics], ['unsupported-receiver'])
        self.assertEqual([d.code for d in usage.interface_diagnostics],
                         ['no-local-implementation'])
        default = self.report()
        self.assert_coverage(default, 2)
        self.assertIn('No statically declared Feign outbound HTTP dependencies were found.', default)
        for hidden in ('port.lookup', 'request.getId', 'Order.java:4',
                       'no-local-implementation', 'unsupported-receiver'):
            self.assertNotIn(hidden, default)
        detailed = self.report(details=True)
        self.assert_coverage(detailed, 2)
        rows = [row for row in detailed.splitlines()
                if 'src/main/java/sample/Order.java:4' in row]
        self.assertEqual(len(rows), 2, detailed)
        self.assertIn('port.lookup', rows[0])
        self.assertRegex(rows[0].lower(), r'no.*implementation')
        self.assertIn('request.getId', rows[1])
        self.assertRegex(rows[1].lower(), r'not.*(?:field|follow|trace|support)')
        self.assertEqual(self.outside_coverage(default, 2),
                         self.outside_coverage(detailed, 2))

    def test_one_site_across_diagnostic_sources_consolidates_distinct_reasons(self):
        module = self.interface_gap()
        usage = trace_usage(module)
        interface = usage.interface_diagnostics[0]
        link = interface.link
        # Retained records can describe one site through different channels.
        # Keep the real invocation and field evidence; vary only reasons/codes.
        reason = 'The declared receiver has no uniquely resolved call target.'
        resolver = Diagnostic(link.caller_type, link.caller_method,
                              link.invocation, 'unresolved-method', reason,
                              receiver_field=link.receiver_field)
        same_reason = replace(resolver, code='unsupported-syntax')
        clients = discover_clients(module)
        reports = []
        for records in ((resolver, same_reason, resolver),
                        (same_reason, resolver, same_reason)):
            augmented = replace(usage,
                                diagnostics=usage.diagnostics + records,
                                interface_diagnostics=(interface, interface))
            default = render_report(module, clients, augmented)
            self.assert_coverage(default, 2)
            self.assertNotIn(reason, default)
            self.assertNotIn(interface.message, default)
            detailed = render_report(module, clients, augmented,
                                     show_analysis_limitations=True)
            self.assert_coverage(detailed, 2)
            rows = [row for row in detailed.splitlines() if 'port.lookup' in row]
            self.assertEqual(len(rows), 1, detailed)
            self.assertEqual(rows[0].count(reason), 1)
            self.assertEqual(rows[0].count(interface.message), 1)
            self.assertEqual(self.outside_coverage(default, 2),
                             self.outside_coverage(detailed, 2))
            reports.append(detailed)
        self.assertEqual(*reports)


if __name__ == '__main__':
    unittest.main()
