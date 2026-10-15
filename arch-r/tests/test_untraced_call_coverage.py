"""Iteration 003 coverage contracts; only disposable Java source is analyzed.

CLI/report assertions avoid a proposed coverage model or section heading.
The duplicate-reason test injects retained diagnostics at the existing traversal
boundary: real source cannot reliably trigger multiple reasons for one site.
"""
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from archr.cli import main
from archr.module import load_module
from archr.resolution import resolve_index
from archr.indexing import index_module
from archr.traversal import trace_usage


ENTRY_POINT = Path(__file__).resolve().parents[1] / 'arch-r'
FLAG = '--show-analysis-limitations'
ZERO = 'No untraced call sites recorded within supported analysis.'


class UntracedCallCoverageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='arch_r_coverage_')
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.module = self.work / 'orders'
        (self.module / 'src/main/java/sample').mkdir(parents=True)
        self.output = self.work / 'arch-r-report-orders.md'

    def put(self, name, source):
        path = self.module / 'src/main/java/sample' / (name + '.java')
        path.write_text(source, encoding='utf-8')

    def client(self, name='Client', system='products', url='https://products.example'):
        self.put(name, f'''package sample;
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient(name="{system}", url="{url}")
interface {name} {{ String get(String id); }}
''')

    def snapshot(self):
        return {str(p.relative_to(self.module)):
                (p.stat().st_mode, p.read_bytes() if p.is_file() else None)
                for p in self.module.rglob('*')}

    def run_cli(self, details=False, before=False, path=None):
        args = ['analyze', str(path or self.module)]
        if details:
            args.insert(1 if before else len(args), FLAG)
        return subprocess.run([str(ENTRY_POINT), *args], cwd=self.work,
                              capture_output=True, text=True, timeout=10)

    def report(self, details=False, before=False):
        snapshot = self.snapshot()
        result = self.run_cli(details, before)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertEqual(snapshot, self.snapshot())
        self.assertEqual(list(self.work.glob('arch-r-report-*.md')), [self.output])
        self.assertFalse(list(self.work.glob('.arch-r-*.tmp')))
        return self.output.read_text(encoding='utf-8')

    def assert_coverage(self, report, count):
        if count == 0:
            self.assertIn(ZERO, report)
            self.assertNotRegex(report.lower(), r'\b(?:full|complete) (?:java )?coverage\b')
            return
        match = re.search(r'[^\n]*\b' + str(count)
                          + r' call sites? (?:was|were) not traced[^\n]*', report)
        self.assertIsNotNone(match, report)
        self.assertRegex(match.group().lower(), r'external effects.*(?:cannot|can.t|not).*ruled out')
        self.assertIn(FLAG, report)
        # The brief coverage paragraph must not grow into a default site list.
        paragraph = re.split(r'\n\s*\n', report)
        coverage = next(p for p in paragraph if match.group() in p)
        sentences = re.findall(r'[^.!?]+[.!?](?:\s|$)', coverage)
        self.assertLessEqual(len(sentences), 2, coverage)
        self.assertLessEqual(len(coverage.split()), 55, coverage)

    def architectural_sections(self, report):
        from tests.report_sections import findings, section
        return findings(report) + [section(report, 'Architectural Connections')]

    def seven_sites(self):
        self.client()
        self.put('Order', '''package sample;
class Order {
    Client client;
    void place(Request request) {
        client.get("id");
        request.getId();
        request.getName();
        request.getCode();
        request.getRegion();
        request.getStatus();
        request.getToken();
        request.getTime();
    }
}
''')

    def test_seven_unrelated_sites_are_summary_only_not_findings_or_advice(self):
        self.seven_sites()
        usage = trace_usage(load_module(str(self.module)))
        self.assertEqual(len(usage.diagnostics), 7)
        self.assertTrue(all(d.code == 'unsupported-receiver' for d in usage.diagnostics))
        report = self.report()
        self.assert_coverage(report, 7)
        from tests.report_sections import findings
        self.assertEqual(len(findings(report)), 1)
        self.assertIn('Found 1 statically declared Feign outbound HTTP dependency.', report)
        for method in ('getId', 'getName', 'getCode', 'getRegion', 'getStatus', 'getToken', 'getTime'):
            self.assertNotIn(method, report)
        for line in range(6, 13):
            self.assertNotIn(f'src/main/java/sample/Order.java:{line}', report)
        self.assertNotIn('unsupported-receiver', report)
        self.assertNotIn('Request', report)
        self.assertIn('sample.Order.place → sample.Client.get', report)
        from tests.analysis_evidence import locations
        self.assertIn('src/main/java/sample/Order.java:5', locations(self.module))

    def test_details_flag_positions_preserve_architecture_and_order_sites(self):
        self.seven_sites()
        default = self.report()
        detailed = self.report(details=True)
        self.assert_coverage(detailed, 7)
        self.assertEqual(self.architectural_sections(default),
                         self.architectural_sections(detailed))
        self.assertIn('Found 1 statically declared Feign outbound HTTP dependency.', detailed)
        positions = []
        for line, method in zip(range(6, 13),
                                ('getId', 'getName', 'getCode', 'getRegion',
                                 'getStatus', 'getToken', 'getTime')):
            citation = f'src/main/java/sample/Order.java:{line}'
            self.assertEqual(detailed.count(citation), 1, detailed)
            positions.append(detailed.index(citation))
            entry = next(row for row in detailed.splitlines() if citation in row)
            self.assertIn(method, entry)
            self.assertRegex(entry.lower(), r'not.*(?:field|follow|support|trace)|unsupported')
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(detailed, self.report(details=True, before=True))
        self.assertEqual(detailed, self.report(details=True))
        self.assertEqual(default, self.report())
        self.assertEqual(default, self.report())

    def test_same_line_identical_calls_are_distinct_sites(self):
        self.put('Plain', '''package sample;
class Plain {
    void work(Request request) { request.getId(); request.getId(); }
}
''')
        self.assert_coverage(self.report(), 2)
        detailed = self.report(details=True)
        self.assert_coverage(detailed, 2)
        entries = [line for line in detailed.splitlines()
                   if 'src/main/java/sample/Plain.java:3' in line]
        self.assertEqual(len(entries), 2, detailed)
        self.assertNotEqual(entries[0], entries[1], 'Same-line sites need distinguishable locations/identity')
        self.assertTrue(all('getId' in entry for entry in entries))

    def test_same_line_sites_deduplicate_reasons_without_merging_calls(self):
        self.put('Plain', '''package sample;
class Plain {
    void work(Request request) { request.alpha(); request.beta(); request.alpha(); }
}
''')
        usage = trace_usage(load_module(str(self.module)))
        self.assertEqual(len(usage.diagnostics), 3)
        self.assertEqual(len({d.invocation for d in usage.diagnostics}), 3)
        # Repeat traversal results and attach another reason to each real site.
        # Neither repetition nor different reasons may change the site count.
        extra_reason = 'The receiver type cannot be resolved within supported analysis.'
        augmented = replace(usage, diagnostics=tuple(
            item for diagnostic in reversed(usage.diagnostics)
            for item in (diagnostic, replace(diagnostic, message=extra_reason), diagnostic)
        ))
        old_cwd = Path.cwd()
        try:
            os.chdir(self.work)
            with patch('archr.cli.trace_usage', return_value=augmented), \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main(['analyze', str(self.module)]), 0)
                default = self.output.read_text(encoding='utf-8')
                self.assert_coverage(default, 3)
                for hidden in ('Plain.java:3', 'request.alpha', 'request.beta',
                               'unsupported-receiver', extra_reason):
                    self.assertNotIn(hidden, default)
                self.assertEqual(main(['analyze', str(self.module), FLAG]), 0)
                detailed = self.output.read_text(encoding='utf-8')
        finally:
            os.chdir(old_cwd)
        self.assert_coverage(detailed, 3)
        entries = [line for line in detailed.splitlines()
                   if 'src/main/java/sample/Plain.java:3' in line]
        self.assertEqual(len(entries), 3, detailed)
        self.assertEqual(len(set(entries)), 3, detailed)
        self.assertIn('alpha', entries[0])
        self.assertIn('beta', entries[1])
        self.assertIn('alpha', entries[2])
        for entry in entries:
            self.assertEqual(entry.count(extra_reason), 1, entry)
            self.assertEqual(entry.count(usage.diagnostics[0].message), 1, entry)

    def test_flag_positions_with_relative_module_path_containing_spaces(self):
        self.module = self.module.rename(self.work / 'orders with spaces')
        self.output = self.work / load_module(str(self.module)).report_filename
        self.put('Plain', '''package sample;
class Plain {
    void work(Request request) { request.getId(); }
}
''')
        reports = []
        snapshot = self.snapshot()
        for before in (False, True):
            with self.subTest(before=before):
                result = self.run_cli(details=True, before=before,
                                      path=Path(self.module.name))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, '')
                report = self.output.read_text(encoding='utf-8')
                self.assert_coverage(report, 1)
                self.assertIn('src/main/java/sample/Plain.java:3', report)
                self.assertIn('getId', report)
                reports.append(report)
        self.assertEqual(reports[0], reports[1])
        self.assertEqual(snapshot, self.snapshot())
        self.assertEqual(list(self.work.glob('arch-r-report-*.md')), [self.output])

    def test_flag_is_accepted_before_and_after_path(self):
        for before in (False, True):
            with self.subTest(before=before):
                self.report(details=True, before=before)

    def test_detailed_then_default_replaces_same_file_and_removes_details(self):
        self.put('Plain', '''package sample;
class Plain {
    void work(Request request) { request.getId(); }
}
''')
        detailed = self.report(details=True)
        detailed_bytes = self.output.read_bytes()
        self.assertIn('src/main/java/sample/Plain.java:3', detailed)
        self.assertEqual(detailed, self.report(details=True))
        self.assertEqual(detailed_bytes, self.output.read_bytes())
        default = self.report()
        default_bytes = self.output.read_bytes()
        self.assertNotIn('src/main/java/sample/Plain.java:3', default)
        self.assertNotIn('getId', default)
        self.assertEqual(default, self.report())
        self.assertEqual(default_bytes, self.output.read_bytes())
        self.assertNotEqual(detailed_bytes, default_bytes)

    def test_same_line_invocation_identity_survives_retained_diagnostics(self):
        self.put('Plain', '''package sample;
class Plain {
    void work(Request request) { request.getId(); request.getId(); }
}
''')
        diagnostics = trace_usage(load_module(str(self.module))).diagnostics
        self.assertEqual(len(diagnostics), 2)
        self.assertNotEqual(diagnostics[0].invocation, diagnostics[1].invocation,
                            'Distinct invocation sites must not collapse in deduplication')

    def test_retains_all_resolver_diagnostics_independent_of_client_traversal(self):
        self.client()
        self.client('BillingClient', 'billing')
        self.put('Shared', '''package sample;
class Shared {
    Client products;
    BillingClient billing;
    void work(Request request) { products.get("id"); billing.get("id"); request.getId(); }
}
''')
        self.put('First', '''package sample;
class First { Shared shared; void run(Request request) { shared.work(request); } }
''')
        self.put('Second', '''package sample;
class Second { Shared shared; void run(Request request) { shared.work(request); } }
''')
        self.put('Disconnected', '''package sample;
class Disconnected { void run(Request request) { request.getName(); } }
''')
        module = load_module(str(self.module))
        recorded = resolve_index(index_module(module)).diagnostics
        self.assertEqual(len(recorded), 2)
        self.assertEqual({d.code for d in recorded}, {'unsupported-receiver'})
        for depth in (1, 2, 3):
            with self.subTest(depth=depth):
                usage = trace_usage(module, max_depth=depth)
                self.assertEqual(usage.diagnostics, recorded,
                                 'Traversal must retain even disconnected diagnostics unchanged')
                self.assertEqual({c.client_type for c in usage.chains},
                                 {'sample.Client', 'sample.BillingClient'})
                if depth > 1:
                    self.assertEqual(len(usage.chains), 4)
        self.assert_coverage(self.report(), 2)
        detailed = self.report(details=True)
        self.assert_coverage(detailed, 2)
        for path, line, call in (('Shared', 5, 'getId'), ('Disconnected', 2, 'getName')):
            entries = [row for row in detailed.splitlines()
                       if f'src/main/java/sample/{path}.java:{line}' in row and call in row]
            self.assertEqual(len(entries), 1, detailed)

    def test_module_wide_identity_includes_source_path(self):
        # Equal-length type names keep every call's line and lexer offset equal.
        for name in ('Alpha', 'Bravo'):
            self.put(name, f'''package sample;
class {name} {{
    void work(Request request) {{ request.getId(); request.getId(); }}
}}
''')
        diagnostics = trace_usage(load_module(str(self.module))).diagnostics
        self.assertEqual(len(diagnostics), 4)
        self.assertEqual(len({d.invocation for d in diagnostics}), 4)
        by_path = {}
        for diagnostic in diagnostics:
            by_path.setdefault(diagnostic.invocation.source_path, []).append(diagnostic.invocation)
        self.assertEqual(len(by_path), 2)
        calls = list(by_path.values())
        self.assertEqual([i.source_offset for i in calls[0]],
                         [i.source_offset for i in calls[1]])
        self.assert_coverage(self.report(), 4)
        detailed = self.report(details=True)
        self.assert_coverage(detailed, 4)
        for name in ('Alpha', 'Bravo'):
            entries = [row for row in detailed.splitlines()
                       if f'src/main/java/sample/{name}.java:3' in row]
            self.assertEqual(len(entries), 2, detailed)
            self.assertEqual(len(set(entries)), 2)

    def test_same_line_sites_across_methods_and_nested_calls_remain_distinct(self):
        self.put('Plain', '''package sample;
class Plain {
    void first(Request request) { request.getId(); } void second(Request request) { request.getId(); request.accept(request.getId()); }
}
''')
        diagnostics = trace_usage(load_module(str(self.module))).diagnostics
        self.assertEqual(len(diagnostics), 4)
        self.assertEqual({d.code for d in diagnostics}, {'unsupported-receiver'})
        self.assertEqual({d.invocation.line for d in diagnostics}, {3})
        self.assertEqual(len({d.invocation for d in diagnostics}), 4)
        self.assertEqual(sorted(d.invocation.method_name for d in diagnostics),
                         ['accept', 'getId', 'getId', 'getId'])
        self.assertEqual({d.caller_method.name for d in diagnostics}, {'first', 'second'})
        self.assert_coverage(self.report(), 4)
        detailed = self.report(details=True)
        self.assert_coverage(detailed, 4)
        entries = [row for row in detailed.splitlines()
                   if 'src/main/java/sample/Plain.java:3' in row]
        self.assertEqual(len(entries), 4, detailed)
        self.assertEqual(len(set(entries)), 4,
                         'Method ownership and nesting must not merge same-line sites')

    def test_details_sort_by_path_then_location_not_creation_order(self):
        for name in ('ZPlain', 'APlain'):
            self.put(name, f'''package sample;
class {name} {{
    void work(Request request) {{
        request.first();
        request.second();
    }}
}}
''')
        detailed = self.report(details=True)
        self.assert_coverage(detailed, 4)
        citations = [f'src/main/java/sample/{name}.java:{line}'
                     for name in ('APlain', 'ZPlain') for line in (4, 5)]
        positions = [detailed.index(citation) for citation in citations]
        self.assertEqual(positions, sorted(positions))

    def test_coverage_without_findings_and_zero_gaps(self):
        self.put('Plain', '''package sample;
class Plain {
    void work(Request request) { request.getId(); }
}
''')
        default = self.report()
        self.assertIn('No statically declared Feign outbound HTTP dependencies were found.', default)
        self.assert_coverage(default, 1)
        self.assertNotIn('Plain.java:3', default)
        detailed = self.report(details=True)
        self.assert_coverage(detailed, 1)
        self.assertIn('src/main/java/sample/Plain.java:3', detailed)
        self.assertIn('getId', detailed)
        self.put('Plain', 'package sample; class Plain {}\n')
        for has_client in (False, True):
            if has_client:
                self.client(url='${products.url}')
            for details in (False, True):
                with self.subTest(has_client=has_client, details=details):
                    report = self.report(details)
                    self.assert_coverage(report, 0)
                    self.assertNotIn('Plain.java:', report)
                    self.assertNotIn('unsupported-receiver', report)
                    if has_client:
                        self.assertIn('destination unresolved', report)

    def test_shared_relevant_site_counts_once_and_reasons_are_deduplicated(self):
        self.client()
        self.client('BillingClient', 'billing')
        self.put('Shared', '''package sample;
class Shared {
    Client products;
    BillingClient billing;
    void work(String id) { products.get(id); billing.get(id); products.missing(id); }
}
''')
        module = load_module(str(self.module))
        usage = trace_usage(module)
        self.assertEqual(len(usage.diagnostics), 1)
        original = usage.diagnostics[0]
        # Two distinct plain-language reasons, with both repeated. Preserve the
        # actual invocation identity; do not invent a future coverage API.
        first = replace(original, message='The declared receiver has no matching method.')
        second = replace(original, code='unsupported-syntax',
                         message='Generic method resolution is not supported.')
        duplicated = replace(usage, diagnostics=(first, second, first, second, original))
        old_cwd = Path.cwd()
        try:
            os.chdir(self.work)
            with patch('archr.cli.trace_usage', return_value=duplicated), \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main(['analyze', str(self.module)]), 0)
                default = self.output.read_text(encoding='utf-8')
                self.assert_coverage(default, 1)
                # Explicit Client field evidence makes this site relevant to
                # products, but not billing merely because it shares a method.
                findings = self.architectural_sections(default)
                from tests.report_sections import finding
                product = finding(default, 'products')
                billing = finding(default, 'billing')
                self.assertIn('missing', product)
                self.assertNotIn('products.missing', billing)
                self.assertNotIn(first.message, billing)
                self.assertEqual(main(['analyze', str(self.module), FLAG]), 0)
                detailed = self.output.read_text(encoding='utf-8')
        finally:
            os.chdir(old_cwd)
        self.assert_coverage(detailed, 1)
        from tests.report_sections import section
        context = section(detailed, 'Limitations')
        self.assertEqual(context.count('src/main/java/sample/Shared.java:5'), 1, context)
        self.assertEqual(context.count(first.message), 1, context)
        self.assertEqual(context.count(second.message), 1, context)
        self.assertEqual(self.architectural_sections(default), self.architectural_sections(detailed))

    def test_followed_possible_link_destination_and_traversal_limits_are_not_gaps(self):
        self.client(url='${products.url}')
        self.put('Port', 'package sample; interface Port { String lookup(String id); }\n')
        self.put('Gateway', '''package sample;
class Gateway implements Port {
    Client client;
    public String lookup(String id) { return client.get(id); }
}
''')
        self.put('Order', '''package sample;
class Order {
    Port port;
    Order other;
    String place(String id) { return port.lookup(id); }
    String cycle(String id) { other.cycle(id); return port.lookup(id); }
}
''')
        self.assertFalse(trace_usage(load_module(str(self.module))).diagnostics)
        for details in (False, True):
            report = self.report(details)
            self.assert_coverage(report, 0)
            self.assertIn('destination unresolved', report)
            self.assertIn('Possible chain', report)
            self.assertIn('verify that runtime wiring connects', report)
            self.assertRegex(report.lower(), r'boundary|limit')

    def test_cycle_and_depth_cutoffs_do_not_inflate_untraced_count(self):
        self.client()
        self.put('Order', '''package sample;
class Order {
    Client client;
    Order other;
    void place(String id) { client.get(id); other.place(id); }
}
''')
        self.put('Checkout', '''package sample;
class Checkout {
    Order order;
    void checkout(String id) { order.place(id); }
}
''')
        usage = trace_usage(load_module(str(self.module)))
        self.assertEqual({chain.boundary for chain in usage.chains}, {'cycle', 'depth'})
        self.assertFalse(usage.diagnostics)
        report = self.report()
        self.assert_coverage(report, 0)
        self.assertIn('Cycle cutoff:', report)
        from tests.analysis_evidence import locations
        retained = locations(self.module)
        self.assertIn('src/main/java/sample/Order.java:5', retained)
        self.assertIn('src/main/java/sample/Checkout.java:4', retained)
        detailed = self.report(details=True)
        self.assert_coverage(detailed, 0)
        self.assertEqual(self.architectural_sections(report), self.architectural_sections(detailed))

    def test_invalid_input_and_atomic_failure_preserve_prior_report_in_both_modes(self):
        self.seven_sites()
        successful = self.report()
        for details in (False, True):
            with self.subTest(details=details):
                invalid = self.run_cli(details=details, path=self.work / 'missing')
                self.assertNotEqual(invalid.returncode, 0)
                self.assertIn('arch-r:', invalid.stderr)
                self.assertNotIn('Traceback', invalid.stderr)
                self.assertEqual(successful, self.output.read_text(encoding='utf-8'))
                old_cwd = Path.cwd()
                errors = io.StringIO()
                try:
                    os.chdir(self.work)
                    with patch('archr.cli.os.replace', side_effect=OSError('replacement failed')), \
                            redirect_stdout(io.StringIO()), redirect_stderr(errors):
                        args = ['analyze', str(self.module)] + ([FLAG] if details else [])
                        try:
                            status = main(args)
                        except SystemExit as exc:
                            self.fail(f'Valid analysis options were rejected: {exc}')
                        self.assertEqual(status, 1)
                finally:
                    os.chdir(old_cwd)
                self.assertIn('Cannot write report', errors.getvalue())
                self.assertNotIn('Traceback', errors.getvalue())
                self.assertEqual(successful, self.output.read_text(encoding='utf-8'))
                self.assertFalse(list(self.work.glob('.arch-r-*.tmp')))


if __name__ == '__main__':
    unittest.main()
