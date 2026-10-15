"""Executable-level iteration 004 contracts across discovery, tracing and reports."""
import html
from pathlib import Path
import subprocess
import tempfile
import unittest


ENTRY_POINT = Path(__file__).resolve().parents[1] / 'arch-r'


class Iteration004AcceptanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='archr_004_')
        self.addCleanup(temporary.cleanup)
        self.caller = Path(temporary.name)
        self.module = self.caller / 'orders'
        self.java = self.module / 'src/main/java'
        self.java.mkdir(parents=True)
        (self.module / 'pom.xml').write_text(
            '<project><artifactId>orders</artifactId></project>', encoding='utf-8')
        self.output = self.caller / 'arch-r-report-orders.md'

    def source(self, name, content):
        path = self.java / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def run_cli(self, detailed=False, flag_first=False):
        arguments = [str(ENTRY_POINT), 'analyze', str(self.module)]
        if detailed:
            arguments.insert(2 if flag_first else len(arguments),
                             '--show-analysis-limitations')
        result = subprocess.run(arguments, cwd=self.caller, capture_output=True,
                                text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        return html.unescape(self.output.read_text(encoding='utf-8'))

    def findings(self, report):
        return [part.split('\n## ', 1)[0]
                for part in report.split('\n## Finding ')[1:]]

    def test_declarations_only_exclusions_counts_and_empty_scope(self):
        self.source('Declarations.java', '''
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.reactive.function.client.WebClient;
interface Orders extends JpaRepository<Order, Long> {}
interface Customers extends JpaRepository<Customer, Long> {}
interface Indirect extends Orders {}
class Gateway {
 final JdbcTemplate jdbc;
 final RestTemplate first;
 final RestTemplate second;
 final WebClient web;
 Gateway(JdbcTemplate jdbc, RestTemplate first, RestTemplate second, WebClient web) {
  this.jdbc = jdbc; this.first = first; this.second = second; this.web = web;
 }
}
''')
        # These files must neither create declarations nor add callers.
        self.source('Parameters.java', '''
import org.springframework.web.client.RestTemplate;
class Parameters {
 Parameters(RestTemplate client) {}
 void run(RestTemplate client) { RestTemplate local = client; }
 @Bean RestTemplate client() { return null; }
}
''')
        self.source('local/Lookalikes.java', '''package local;
class JdbcTemplate {} class RestTemplate {} class WebClient {}
interface JpaRepository<T, ID> {}
interface FakeRepo extends JpaRepository<Object, Long> {}
class Lookalikes { JdbcTemplate jdbc; RestTemplate rest; WebClient web; }
''')
        report = self.run_cli()
        self.assertIn('Found 6 integration declarations: 3 HTTP and 3 database.', report)
        findings = self.findings(report)
        self.assertEqual(len(findings), 6)
        for finding in findings:
            self.assertIn('Declared integration — No supported caller found', finding)
            self.assertIn('Destination unknown', finding)
            self.assertIn('Declaration evidence:', finding)
            self.assertIn('No specific adapter placement recommendation', finding)
        (self.java / 'Declarations.java').unlink()
        empty = self.run_cli()
        self.assertEqual(self.findings(empty), [])
        self.assertIn('No recognized integration declarations were found within supported scope', empty)
        self.assertIn('External dependencies outside supported scope may still exist', empty)

    def test_shared_repository_and_feign_chains_remain_independent(self):
        self.source('data/Orders.java', '''package data;
import org.springframework.data.jpa.repository.JpaRepository;
interface Orders extends JpaRepository<Order, Long> { Order findByCode(String code); }
''')
        self.source('shop/Usage.java', '''package shop;
import data.Orders;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
@FeignClient(name="products", url="https://products.example")
interface Products { @GetMapping("/items") String items(); }
class Writer { Orders writes; void store() { this.writes.save(null); } }
class Reader { Orders reads; void load() { reads.findByCode("code"); } }
class Browser { Products products; void browse() { products.items(); } }
class Service {
 Writer writer; Reader reader; Browser browser;
 void place() { writer.store(); }
 void list() { reader.load(); }
 void browse() { browser.browse(); }
}
''')
        report = self.run_cli()
        self.assertIn('Found 2 integration declarations: 1 HTTP and 1 database.', report)
        repository, = [f for f in self.findings(report) if 'Spring Data JPA' in f]
        self.assertIn('shop.Service → shop.Writer → data.Orders', repository)
        self.assertIn('shop.Service → shop.Reader → data.Orders', repository)
        self.assertIn('receiver writes declared as data.Orders', repository)
        self.assertIn('receiver reads declared as data.Orders', repository)
        self.assertIn('candidate adapter location', repository)
        self.assertIn('Destination unknown', repository)
        self.assertNotIn('SQL:**', repository)
        self.assertNotIn('shop.Browser', repository)
        self.assertIn('GET /items', report)
        self.assertEqual(report.count('```mermaid'), 1)

    def test_rest_verbs_and_independent_destination_uncertainty(self):
        # Keep this oracle independent of the analyzer's operation registry.
        cases = [
            ('getForObject("/get-object", String.class)', 'GET', '/get-object'),
            ('getForEntity("/get-entity", String.class)', 'GET', '/get-entity'),
            ('postForObject("/post-object", null, String.class)', 'POST', '/post-object'),
            ('postForEntity("/post-entity", null, String.class)', 'POST', '/post-entity'),
            ('put("/put", null)', 'PUT', '/put'),
            ('patchForObject("/patch", null, String.class)', 'PATCH', '/patch'),
            ('delete("/delete")', 'DELETE', '/delete'),
            ('headForHeaders("/head")', 'HEAD', '/head'),
            ('optionsForAllow("/options")', 'OPTIONS', '/options'),
            ('exchange("/exchange", HttpMethod.PATCH, null, String.class)', 'PATCH', '/exchange'),
        ]
        self.source('Gateway.java', '''
import org.springframework.web.client.RestTemplate;
import org.springframework.http.HttpMethod;
class Gateway { RestTemplate rest; RestTemplate unknown;
 void request(String url) {
''' + '\n'.join('rest.' + call + ';' for call, _, _ in cases) + '''
 rest.getForObject(url, String.class);
 rest.postForObject("${base}/items", null, String.class);
 rest.exchange("/unknown-verb", verb, null, String.class);
 unknown.toString(); unknown.unsupported();
 }
}
''')
        report = self.run_cli()
        rest, unknown = self.findings(report)
        for _, verb, path in cases:
            with self.subTest(path=path):
                self.assertIn(f'HTTP method: {verb}; Path: {path} — Host unknown', rest)
        self.assertIn('HTTP method: GET; Destination unresolved: nonliteral expression', rest)
        self.assertIn('${base}/items', rest)
        self.assertIn('HTTP method: unresolved; Path: /unknown-verb — Host unknown', rest)
        self.assertIn('No supported caller found', unknown)
        self.assertNotIn('Supported source operation caller found', unknown)
        self.assertNotIn('**Suggestion:**', unknown)

    def test_query_language_and_unicode_bounds_reach_both_cli_modes(self):
        exact = '😀' * 100
        truncated = '界' * 101 + 'PRIVATE_QUERY_TAIL'
        self.source('Queries.java', '''
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.jdbc.core.JdbcTemplate;
interface Orders extends JpaRepository<Order, Long> {
 @Query("''' + exact + '''") Order exact();
 @Query(value="''' + truncated + '''", nativeQuery=true) Order nativeQuery();
 @Query(value="select x from Order x", nativeQuery=false) Order jpql();
 @Query(value="select 1", nativeQuery=Settings.NATIVE) Order unknownLanguage();
 @Query("select " + SQL) Order unresolved();
 @Query(name="PRIVATE_NAMED_QUERY") Order named();
}
class Gateway { JdbcTemplate jdbc;
 void run() {
  jdbc.query("""
    select   x
    from   items
    """, mapper);
  jdbc.update("''' + truncated + '''");
  jdbc.query(SQL, mapper);
 }
}
''')
        for detailed in (False, True):
            with self.subTest(detailed=detailed):
                report = self.run_cli(detailed)
                self.assertIn('JPQL:** ' + exact, report)
                self.assertEqual(report.count('SQL:** ' + '界' * 99 + '…'), 2)
                self.assertNotIn('界' * 100, report)
                self.assertNotIn('PRIVATE_QUERY_TAIL', report)
                self.assertNotIn('PRIVATE_NAMED_QUERY', report)
                self.assertIn('SQL:** select x from items', report)
                self.assertIn('JPQL:** select x from Order x', report)
                self.assertIn('Query (language unresolved):** select 1', report)
                self.assertIn('Unresolved query expression (not evaluated)', report)
                self.assertIn('src/main/java/Queries.java:', report)
                self.assertEqual(report.count('JPQL queries Java persistence entities'), 1)
                repository, = [f for f in self.findings(report) if 'Spring Data JPA' in f]
                self.assertIn('No supported caller found', repository)

    def test_webclient_requests_builders_and_split_chains_have_bounded_coverage(self):
        self.source('Gateway.java', '''
import org.springframework.web.reactive.function.client.WebClient;
class Gateway { WebClient request; WebClient builder; WebClient split;
 void run() {
  request.get().uri("/items").retrieve().bodyToMono(String.class);
  builder.post().uri("/build-only");
  var local = split.get().uri("/split");
  local.retrieve().bodyToMono(String.class);
 }
}
class Service { Gateway gateway; void act() { gateway.run(); } }
''')
        brief = self.run_cli()
        findings = self.findings(brief)
        request, = [f for f in findings if f.split('\n', 1)[0].endswith('Gateway.request')]
        builder, = [f for f in findings if f.split('\n', 1)[0].endswith('Gateway.builder')]
        split, = [f for f in findings if f.split('\n', 1)[0].endswith('Gateway.split')]
        self.assertIn('Supported source operation caller found', request)
        self.assertIn('Service → Gateway', request)
        self.assertIn('HTTP method: GET; Path: /items — Host unknown', request)
        for finding in (builder, split):
            self.assertIn('No supported caller found', finding)
            self.assertIn('Request-builder configuration only', finding)
            self.assertNotIn('**Suggestion:**', finding)
        detailed = self.run_cli(True)
        # Fluent segments rooted in recognized fields add no gaps. Only the
        # two segments on the split local remain outside supported scope.
        self.assertIn('2 call sites were not traced', brief)
        self.assertIn('2 call sites were not traced', detailed)
        self.assertEqual(detailed, self.run_cli(True, flag_first=True))


if __name__ == '__main__':
    unittest.main()
