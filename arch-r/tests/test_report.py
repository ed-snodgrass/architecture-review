from dataclasses import replace
from pathlib import Path
import unittest

from archr.discovery import FeignClient, extract_clients
from archr.module import Module
from archr.report import render_report


IMPORTS = '''import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.*;
'''


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.module = Module(Path('/modules/order-service'),
                             Path('/modules/order-service/src/main/java'),
                             'order-service')

    def clients(self, source, path='src/main/java/Clients.java'):
        return extract_clients(IMPORTS + source, path)

    def test_literal_finding_operations_and_evidence(self):
        clients = self.clients('''@FeignClient(name = "inventory", url = "https://inventory.example")
public interface InventoryClient {
    @GetMapping("/items/{id}")
    Item getItem(String id);
}''')
        report = render_report(self.module, clients)
        for text in ('**Module:** order-service', '/modules/order-service',
                     'Found 1 statically declared Feign outbound HTTP dependency.',
                     'order-service makes an outbound HTTP connection to inventory',
                     '**External system:** inventory', 'https://inventory.example',
                     'High confidence', 'literal destination are visible in source',
                     'GET /items/{id}', 'src/main/java/Clients.java:3',
                     'src/main/java/Clients.java:5', 'InventoryClient'):
            self.assertIn(text, report)
        diagram = report.split('```mermaid\n')[1].split('```')[0]
        self.assertIn('C4Context', diagram)
        self.assertIn('System(module, "order-service"', diagram)
        self.assertIn('Container(feign_1, "InventoryClient"', diagram)
        self.assertIn('System_Ext(external_1, "inventory"', diagram)
        self.assertIn('Rel(module, feign_1,', diagram)
        self.assertIn('Rel(feign_1, external_1,', diagram)
        self.assertNotIn('getItem', diagram)
        self.assertNotIn('/items', diagram)

    def test_placeholder_missing_and_expression_destinations(self):
        cases = [
            ('url = "${pricing.url}"', '${pricing.url}', 'property placeholder'),
            ('url = "https://${host}/api"', 'https://${host}/api', 'property placeholder'),
            ('url = Settings.URL', 'Settings.URL', 'not a literal URL'),
            ('url = ""', 'Not specified', 'no destination URL'),
            ('', 'Not specified', 'no destination URL'),
        ]
        for attribute, destination, reason in cases:
            with self.subTest(attribute=attribute):
                suffix = ', ' + attribute if attribute else ''
                report = render_report(self.module, self.clients(
                    '@FeignClient(name = "pricing"' + suffix + ') interface Pricing {}'))
                self.assertIn(destination, report)
                self.assertIn('destination unresolved', report)
                self.assertIn('Lower confidence', report)
                self.assertIn(reason, report)
                self.assertNotIn('High confidence', report)

    def test_alias_multiple_clients_and_stable_order(self):
        clients = self.clients('''@FeignClient(value = "shipping", url = "https://shipping.example")
interface Shipping {}
@FeignClient("pricing") interface Pricing {}''')
        other = self.clients('@FeignClient("first") interface First {}',
                             'src/main/java/A.java')[0]
        clients.append(other)
        report = render_report(self.module, clients)
        self.assertEqual(report, render_report(self.module, reversed(clients)))
        self.assertEqual(report, render_report(self.module, clients))
        self.assertIn('Found 3 statically declared Feign outbound HTTP dependencies.', report)
        self.assertLess(report.index('Finding 1: first'), report.index('Finding 2: shipping'))
        self.assertIn('Finding 3: pricing', report)
        self.assertEqual(report.count('```mermaid'), 1)
        self.assertEqual(report.count('System_Ext('), 3)
        self.assertTrue(report.endswith('\n'))

    def test_zero_findings_and_limitations(self):
        report = render_report(self.module, [])
        self.assertIn('No statically declared Feign outbound HTTP dependencies were found.', report)
        self.assertIn('does not mean the module makes no outbound calls by other means', report)
        self.assertIn('did not inspect callers', report)
        self.assertIn('separate domain-facing port or adapter is needed', report)
        self.assertIn('not assumed to be a sufficient architectural adapter', report)
        self.assertEqual(report.count('```mermaid'), 1)
        self.assertNotIn('System_Ext(', report)
        self.assertNotIn('## Finding', report)

    def test_unknown_names_and_operations_are_not_invented(self):
        clients = self.clients('''@FeignClient(name = Names.SYSTEM) interface Unknown {
 @RequestMapping void call();
}
@FeignClient interface Missing {}''')
        report = render_report(self.module, clients)
        self.assertIn('External system name unresolved: Names.SYSTEM', report)
        self.assertIn('External system name not specified', report)
        self.assertIn('HTTP method unspecified path unspecified', report)
        self.assertIn('No supported mapped HTTP operations were discovered', report)
        self.assertNotIn('GET /', report)

    def test_arrays_and_interface_evidence(self):
        clients = self.clients('''@RequestMapping("/api")
@FeignClient("inventory") interface Inventory {
 @RequestMapping(path = {"/one", "/two"}, method = {RequestMethod.GET, RequestMethod.POST})
 void many();
}''')
        report = render_report(self.module, clients)
        for operation in ('GET /api/one', 'GET /api/two', 'POST /api/one', 'POST /api/two'):
            self.assertIn(operation, report)
        self.assertIn('src/main/java/Clients.java:3; src/main/java/Clients.java:5', report)

    def test_markdown_and_mermaid_injection_are_escaped(self):
        hostile = 'evil"), System_Ext(injected, "x")\n```\n<script>&[*]\\|'
        module = replace(self.module, name=hostile, path=Path('/modules') / hostile)
        client = FeignClient(hostile, hostile, 'https://example/' + hostile,
                             'src/main/java/' + hostile + '.java', 9)
        report = render_report(module, [client])
        self.assertNotIn('<script>', report)
        self.assertNotIn(hostile, report)
        self.assertIn('&#60;script&#62;', report)
        self.assertIn('&#10;', report)
        self.assertEqual(report.count('```'), 2)
        diagram = report.split('```mermaid\n')[1].split('```')[0]
        self.assertIn('#34;', diagram)
        self.assertIn('#10;', diagram)
        self.assertIn('#96;', diagram)
        self.assertEqual(diagram.count('System_Ext('), 1)
        self.assertEqual(len(diagram.splitlines()), 6)


if __name__ == '__main__':
    unittest.main()
