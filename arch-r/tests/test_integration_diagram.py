"""Diagram contracts for the iteration 004 integration declarations."""
import unittest

from archr.discovery import discover_clients
from archr.findings import discover_findings
from archr.module import load_module
from archr.report import render_report
from tests.test_outbound_report import OutboundReportTests
from tests.test_usage_diagram import Diagram


class IntegrationDiagramTests(unittest.TestCase):
    setUp = OutboundReportTests.setUp
    put = OutboundReportTests.put
    report = OutboundReportTests.report

    def diagram(self):
        return Diagram(self, self.report())

    def test_shared_repository_and_distinct_field_endpoints(self):
        self.put('''package shop;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.reactive.function.client.WebClient;
interface Orders extends JpaRepository<Order, Long> {}
class Gateway {
 Orders first; Orders second; JdbcTemplate jdbc;
 RestTemplate rest; RestTemplate other; WebClient web;
 void store() { first.save(null); second.findAll(); jdbc.update("secret SQL"); }
 void request() { rest.getForObject("/items", String.class); }
 void reactive() { web.get().uri("/items").retrieve().bodyToMono(String.class); }
 void unrelated() {}
}
class Service { Gateway gateway; void place() { gateway.store(); } }
class Unrelated { Gateway gateway; void check() { gateway.unrelated(); } }
''')
        diagram = self.diagram()
        gateway, = [node for node, (_, label) in diagram.nodes.items()
                    if label == 'shop.Gateway']
        repository = diagram.named(self, 'shop.Orders')
        for name in ('shop.Orders', 'shop.Gateway.jdbc', 'shop.Gateway.rest',
                     'shop.Gateway.web'):
            labels = diagram.labels(gateway, diagram.named(self, name))
            self.assertEqual(len(labels), 1)
            self.assertIn('Observed source call', labels[0])
        self.assertEqual(len(diagram.labels(gateway, repository)), 1)
        other = diagram.named(self, 'shop.Gateway.other')
        self.assertFalse(diagram.labels(gateway, other))
        self.assertTrue(diagram.paths(diagram.named(self, 'shop.Service'), repository))
        self.assertNotIn('Unrelated', diagram.text)
        for detail in ('save', 'findAll', 'update', 'getForObject', 'retrieve',
                       'bodyToMono', 'secret SQL', '/items', 'adapter'):
            self.assertNotIn(detail, diagram.text)
        self.assertEqual(diagram.text, self.diagram().text)

    def test_literal_destination_is_not_labeled_unknown(self):
        self.put('''package shop;
import org.springframework.web.client.RestTemplate;
class Gateway {
 RestTemplate rest;
 void request() { rest.getForObject("https://products.example/items", String.class); }
}
''')
        diagram = self.diagram()
        destination = diagram.named(self, 'https://products.example/items')
        endpoint = diagram.named(self, 'shop.Gateway.rest')
        labels = diagram.labels(endpoint, destination)
        self.assertEqual(len(labels), 1)
        self.assertIn('not runtime traffic', labels[0])
        self.assertNotIn('Destination unknown', diagram.text)

    def test_declarations_without_usage_and_shared_unknown_destinations(self):
        self.put('''package shop;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.web.client.RestTemplate;
interface Orders extends JpaRepository<Order, Long> {}
interface Customers extends JpaRepository<Customer, Long> {}
class Gateway { RestTemplate one; RestTemplate two; }
''')
        module = load_module(self.root)
        report = render_report(module, discover_clients(module),
                               findings=discover_findings(module))
        diagram = Diagram(self, report)
        external = [node for node, (kind, _) in diagram.nodes.items()
                    if kind.endswith('_Ext')]
        self.assertEqual(len(external), 2)
        for node in external:
            self.assertIn('Destination unknown', diagram.nodes[node][1])
            self.assertFalse(diagram.boundaries[node])
        self.assertIn('not a count of distinct systems', diagram.text)
        for name in ('shop.Orders', 'shop.Customers', 'shop.Gateway.one', 'shop.Gateway.two'):
            node = diagram.named(self, name)
            self.assertTrue(diagram.boundaries[node])
            outgoing = [label for source, _, label in diagram.edges if source == node]
            self.assertEqual(len(outgoing), 1)
            self.assertIn('not runtime traffic', outgoing[0])
        self.assertNotIn('Observed', diagram.text)


if __name__ == '__main__':
    unittest.main()
