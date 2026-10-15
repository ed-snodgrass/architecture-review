"""Iteration 004 report content, independently of the diagram update."""

import html
from pathlib import Path
import tempfile
import unittest

from archr.cli import main
from archr.discovery import discover_clients
from archr.findings import discover_findings
from archr.module import load_module
from archr.report import render_report
from archr.traversal import trace_usage


class OutboundReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'orders'
        self.java = self.root / 'src/main/java/shop'
        self.java.mkdir(parents=True)
        (self.root / 'pom.xml').write_text('<project><artifactId>orders</artifactId></project>')

    def put(self, source):
        (self.java / 'Example.java').write_text(source, encoding='utf-8')

    def report(self, detailed=False):
        module = load_module(self.root)
        return render_report(module, discover_clients(module), trace_usage(module),
                             findings=discover_findings(module),
                             show_analysis_limitations=detailed)

    def finding(self, report, number):
        from tests.report_sections import findings
        return findings(report)[number - 1]

    def test_declaration_counts_and_no_caller_guidance(self):
        self.put('''package shop;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.reactive.function.client.WebClient;
interface Orders extends JpaRepository<Order, Long> {}
class Gateway { JdbcTemplate jdbc; RestTemplate rest; WebClient web; }
''')
        report = self.report()
        self.assertTrue(report.startswith('# Outbound dependencies: orders\n'))
        self.assertIn('Found 4 integration declarations: 2 HTTP and 2 database.', report)
        self.assertIn('do not establish distinct external systems', report)
        self.assertEqual(report.split('## Findings\n', 1)[1].split('\n## ', 1)[0].count('### Finding '), 4)
        for number in range(1, 5):
            finding = self.finding(report, number)
            self.assertIn('**Status:** No caller found', finding)
            self.assertIn('**Destination:** Unknown', finding)
            self.assertIn('Declaration evidence:', finding)
            self.assertIn('src/main/java/shop/Example.java:', finding)
            self.assertIn('No recommendation: no supported caller was found', finding)
            self.assertNotIn('**Suggestion:**', finding)
        self.assertIn('does not establish direct JDBC calls', report)
        self.assertEqual(report, self.report())

    def test_repository_chain_queries_and_conditional_advice(self):
        self.put('''package shop;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
interface Orders extends JpaRepository<Order, Long> {
 @Query("select o from Order o") Order lookup();
}
class Gateway { Orders orders; void store() { orders.save(null); } }
class Service { Gateway gateway; void place() { gateway.store(); } }
''')
        report = self.report()
        finding = html.unescape(self.finding(report, 1))
        self.assertIn('**Status:** Caller found', finding)
        self.assertIn('shop.Service.place → shop.Gateway.store → shop.Orders.save', finding)
        self.assertIn('shop.Gateway.store', finding)
        self.assertIn('Check whether', finding)
        self.assertIn('persistence-library exceptions', finding)
        self.assertIn('JPQL:** select o from Order o', finding)
        self.assertEqual(report.count('JPQL queries Java persistence entities'), 1)
        self.assertIn('**Destination:** Unknown', finding)
        self.assertNotIn('HTTP status codes', finding)

    def test_http_operation_destinations_and_builder_only_status(self):
        self.put('''package shop;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.reactive.function.client.WebClient;
class Gateway {
 RestTemplate rest;
 WebClient web;
 void request(String url) {
  rest.getForObject("/items", String.class);
  rest.postForObject(url, null, String.class);
  web.get().uri("/built-only");
 }
}
''')
        report = self.report()
        rest = self.finding(report, 1)
        web = self.finding(report, 2)
        self.assertIn('HTTP method: GET; Path: /items — Host unknown', rest)
        self.assertIn('HTTP method: POST; Destination unresolved: nonliteral expression', rest)
        self.assertNotIn('None', rest)
        self.assertIn('→ org.springframework.web.client.RestTemplate.getForObject', rest)
        self.assertIn('src/main/java/shop/Example.java:8', rest)
        self.assertNotIn('domain-facing interface', rest)
        self.assertIn('**Status:** No caller found', web)
        self.assertIn('Request-builder configuration only', web)
        self.assertIn('no recommendation', web.lower())
        self.assertNotIn('**Suggestion:**', web)

    def test_query_preview_bounded_in_both_modes_without_caller(self):
        query = 'select ' + '界' * 110
        self.put('''package shop;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
interface Orders extends JpaRepository<Order, Long> {
 @Query(nativeQuery = true, value = "''' + query + '''") Order lookup();
}
''')
        for detailed in (False, True):
            report = self.report(detailed)
            self.assertIn('SQL:** ' + query[:99] + '…', report)
            self.assertNotIn(query[:100], report)
            self.assertIn('**Status:** No caller found', report)
            self.assertIn('Example.java:5', report)
            self.assertNotIn('JPQL queries', report)

    def test_empty_scope_does_not_claim_no_dependencies(self):
        self.put('package shop; class Empty {}')
        report = self.report()
        self.assertIn('No recognized integration declarations were found within supported scope', report)
        self.assertIn('External dependencies outside supported scope may still exist', report)
        self.assertNotIn('## Finding ', report)

    def test_mixed_mechanisms_keep_feign_and_field_identity(self):
        self.put('''package shop;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.client.RestTemplate;
@FeignClient(name = "products", url = "https://products.example")
interface Products { @GetMapping("/items") String items(); }
class Gateway {
 Products products; RestTemplate first; RestTemplate second;
 void call() { products.items(); first.getForObject("/first", String.class); second.unknown(); }
}
''')
        report = self.report()
        self.assertIn('Found 3 integration declarations: 3 HTTP and 0 database.', report)
        self.assertIn('GET /items', self.finding(report, 1))
        first = self.finding(report, 2)
        second = self.finding(report, 3)
        self.assertIn('shop.Gateway.first', first)
        self.assertIn('**Status:** Caller found', first)
        self.assertIn('shop.Gateway.second', second)
        self.assertIn('**Status:** Caller unresolved', second)
        self.assertIn('unsupported-operation', second)
        self.assertNotIn('unsupported-operation', first)
        self.assertNotIn('**Suggestion:**', second)

    def test_possible_database_chain_keeps_wiring_uncertainty(self):
        self.put('''package shop;
import org.springframework.jdbc.core.JdbcTemplate;
interface Port { void store(); }
class Gateway implements Port {
 JdbcTemplate jdbc;
 public void store() { jdbc.update("delete from orders"); }
}
class Service { Port port; void place() { port.store(); } }
''')
        finding = self.finding(self.report(), 1)
        self.assertIn('Possible chain', finding)
        self.assertIn('possible, not confirmed', finding)
        self.assertIn('verify that runtime wiring connects shop.Port to shop.Gateway', finding)
        self.assertIn('shop.Gateway.store', finding)
        self.assertNotIn('candidate adapter location', finding)
        self.assertIn('SQL:** delete from orders', finding)
        self.assertIn('**Destination:** Unknown', finding)

    def test_cli_supplies_expanded_findings(self):
        from unittest.mock import patch
        self.put('''package shop; class Gateway {
 org.springframework.jdbc.core.JdbcTemplate jdbc;
}''')
        with patch('archr.cli.write_report') as output:
            self.assertEqual(main(['analyze', str(self.root)]), 0)
        report = output.call_args.args[1]
        self.assertIn('Found 1 integration declarations: 0 HTTP and 1 database.', report)
        self.assertIn('shop.Gateway.jdbc', report)


if __name__ == '__main__':
    unittest.main()
