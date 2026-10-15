"""Iteration 005: bounded, report-relevant limitations without a syntax catalog."""
import unittest

from archr.discovery import discover_clients
from archr.module import load_module
from archr.report import render_report
from archr.traversal import trace_usage
from tests import test_analysis_limitations as fixtures


class ConciseLimitationsTests(unittest.TestCase):
    setUp = fixtures.AnalysisLimitationsTests.setUp
    put = fixtures.AnalysisLimitationsTests.put
    client = fixtures.AnalysisLimitationsTests.client

    def render(self, *, depth=2, traversal=True):
        module = load_module(str(self.module))
        usage = trace_usage(module, max_depth=depth) if traversal else None
        return render_report(module, discover_clients(module), usage)

    def test_summary_explains_statuses_and_preserves_uncertainty_once(self):
        self.client()
        report = self.render()
        limitations = report.split('## Limitations\n', 1)[1]
        self.assertLess(len(limitations.split()), 320)
        for status in ('Caller found', 'No caller found', 'Caller unresolved'):
            self.assertEqual(limitations.count(f'**{status}**'), 1)
        for fact in ('src/main/java', 'did not compile, run, or modify',
                     'runtime wiring, execution, or reachability',
                     'limit is 2 call steps', 'property placeholders are not resolved',
                     'OpenFeign', 'JpaRepository', 'JdbcTemplate', 'RestTemplate',
                     'WebClient', 'field.method(...)', 'this.field.method(...)',
                     'No untraced call sites recorded within supported analysis.'):
            self.assertIn(fact, limitations)
        self.assertNotIn('${product.url}', limitations)
        self.assertIn('${product.url}', report.split('## Limitations\n')[0])
        for catalog_item in ('lambdas', 'reflection', 'method references', 'qualifiers',
                             'queryForObject', 'batchUpdate', 'exchangeToFlux'):
            self.assertNotIn(catalog_item, limitations)
        self.assertEqual(report, self.render())

    def test_empty_report_retains_scope_and_actual_depth(self):
        self.put('Plain', 'package sample; class Plain {}\n')
        for depth in (1, 3):
            with self.subTest(depth=depth):
                limitations = self.render(depth=depth).split('## Limitations\n')[1]
                self.assertIn(f'limit is {depth} call steps', limitations)
                self.assertIn('Other HTTP and database mechanisms are outside scope', limitations)
        self.assertIn('No usage traversal was supplied', self.render(traversal=False))


if __name__ == '__main__':
    unittest.main()
