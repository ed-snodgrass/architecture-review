"""Contracts for the first pending iteration-002 task: limitations and stability.

Analyze disposable source only. Do not compile/run Java or prescribe report prose.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from archr.discovery import discover_clients
from archr.module import load_module
from archr.report import render_report
from archr.traversal import trace_usage


ENTRY_POINT = Path(__file__).resolve().parents[1] / 'arch-r'


class AnalysisLimitationsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='arch_r_limitations_')
        self.addCleanup(temp.cleanup)
        self.caller = Path(temp.name)
        self.module = self.caller / 'orders'
        (self.module / 'src/main/java').mkdir(parents=True)

    def put(self, name, source):
        path = self.module / 'src/main/java/sample' / (name + '.java')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')

    def client(self):
        self.put('Client', '''package sample;
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient(name="products", url="${product.url}")
public interface Client {
    String get(String id);
}
''')

    def report_bytes(self):
        before = {p.relative_to(self.module): p.read_bytes()
                  for p in self.module.rglob('*') if p.is_file()}
        result = subprocess.run(
            [str(ENTRY_POINT), 'analyze', str(self.module)], cwd=self.caller,
            capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertEqual(before, {p.relative_to(self.module): p.read_bytes()
                                  for p in self.module.rglob('*') if p.is_file()})
        return (self.caller / 'arch-r-report-orders.md').read_bytes()

    def limitations(self, report):
        match = re.search(r'^## Limitations\s*$', report, re.M)
        self.assertIsNotNone(match, report)
        return re.split(r'^## ', report[match.end():], maxsplit=1, flags=re.M)[0]

    def assert_depth(self, text, depth):
        # Require an applied call-step limit, not an incidental numeral in a citation.
        number = {1: r'(?:1|one)', 2: r'(?:2|two)', 3: r'(?:3|three)'}[depth]
        self.assertRegex(text.lower(), r'(?:limit|depth)[^.\n]*\b' + number
                         + r'\b[^.\n]*(?:call|step)|\b' + number
                         + r'\b[^.\n]*(?:call|step)[^.\n]*(?:limit|depth)')

    def test_supported_receiver_forms_are_explained_in_limitations(self):
        self.client()
        self.put('Order', '''package sample;
class Order {
    private final Client client;
    Order(Client client) { this.client = client; }
    String place(String id) { return this.client.get(id); }
}
''')
        report = self.report_bytes().decode('utf-8')
        self.assertNotIn('did not inspect callers', report.lower())
        text = self.limitations(report).lower()
        self.assertRegex(text, r'(?:explicit|declared|typed)[^.\n]*field|field[^.\n]*(?:explicit|declared|typed)')
        self.assertIn('field.method', text)
        self.assertIn('this.field.method', text)
        self.assertRegex(text, r'constructor[^.\n]*inject|inject[^.\n]*constructor')
        self.assert_depth(text, 2)

    def test_applied_depth_is_documented_even_without_feign_findings(self):
        self.put('Plain', 'package sample; class Plain {}\n')
        report = self.report_bytes().decode('utf-8')
        self.assertNotIn('did not inspect callers', report.lower())
        self.assert_depth(self.limitations(report), 2)

    def test_applied_depth_is_documented_for_declaration_only_client(self):
        self.client()
        report = self.report_bytes().decode('utf-8')
        self.assertRegex(report.lower(), r'no supported caller.*found')
        self.assert_depth(self.limitations(report), 2)

    def test_limitations_use_the_supplied_traversal_depth_not_a_fixed_two(self):
        self.client()
        module = load_module(str(self.module))
        clients = discover_clients(module)
        for depth in (1, 3):
            with self.subTest(depth=depth):
                report = render_report(module, clients, trace_usage(module, max_depth=depth))
                self.assert_depth(self.limitations(report), depth)

    def test_source_boundary_and_runtime_caveats_remain_explicit(self):
        self.client()
        text = self.limitations(self.report_bytes().decode('utf-8')).lower()
        self.assertIn('src/main/java', text)
        self.assertRegex(text, r'(?:did not|does not|without|not)[^.\n]*compil')
        self.assertRegex(text, r'(?:did not|does not|without|not)[^.\n]*(?:run|execut)')
        self.assertRegex(text, r'(?:did not|does not|without|not)[^.\n]*modif')
        self.assertRegex(text, r'runtime[^.\n]*(?:not|unverified)|(?:not|unverified)[^.\n]*runtime')
        self.assertRegex(text, r'(?:unsupported|unresolved)[^.\n]*(?:absence|no caller)|'
                         r'(?:absence|no caller)[^.\n]*(?:unsupported|unresolved)')

    def test_unsupported_local_receiver_is_not_silently_proof_of_absence(self):
        self.client()
        self.put('LocalOnly', '''package sample;
class LocalOnly {
    void work(Client supplied) {
        Client local = supplied;
        local.get("id");
    }
}
''')
        report = self.report_bytes().decode('utf-8')
        self.assertRegex(report.lower(), r'no supported caller.*found')
        self.assertIn('src/main/java/sample/LocalOnly.java:5', report)
        self.assertRegex(report.lower(), r'(?:unsupported|unresolved)[^\n]*(?:local|receiver)|'
                         r'(?:local|receiver)[^\n]*(?:unsupported|unresolved)')

    def test_multiple_calls_and_unresolved_evidence_are_byte_stable(self):
        self.client()
        # Intentionally create reverse-alphabetical files and repeated class links.
        for name in ('ZOrder', 'AOrder'):
            self.put(name, f'''package sample;
class {name} {{
    Client client;
    String work(String id) {{
        client.get(id);
        return this.client.get(id);
    }}
}}
''')
        self.put('Unresolved', '''package sample;
class Unresolved {
    OutsideModule outside;
    void work() { outside.fetch(); }
}
''')
        first = self.report_bytes()
        report = first.decode('utf-8')
        for name in ('AOrder', 'ZOrder'):
            for line in (5, 6):
                self.assertIn(f'src/main/java/sample/{name}.java:{line}', report)
        self.assertIn('src/main/java/sample/Unresolved.java:4', report)
        self.assertEqual(first, self.report_bytes())
        self.assertEqual(first, self.report_bytes())
        self.assertEqual(list(self.caller.glob('arch-r-report-*.md')),
                         [self.caller / 'arch-r-report-orders.md'])
        self.assertFalse(list(self.caller.glob('.arch-r-*.tmp')))


if __name__ == '__main__':
    unittest.main()
