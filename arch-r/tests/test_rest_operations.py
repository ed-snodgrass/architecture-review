"""RestTemplate source operations keep independent verb/destination evidence."""
import tempfile
from pathlib import Path
import unittest

from archr.findings import discover_findings, DestinationCertainty
from archr.indexing import index_source
from archr.resolution import REST_OPERATIONS, resolve_index


class RestOperationTests(unittest.TestCase):
    def findings(self, body, imports='import org.springframework.http.HttpMethod;',
                 parameters='String url', fields=''):
        from archr.module import load_module
        with tempfile.TemporaryDirectory() as directory:
            sources = Path(directory) / 'src/main/java'
            sources.mkdir(parents=True)
            (sources / 'Gateway.java').write_text('''
import org.springframework.web.client.RestTemplate;
''' + imports + '''
class Gateway {
 final RestTemplate rest;
 RestTemplate other;
 ''' + fields + '''
 Gateway(RestTemplate rest) { this.rest = rest; }
 void run(''' + parameters + ''') { ''' + body + ''' }
 void unrelated() { rest.toString(); }
}
class Service { Gateway gateway; void act() { gateway.run(null); }
 void unrelated() { gateway.unrelated(); } }
''', encoding='utf-8')
            return discover_findings(load_module(directory))

    def test_operations_and_two_step_chains(self):
        rest, other = self.findings(''.join(
            f'this.rest.{name}("https://example.test/items", HttpMethod.GET);'
            for name in REST_OPERATIONS))
        self.assertEqual({op.method_name for op in rest.operations}, set(REST_OPERATIONS))
        for op in rest.operations:
            self.assertEqual(op.http_method, REST_OPERATIONS[op.method_name] or 'GET')
            self.assertEqual(op.destination.certainty, DestinationCertainty.LITERAL)
            self.assertEqual(op.destination.value, 'https://example.test/items')
            self.assertTrue(op.has_supported_caller)
            self.assertIsNone(op.query)
        self.assertTrue(all(len(c.steps) == 2 for c in rest.chains))
        self.assertFalse(other.has_supported_caller)
        self.assertEqual(rest.destination.label, 'Destination unknown')

    def test_independent_unknowns_paths_and_placeholders(self):
        rest, _ = self.findings('''rest.getForObject(url, String.class);
rest.getForEntity("/items", String.class);
rest.postForObject("${base}/items", null, String.class);
rest.exchange("https://example.test/{id}", HttpMethod.POST, null, String.class);
rest.exchange("/items", verb, null, String.class);
rest.exchange(url, HttpMethod.DELETE, null, String.class);
rest.put("https://example.test/" + url, null);''')
        ops = rest.operations
        self.assertEqual([op.http_method for op in ops],
                         ['GET', 'GET', 'POST', 'POST', None, 'DELETE', 'PUT'])
        self.assertEqual([op.destination.certainty for op in ops],
                         [DestinationCertainty.UNRESOLVED, DestinationCertainty.PATH,
                          DestinationCertainty.UNRESOLVED, DestinationCertainty.UNRESOLVED,
                          DestinationCertainty.PATH, DestinationCertainty.UNRESOLVED,
                          DestinationCertainty.UNRESOLVED])
        self.assertEqual(ops[2].destination.value, '${base}/items')
        self.assertTrue(all(op.has_supported_caller for op in ops))

    def test_http_method_requires_exact_spring_type(self):
        for imports in ('', 'import other.HttpMethod;',
                        'import org.springframework.http.*;',
                        'import org.springframework.http.HttpMethod; class HttpMethod {}'):
            rest, _ = self.findings('rest.exchange("/x", HttpMethod.GET, null);', imports)
            self.assertIsNone(rest.operations[0].http_method)
        rest, _ = self.findings(
            'rest.exchange("/x", org.springframework.http.HttpMethod.PATCH, null);', '')
        self.assertEqual(rest.operations[0].http_method, 'PATCH')

    def test_exchange_value_name_shadowing_keeps_other_evidence(self):
        for options, prefix in (
                ({'parameters': 'Holder HttpMethod'}, ''),
                ({}, 'Holder HttpMethod = null;'),
                ({'fields': 'Holder HttpMethod;'}, '')):
            with self.subTest(options=options):
                rest, _ = self.findings(
                    prefix + 'rest.exchange("/items", HttpMethod.GET, null, String.class);',
                    imports='import org.springframework.http.HttpMethod; '
                            'class Holder { HttpMethod GET; }', **options)
                op, = rest.operations
                self.assertEqual(op.method_name, 'exchange')
                self.assertIsNone(op.http_method)
                self.assertEqual(op.destination.value, '/items')
                self.assertEqual(op.destination.certainty, DestinationCertainty.PATH)
                self.assertTrue(op.has_supported_caller)
                self.assertEqual(len(rest.chains[0].steps), 2)
                self.assertTrue(op.evidence)

    def test_fully_qualified_exchange_value_shadowing_keeps_other_evidence(self):
        for options, prefix in (
                ({'parameters': 'Holder org'}, ''),
                ({}, 'Holder org = null;'),
                ({'fields': 'Holder org;'}, '')):
            with self.subTest(options=options):
                rest, _ = self.findings(
                    prefix + 'rest.exchange("/items", '
                    'org.springframework.http.HttpMethod.GET, null, String.class);',
                    imports='''import org.springframework.http.HttpMethod;
class Holder { SpringFramework springframework; }
class SpringFramework { Http http; }
class Http { Methods HttpMethod; }
class Methods { HttpMethod GET; }''', **options)
                op, = rest.operations
                self.assertEqual(op.method_name, 'exchange')
                self.assertIsNone(op.http_method)
                self.assertEqual(op.destination.value, '/items')
                self.assertEqual(op.destination.certainty, DestinationCertainty.PATH)
                self.assertTrue(op.has_supported_caller)
                self.assertTrue(op.evidence)
                self.assertTrue(op.destination.evidence)
                self.assertTrue(rest.chains)
                self.assertTrue(all(len(chain.steps) == 2 for chain in rest.chains))

    def test_fully_qualified_constant_with_source_type_package_shadow(self):
        rest, _ = self.findings(
            'rest.exchange("/items", org.springframework.http.HttpMethod.GET, null);',
            imports='''class org {
 static class springframework {
  static class http {
   static class HttpMethod { static final Object GET = null; }
  }
 }
}''')
        op, = rest.operations
        self.assertIsNone(op.http_method)
        self.assertEqual(op.destination.value, '/items')
        self.assertTrue(op.has_supported_caller)
        self.assertTrue(rest.chains)

    def test_fully_qualified_exchange_constant_after_local_scope_ends(self):
        rest, _ = self.findings('''{ Holder org = null; }
rest.exchange("/items", org.springframework.http.HttpMethod.GET, null, String.class);''')
        self.assertEqual(rest.operations[0].http_method, 'GET')

    def test_exchange_constant_after_local_scope_ends(self):
        rest, _ = self.findings('''{ Object HttpMethod = null; }
rest.exchange("/items", HttpMethod.GET, null, String.class);''')
        self.assertEqual(rest.operations[0].http_method, 'GET')

    def test_fully_qualified_constant_with_shadowed_simple_name(self):
        rest, _ = self.findings(
            'rest.exchange("/items", org.springframework.http.HttpMethod.GET, null);',
            parameters='Object HttpMethod')
        self.assertEqual(rest.operations[0].http_method, 'GET')

    def test_only_exact_argument_not_nested_expression(self):
        rest, _ = self.findings('''rest.exchange(makeUrl("/not-literal", 1),
 makeVerb(HttpMethod.POST), null); this.rest.getForObject(
 "/visible", String.class);''')
        first, second = rest.operations
        self.assertIsNone(first.http_method)
        self.assertIsNone(first.destination.value)
        self.assertEqual(second.destination.value, '/visible')
        self.assertEqual(second.destination.evidence[0].line, second.invocation.line + 1)

    def test_unknown_operations_and_shadowing(self):
        rest, _ = self.findings('rest.toString(); rest.unknown("/x");')
        self.assertEqual(rest.operations, ())
        self.assertFalse(rest.has_supported_caller)
        index = index_source('''import org.springframework.web.client.RestTemplate;
class G { RestTemplate rest; void run(RestTemplate rest) {
 rest.getForObject("/shadow", String.class);
 this.rest.<String>getForObject("/generic", String.class);
 this.rest.getForObject("/ok", String.class);
} }''', 'G.java')
        result = resolve_index(index)
        self.assertEqual(len(result.links), 1)
        self.assertEqual(len(result.diagnostics), 2)

    def test_fields_and_sites_remain_separate(self):
        rest, other = self.findings('rest.getForObject("/one", String.class);'
                                   'other.delete("/two"); rest.delete("/three");')
        self.assertEqual([op.destination.value for op in rest.operations], ['/one', '/three'])
        self.assertEqual([op.destination.value for op in other.operations], ['/two'])
        self.assertEqual(len(rest.chains), 2)


if __name__ == '__main__':
    unittest.main()
