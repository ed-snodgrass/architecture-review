"""WebClient evidence stays within a single field-rooted expression."""
import tempfile
from pathlib import Path
import unittest

from archr.findings import discover_findings, DestinationCertainty
from archr.module import load_module
from archr.traversal import trace_usage


class WebClientOperationTests(unittest.TestCase):
    def analyze(self, body, parameters=''):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'src/main/java/Gateway.java'
            source.parent.mkdir(parents=True)
            source.write_text('''
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.http.HttpMethod;
class Gateway {
 WebClient client;
 WebClient other;
 void run(''' + parameters + ''') { ''' + body + ''' }
 void unrelated() {}
}
class Service { Gateway gateway; void act() { gateway.run(''' +
                              ', '.join('null' for _ in parameters.split(',') if parameters) + '''); }
 void unrelated() { gateway.unrelated(); } }
''', encoding='utf-8')
            module = load_module(directory)
            return discover_findings(module), trace_usage(module)

    def test_verbs_requests_and_two_step_continuity(self):
        for root, verb in [('get()', 'GET'), ('post()', 'POST'), ('put()', 'PUT'),
                           ('patch()', 'PATCH'), ('delete()', 'DELETE'),
                           ('head()', 'HEAD'), ('options()', 'OPTIONS'),
                           ('method(HttpMethod.PATCH)', 'PATCH')]:
            for request in ('retrieve()', 'exchangeToMono(r -> null)',
                            'exchangeToFlux(r -> null)'):
                with self.subTest(root=root, request=request):
                    (finding, other), usage = self.analyze(
                        f'this.client.{root}.uri("/items").{request}.bodyToMono(String.class);')
                    operation, = finding.operations
                    self.assertEqual(operation.http_method, verb)
                    self.assertEqual(operation.destination.value, '/items')
                    self.assertEqual(operation.destination.certainty, DestinationCertainty.PATH)
                    self.assertTrue(finding.has_supported_caller)
                    self.assertFalse(other.has_supported_caller)
                    self.assertEqual(len(finding.chains), 1)
                    self.assertEqual(len(finding.chains[0].steps), 2)
                    self.assertEqual(len(usage.untraced_sites), 0)

    def test_build_only_and_split_chains_do_not_become_requests(self):
        (finding, _), usage = self.analyze('''
var request = client.get().uri("/items");
request.retrieve().bodyToMono(String.class);
''')
        operation, = finding.operations
        self.assertFalse(operation.is_request_operation)
        self.assertEqual(operation.destination.value, '/items')
        self.assertFalse(finding.has_supported_caller)
        self.assertEqual(finding.chains, ())
        self.assertIn('No supported caller found', finding.status_label)
        self.assertEqual(len(usage.untraced_sites), 2)

    def test_unknown_facts_do_not_erase_request(self):
        (finding, _), usage = self.analyze(
            'client.method(verb).uri(url).retrieve();', 'Object verb, String url')
        operation, = finding.operations
        self.assertIsNone(operation.http_method)
        self.assertIsNone(operation.destination.value)
        self.assertTrue(operation.has_supported_caller)
        self.assertEqual(len(usage.untraced_sites), 0)

    def test_shadowed_and_helper_roots_not_followed(self):
        (finding, _), _ = self.analyze(
            'client.get().uri("/x").retrieve();', 'WebClient client')
        self.assertEqual(finding.operations, ())
        (finding, _), _ = self.analyze(
            'client.mutate().build().get().uri("/x").retrieve();')
        self.assertFalse(finding.has_supported_caller)

    def test_literal_uri_overload_retains_unresolved_template(self):
        (finding, _), usage = self.analyze(
            'client.get().uri("https://example.test/items/{id}", id).retrieve();',
            'String id')
        operation, = finding.operations
        self.assertEqual(operation.destination.value, 'https://example.test/items/{id}')
        self.assertEqual(operation.destination.certainty, DestinationCertainty.UNRESOLVED)
        self.assertTrue(operation.has_supported_caller)
        self.assertEqual(len(usage.untraced_sites), 0)

    def test_canonical_http_method_and_multiline_evidence(self):
        (finding, _), usage = self.analyze('''
client.method(org.springframework.http.HttpMethod.TRACE)
    .uri("https://example.test/items")
    .retrieve()
    .bodyToMono(String.class);
''')
        operation, = finding.operations
        self.assertEqual(operation.http_method, 'TRACE')
        self.assertEqual(operation.destination.certainty, DestinationCertainty.LITERAL)
        self.assertEqual(operation.destination.evidence[0].line,
                         operation.invocation.line + 1)
        self.assertEqual([item.line for item in operation.evidence],
                         [operation.invocation.line, operation.invocation.line + 2])
        self.assertEqual(len(usage.untraced_sites), 0)

    def test_unknown_helper_interrupts_request_recognition(self):
        (finding, _), usage = self.analyze(
            'client.get().customize().uri("/items").retrieve();')
        operation, = finding.operations
        self.assertFalse(operation.is_request_operation)
        self.assertIsNone(operation.destination.value)
        self.assertFalse(finding.has_supported_caller)
        self.assertEqual(len(usage.untraced_sites), 3)

    def test_helper_result_and_local_request_are_not_joined(self):
        (finding, _), _ = self.analyze('''
var builder = client.get().uri("/items");
helper(builder).retrieve();
''')
        self.assertFalse(finding.has_supported_caller)
        self.assertFalse(finding.operations[0].is_request_operation)

    def test_builder_and_request_sites_on_same_field_remain_distinct(self):
        (finding, _), usage = self.analyze('''
client.post().uri("/builder");
client.get().uri("/request").retrieve().bodyToMono(String.class);
''')
        self.assertEqual(len(finding.operations), 2)
        self.assertEqual([op.is_request_operation for op in finding.operations],
                         [False, True])
        self.assertEqual(len(finding.supported_call_evidence), 1)
        self.assertEqual(len(finding.chains), 1)
        self.assertEqual(len(usage.untraced_sites), 0)

    def test_shadowed_http_method_does_not_invent_verb(self):
        (finding, _), _ = self.analyze(
            'client.method(HttpMethod.GET).uri("/items").retrieve();',
            'Object HttpMethod')
        operation, = finding.operations
        self.assertIsNone(operation.http_method)
        self.assertTrue(operation.has_supported_caller)

    def test_nested_arguments_remain_separate_gaps(self):
        (finding, _), usage = self.analyze(
            'client.get().uri(helper.path()).retrieve().bodyToMono(String.class);')
        self.assertTrue(finding.has_supported_caller)
        self.assertEqual(len(usage.untraced_sites), 1)
        self.assertEqual(usage.untraced_sites[0].invocation.receiver, 'helper')


if __name__ == '__main__':
    unittest.main()
