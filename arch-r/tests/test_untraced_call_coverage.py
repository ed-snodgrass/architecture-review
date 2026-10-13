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
        sections = re.split(r'(?=^## )', report, flags=re.M)
        return [s for s in sections if s.startswith('## Finding ')
                or s.startswith('## Architectural connections')]

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
        self.assertEqual(len(re.findall(r'^## Finding ', report, re.M)), 1)
        self.assertIn('Found 1 statically declared Feign outbound HTTP dependency.', report)
        for method in ('getId', 'getName', 'getCode', 'getRegion', 'getStatus', 'getToken', 'getTime'):
            self.assertNotIn(method, report)
        for line in range(6, 13):
            self.assertNotIn(f'src/main/java/sample/Order.java:{line}', report)
        self.assertNotIn('unsupported-receiver', report)
        self.assertNotIn('Request', report)
        self.assertIn('src/main/java/sample/Order.java:5', report)

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
                product = next(s for s in findings if re.match(r'## Finding \d+: products', s))
                billing = next(s for s in findings if 'billing' in s and s.startswith('## Finding'))
                self.assertIn('missing', product)
                self.assertNotIn('products.missing', billing)
                self.assertNotIn(first.message, billing)
                self.assertEqual(main(['analyze', str(self.module), FLAG]), 0)
                detailed = self.output.read_text(encoding='utf-8')
        finally:
            os.chdir(old_cwd)
        self.assert_coverage(detailed, 1)
        sections = re.split(r'(?=^## )', detailed, flags=re.M)
        context = '\n'.join(s for s in sections if not s.startswith('## Finding '))
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
            self.assertIn('Runtime wiring is unverified', report)
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
        self.assertIn('Cycle cutoff invocation', report)
        self.assertIn('src/main/java/sample/Order.java:5', report)
        self.assertIn('src/main/java/sample/Checkout.java:4', report)
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
