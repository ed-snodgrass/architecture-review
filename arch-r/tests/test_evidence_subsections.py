"""Iteration 005: fixed evidence structure and selective operation citations."""
import html
import re
import tempfile
from pathlib import Path
import unittest

from archr.discovery import discover_clients
from archr.findings import discover_findings
from archr.module import load_module
from archr.report import render_report
from archr.traversal import trace_usage


class EvidenceSubsectionTests(unittest.TestCase):
    def report(self, source, *, traversal=True):
        with tempfile.TemporaryDirectory() as directory:
            java = Path(directory) / 'src/main/java'
            java.mkdir(parents=True)
            (java / 'Example.java').write_text(source)
            module = load_module(directory)
            return render_report(module, discover_clients(module),
                                 trace_usage(module) if traversal else None,
                                 findings=discover_findings(module))

    def sections(self, report):
        evidence = report.split('## Findings with Evidence\n', 1)[1].split('## Limitations', 1)[0]
        sections = re.split(r'<a id="finding-\d+-evidence"></a>', evidence)[1:]
        for section in sections:
            self.assertEqual(re.findall(r'^#### (.+)$', section, re.M),
                             ['Declaration', 'Operations', 'Observed Call Chains'])
            declaration, rest = section.split('#### Declaration', 1)[1].split('#### Operations', 1)
            self.assertEqual(len(re.findall(r'src/main/java/Example.java:\d+', declaration)), 1)
        return sections

    def test_empty_evidence_for_all_mechanisms_with_and_without_traversal(self):
        source = '''import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.reactive.function.client.WebClient;
@FeignClient(name="products") interface Products {}
interface Orders extends JpaRepository<Order, Long> {}
class Gateway { JdbcTemplate jdbc; RestTemplate rest; WebClient web; }
'''
        for traversal in (False, True):
            sections = self.sections(self.report(source, traversal=traversal))
            self.assertEqual(len(sections), 5)
            for section in sections:
                self.assertIn('No supported operations observed', section)
                self.assertIn('No supported call chains observed', section)

    def test_feign_operations_cite_their_method_mapping_not_shared_prefix(self):
        source = '''import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
@FeignClient(name="products")
@RequestMapping("/api")
interface Products {
 @GetMapping("/items") String items();
 @GetMapping("/orders") String orders();
}
'''
        for traversal in (False, True):
            with self.subTest(traversal=traversal):
                section, = self.sections(self.report(source, traversal=traversal))
                operations = section.split('#### Operations', 1)[1].split(
                    '#### Observed Call Chains', 1)[0]
                rows = [line for line in operations.splitlines() if line.startswith('- ')]
                self.assertEqual(len(rows), 2)
                for row, path, line in zip(rows, ('/api/items', '/api/orders'), (7, 8)):
                    self.assertIn('GET ' + path, row)
                    self.assertEqual(re.findall(r'src/main/java/Example.java:\d+', row),
                                     [f'src/main/java/Example.java:{line}'])

    def test_operation_citations_are_selective_and_facts_remain(self):
        source = '''import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.client.RestTemplate;
@FeignClient(name="products") interface Products {
 @GetMapping("/items") String items();
}
interface Orders extends JpaRepository<Order, Long> {
 @Query("select o from Order o") Order lookup();
}
class Gateway {
 JdbcTemplate jdbc; RestTemplate rest;
 void call(String url) {
  jdbc.query("select * from orders", mapper);
  rest.getForObject("/items", String.class);
  rest.postForObject(url, null, String.class);
 }
}
'''
        sections = self.sections(self.report(source))
        operations = [s.split('#### Operations', 1)[1].split('#### Observed Call Chains', 1)[0]
                      for s in sections]
        self.assertEqual([len(re.findall(r'Example.java:\d+', s)) for s in operations],
                         [1, 1, 1, 2])
        combined = html.unescape('\n'.join(operations))
        for fact in ('GET /items', 'JPQL:** select o from Order o',
                     'SQL:** select * from orders', 'Path: /items — Host unknown',
                     'Destination unresolved: nonliteral expression'):
            self.assertIn(fact, combined)
        self.assertNotIn('Destination evidence:', combined)


if __name__ == '__main__':
    unittest.main()
