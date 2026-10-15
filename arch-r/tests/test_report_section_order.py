"""Iteration 005 layout, independently of the later content changes."""
from pathlib import Path
import re
import tempfile
import unittest

from archr.discovery import extract_clients
from archr.findings import IntegrationFinding
from archr.integrations import extract_declarations
from archr.module import Module, load_module
from archr.report import render_report
from archr.traversal import trace_usage


class ReportSectionOrderTests(unittest.TestCase):
    headings = [
        'Summary', 'Architectural Connections', 'Findings',
        'Adapter Review Guidance', 'Findings with Evidence', 'Limitations',
    ]

    def sections(self, report):
        self.assertEqual(re.findall(r'^## (.+)$', report, re.M), self.headings)
        return {title: report.split(f'## {title}\n', 1)[1].split('\n## ', 1)[0]
                for title in self.headings}

    def test_mixed_findings_have_same_order_in_all_three_sections(self):
        module = Module(Path('/module'), Path('/module/src/main/java'), 'module')
        clients = extract_clients('''
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
@FeignClient("products") interface ProductClient {
    @GetMapping("/product") String get();
}
@FeignClient("billing") interface BillingClient {}
''', 'src/main/java/Clients.java')
        declarations = extract_declarations('''
class Gateway { org.springframework.jdbc.core.JdbcTemplate jdbc; }
interface Orders extends org.springframework.data.jpa.repository.JpaRepository<Order, Long> {}
''', 'src/main/java/Gateway.java')
        findings = [IntegrationFinding(item) for item in declarations]
        self.assertEqual(len(findings), 2)
        report = render_report(module, clients, findings=findings)
        sections = self.sections(report)
        titles = [re.findall(r'^### Finding .+$', sections[title], re.M)
                  for title in self.headings[2:5]]
        self.assertEqual(len(titles[0]), 4)
        self.assertEqual(titles[0], titles[1])
        self.assertEqual(titles[0], titles[2])
        self.assertIn('Found 4 integration declarations: 2 HTTP and 2 database.',
                      sections['Summary'])
        self.assertIn('Review conditions', sections['Adapter Review Guidance'])
        self.assertNotIn('Review conditions', sections['Findings with Evidence'])
        self.assertNotIn('Operations and query evidence', sections['Findings'])
        self.assertIn('GET /product', sections['Findings with Evidence'])
        self.assertEqual(report.count('```mermaid'), 1)
        self.assertIn('```mermaid', sections['Architectural Connections'])
        self.assertEqual(report, render_report(module, reversed(clients),
                                               findings=reversed(findings)))

    def test_empty_report_still_has_all_sections(self):
        module = Module(Path('/module'), Path('/module/src/main/java'), 'module')
        sections = self.sections(render_report(module, []))
        for title in self.headings[2:5]:
            self.assertEqual(sections[title].strip(), '')

    def test_coverage_modes_leave_all_preceding_sections_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            java = root / 'src/main/java/Example.java'
            java.parent.mkdir(parents=True)
            java.write_text('''
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
@FeignClient("products") interface Client { @GetMapping String get(); }
class Service {
    Client client;
    String run(Request request) { request.unknown(); return client.get(); }
}
''')
            module = load_module(str(root))
            clients = extract_clients(java.read_text(), 'src/main/java/Example.java')
            usage = trace_usage(module)
            default = render_report(module, clients, usage)
            detailed = render_report(module, clients, usage, show_analysis_limitations=True)
            sections = self.sections(default)
            self.sections(detailed)
            self.assertEqual(default.split('## Limitations\n')[0],
                             detailed.split('## Limitations\n')[0])
            self.assertIn('1 call site was not traced', sections['Limitations'])
            self.assertNotIn('### Untraced call sites', default)
            self.assertIn('### Untraced call sites', detailed.split('## Limitations\n')[1])
            self.assertIn('Service.run → Client.get', sections['Findings with Evidence'])
            self.assertNotIn('Source calls show possible behavior', sections['Findings with Evidence'])
            self.assertIn('**Interpreting a client response**', sections['Adapter Review Guidance'])
            self.assertNotIn('**Interpreting a client response**', sections['Findings'])
            self.assertEqual(java.read_text().count('request.unknown()'), 1)


if __name__ == '__main__':
    unittest.main()
