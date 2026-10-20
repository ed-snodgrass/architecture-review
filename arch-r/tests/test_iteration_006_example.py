"""The published example is rendered from source, not a hypothetical catch."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tests.test_usage_report import ENTRY_POINT


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path('tests/fixtures/feign-failure/order-service')
EXAMPLE = ROOT / 'example-reports/006-arch-r-report-order-service.md'


class Iteration006ExampleTests(unittest.TestCase):
    def test_example_matches_fixture_and_modes_preserve_guidance(self):
        module = ROOT / FIXTURE
        before = {p.relative_to(module): p.read_bytes()
                  for p in module.rglob('*') if p.is_file()}
        with tempfile.TemporaryDirectory(prefix='archr_006_') as work:
            reports = []
            for flags in ([], ['--show-analysis-limitations']):
                result = subprocess.run(
                    [str(ENTRY_POINT), 'analyze', str(module), *flags],
                    cwd=work, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, '')
                reports.append((Path(work) / 'arch-r-report-order-service.md').read_text())
        default, detailed = reports
        self.assertEqual(default.replace(str(module), FIXTURE.as_posix()),
                         EXAMPLE.read_text(encoding='utf-8'))
        guidance = lambda text: text.split('## Adapter Review Guidance', 1)[1].split(
            '## Findings with Evidence', 1)[0]
        self.assertEqual(guidance(default), guidance(detailed))
        self.assertIn('shop.OrderService.placeOrder calls shop.ProductClient.getProduct', default)
        self.assertIn('Call: src/main/java/shop/OrderService.java:14', default)
        self.assertIn('catch: src/main/java/shop/OrderService.java:15', default)
        self.assertEqual(before, {p.relative_to(module): p.read_bytes()
                                  for p in module.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
