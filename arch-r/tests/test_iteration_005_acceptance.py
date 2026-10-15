"""Executable-level report contract for iteration 005.

Use one mixed module so ordering, cross-links, caller states and coverage
cannot pass by comparing empty sections or isolated rendering helpers.
"""
import html
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ENTRY_POINT = Path(__file__).resolve().parents[1] / 'arch-r'


class Iteration005AcceptanceTests(unittest.TestCase):
    headings = ['Summary', 'Architectural Connections', 'Findings',
                'Adapter Review Guidance', 'Findings with Evidence', 'Limitations']

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='archr_005_')
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.module = self.work / 'source module'
        java = self.module / 'src/main/java/shop'
        java.mkdir(parents=True)
        (self.module / 'pom.xml').write_text(
            '<project><artifactId>orders</artifactId></project>', encoding='utf-8')
        (java / 'Example.java').write_text('''package shop;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.reactive.function.client.WebClient;
@FeignClient(name="products", url="${products.url}")
interface Products { @GetMapping("/items") String get(); }
@FeignClient("uncertain")
interface Uncertain { String get(String id); String get(Long id); }
@FeignClient("unused") interface Unused {}
interface Orders extends JpaRepository<Order, Long> {
 @Query("select o from Order o") Order lookup();
}
class Service {
 Products products; Uncertain uncertain; Orders orders;
 JdbcTemplate jdbc; RestTemplate first; RestTemplate second; WebClient web;
 void place(Request request) {
  products.get();
  uncertain.get(null);
  orders.lookup();
  orders.save(null);
  orders.save(null);
  jdbc.update("DELETE FROM orders");
  first.getForObject("https://shipping.example/items", String.class);
  request.coverageOnlyGap();
 }
}
class Controller { Service service; void place() { service.place(null); } }
''', encoding='utf-8')
        self.output = self.work / 'arch-r-report-orders.md'

    def snapshot(self):
        return {str(path.relative_to(self.module)): path.read_bytes()
                for path in self.module.rglob('*') if path.is_file()}

    def report(self, *, details=False, flag_first=False, seed='1'):
        arguments = [str(ENTRY_POINT), 'analyze', str(self.module)]
        if details:
            arguments.insert(2 if flag_first else len(arguments),
                             '--show-analysis-limitations')
        result = subprocess.run(arguments, cwd=self.work, capture_output=True,
                                text=True, timeout=30,
                                env={**os.environ, 'PYTHONHASHSEED': seed})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        return self.output.read_text(encoding='utf-8')

    def sections(self, report):
        self.assertEqual(re.findall(r'^## (.+)$', report, re.M), self.headings)
        return {heading: report.split(f'## {heading}\n', 1)[1].split('\n## ', 1)[0]
                for heading in self.headings}

    def finding_sections(self, section):
        return dict(re.findall(
            r'^### Finding \d+: ([^\n]+)\n(.*?)(?=^### Finding |\Z)',
            section, re.M | re.S))

    def test_uniform_cards_and_links_resolve_to_matching_guidance_and_evidence(self):
        report = self.report()
        sections = self.sections(report)
        cards, guidance, evidence = [self.finding_sections(sections[heading])
                                     for heading in self.headings[2:5]]
        self.assertEqual(len(cards), 8)
        self.assertEqual(list(cards), list(guidance))
        self.assertEqual(list(cards), list(evidence))
        self.assertIn('Found 8 integration declarations: 6 HTTP and 2 database.',
                      sections['Summary'])
        self.assertEqual(report.count('```mermaid'), 1)
        self.assertIn('```mermaid', sections['Architectural Connections'])
        for title, card in cards.items():
            with self.subTest(integration=title):
                self.assertEqual(re.findall(r'\*\*([^*]+):\*\*', card), [
                    'Destination', 'Status', 'External system', 'Mechanism',
                    'Adapter Recommendation'])
                for kind, target in [('guidance', guidance), ('evidence', evidence)]:
                    links = re.findall(r'\]\(#(finding-\d+-' + kind + r')\)', card)
                    self.assertEqual(len(links), 1)
                    anchor = f'<a id="{links[0]}"></a>'
                    self.assertEqual(report.count(anchor), 1)
                    # Anchors precede their heading; verify the heading too,
                    # rather than merely checking that some target exists.
                    following = report.split(anchor, 1)[1].lstrip()
                    self.assertRegex(following, r'^### Finding \d+: ' + re.escape(title) + r'\n')
                    self.assertIn(title, target)
                self.assertNotRegex(card, r'src/main/java|→|Confidence|GET /items|```java')
        self.assertIn('**Status:** Caller found', cards['Products'])
        self.assertIn('${products.url} (destination unresolved)', cards['Products'])
        self.assertIn('**External system:** products', cards['Products'])
        self.assertIn('Inspect shop.Service.place to determine whether', cards['Products'])
        self.assertIn('**Status:** Caller unresolved', cards['Uncertain'])
        self.assertIn('**Status:** No caller found', cards['Unused'])
        self.assertIn('No recommendation: no supported caller was found', cards['Unused'])
        self.assertIn('**Destination:** Unknown', cards['shop.Orders'])
        self.assertIn('**External system:** Unknown', cards['shop.Orders'])
        self.assertIn('shop.Service.first', cards)
        self.assertIn('shop.Service.second', cards)

    def test_conditional_guidance_and_scoped_selective_grouped_evidence(self):
        sections = self.sections(html.unescape(self.report()))
        guidance = self.finding_sections(sections['Adapter Review Guidance'])
        evidence = self.finding_sections(sections['Findings with Evidence'])
        for title, text in guidance.items():
            with self.subTest(integration=title):
                self.assertNotRegex(text, r'domain-facing interface|wrapper|refactor')
                if title in ('Uncertain', 'Unused', 'shop.Service.second', 'shop.Service.web'):
                    self.assertIn('ArchR cannot identify code to review', text)
                    self.assertNotIn('```java', text)
                else:
                    self.assertEqual(text.count('```java'), 3)
                    self.assertEqual(text.count('if your code looks like this'), 3)
                    self.assertEqual(text.count('ArchR did not establish this behavior'), 3)
                    self.assertIn('shop.Service.place', text)
        self.assertIn('external fields, statuses, or representations', guidance['Products'])
        self.assertIn('HTTP status codes', guidance['Products'])
        for title in ('shop.Orders', 'shop.Service.jdbc'):
            self.assertIn('SQL errors', guidance[title])
            self.assertNotRegex(guidance[title], r'HTTP|httpStatus|client response')
        for title, text in evidence.items():
            with self.subTest(integration=title):
                self.assertEqual(re.findall(r'^#### (.+)$', text, re.M),
                                 ['Declaration', 'Operations', 'Observed Call Chains'])
                declaration, rest = text.split('#### Declaration', 1)[1].split('#### Operations', 1)
                self.assertEqual(len(re.findall(r'Example.java:\d+', declaration)), 1)
                operations, chains = rest.split('#### Observed Call Chains', 1)
                for row in operations.splitlines():
                    if row.startswith('- '):
                        # Query previews share their operation/metadata citation,
                        # rather than repeating that location on a second row.
                        preview = row.startswith(('- **JPQL:**', '- **SQL:**'))
                        self.assertEqual(len(re.findall(r'Example.java:\d+', row)),
                                         0 if preview else 1)
                self.assertNotRegex(chains, r'Invocation in|receiver .* declared|method name at')
                if title in ('Unused', 'shop.Service.second', 'shop.Service.web'):
                    self.assertIn('No supported operations observed', operations)
                    self.assertIn('No supported call chains observed', chains)
        repository = evidence['shop.Orders']
        self.assertIn('JPQL:** select o from Order o', repository)
        chains = repository.split('#### Observed Call Chains', 1)[1]
        self.assertEqual(chains.count('shop.Controller.place → shop.Service.place'), 1)
        self.assertEqual(chains.count('→ shop.Orders.save'), 1)
        self.assertIn('→ shop.Orders.lookup', chains)
        self.assertIn('Unresolved connection', evidence['Uncertain'])
        self.assertNotIn('Unresolved connection', evidence['Unused'])

    def test_limitations_once_and_cli_modes_append_only_with_stable_bytes(self):
        before = self.snapshot()
        default = self.report()
        limitations = self.sections(default)['Limitations']
        for status in ('Caller found', 'No caller found', 'Caller unresolved'):
            self.assertEqual(limitations.count(f'**{status}**'), 1)
        self.assertEqual(default.count('did not compile, run, or modify'), 1)
        self.assertEqual(default.count('limit is 2 call steps'), 1)
        self.assertLess(len(limitations.split()), 320)
        self.assertNotIn('${products.url}', limitations)
        self.assertNotIn('coverageOnlyGap', default)
        outputs = []
        for flag_first, seed in ((False, '17'), (True, '93')):
            detailed = self.report(details=True, flag_first=flag_first, seed=seed)
            prefix, details = detailed.split('\n### Untraced call sites\n', 1)
            self.assertEqual(prefix.rstrip(), default.rstrip())
            self.assertIn('coverageOnlyGap', details)
            self.assertNotIn('\n## ', details)
            outputs.append(self.output.read_bytes())
        self.assertEqual(*outputs)
        self.assertEqual(default, self.report(seed='93'))
        self.assertEqual(before, self.snapshot())
        self.assertEqual(set(self.work.iterdir()), {self.module, self.output})


if __name__ == '__main__':
    unittest.main()
