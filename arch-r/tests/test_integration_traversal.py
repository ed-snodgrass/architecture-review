"""All supported integrations share method-continuous bounded source tracing."""

from pathlib import Path
import tempfile
import unittest

from archr.findings import UsageCertainty, discover_findings
from archr.module import load_module
from archr.traversal import DEFAULT_MAX_CALL_STEPS, trace_usage


CASES = (
    ('OpenFeign', '''@org.springframework.cloud.openfeign.FeignClient(name="remote")
interface Remote { void send(); }''', 'Remote', 'remote.send();', 'send'),
    ('Spring Data JPA', '''interface Remote extends
org.springframework.data.jpa.repository.JpaRepository<Object, Long> {}''',
     'Remote', 'remote.save(null);', 'save'),
    ('Spring JDBC', '', 'org.springframework.jdbc.core.JdbcTemplate',
     'remote.update("delete from orders");', 'update'),
    ('Spring HTTP', '', 'org.springframework.web.client.RestTemplate',
     'remote.getForObject("/orders", String.class);', 'getForObject'),
    ('Spring reactive HTTP', '',
     'org.springframework.web.reactive.function.client.WebClient',
     'remote.get().uri("/orders").retrieve().bodyToMono(String.class);', 'retrieve'),
)


class IntegrationTraversalTests(unittest.TestCase):
    def module(self, source):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / 'src/main/java/shop/Example.java'
        path.parent.mkdir(parents=True)
        path.write_text('package shop;\n' + source, encoding='utf-8')
        return load_module(temp.name)

    def fixture(self, declaration, field_type, operation, route='direct'):
        port = 'interface Port { void send(); void unrelated(); }'
        gateway = f'''class Gateway implements Port {{
 final {field_type} remote;
 Gateway({field_type} remote) {{ this.remote = remote; }}
 public void send() {{ {operation} }}
 public void unrelated() {{}}
}}'''
        receiver = 'Gateway' if route == 'direct' else 'Port'
        extra = ('''class Other implements Port {
 public void send() {} public void unrelated() {}
}''' if route == 'ambiguous' else '')
        return self.module(declaration + '\n' + port + '\n' + gateway + '\n' + extra + f'''
class Service {{
 {receiver} gateway;
 void act() {{ gateway.send(); }}
 void unrelated() {{ gateway.unrelated(); }}
}}
class Entry {{ Service service; void run() {{ service.act(); }} }}
''')

    def test_every_mechanism_uses_two_method_steps_and_retains_evidence(self):
        for mechanism, declaration, field_type, operation, endpoint in CASES:
            with self.subTest(mechanism=mechanism):
                module = self.fixture(declaration, field_type, operation)
                finding, = discover_findings(module)
                self.assertEqual(finding.declaration.mechanism, mechanism)
                chain, = finding.chains
                self.assertEqual(DEFAULT_MAX_CALL_STEPS, 2)
                self.assertEqual([s.link.caller_method.name for s in chain.steps],
                                 ['send', 'act'])
                self.assertEqual(chain.steps[0].link.target_method.name, endpoint)
                self.assertEqual(chain.boundary, 'depth')
                self.assertEqual(chain.certainty, 'observed')
                self.assertEqual(finding.usage_certainty, UsageCertainty.OBSERVED)
                root = chain.steps[0].link
                self.assertEqual(root.receiver_field.name, 'remote')
                self.assertEqual(root.caller_type, 'shop.Gateway')
                self.assertEqual(root.invocation.receiver, 'remote')
                self.assertEqual(root.invocation.source_path,
                                 'src/main/java/shop/Example.java')
                self.assertGreater(root.invocation.line, root.receiver_field.line)
                self.assertEqual(len(finding.supported_call_evidence), 1)
                self.assertEqual(len(trace_usage(module).untraced_sites), 0)
                # Extra fluent segments and unrelated methods are not call steps.
                longer, = trace_usage(module, max_depth=4).chains
                self.assertEqual([s.link.caller_method.name for s in longer.steps],
                                 ['send', 'act', 'run'])
                self.assertIsNone(longer.boundary)

    def test_possible_interface_route_costs_no_step_for_every_mechanism(self):
        for mechanism, declaration, field_type, operation, _ in CASES:
            with self.subTest(mechanism=mechanism):
                module = self.fixture(declaration, field_type, operation, 'interface')
                finding, = discover_findings(module)
                chain, = finding.chains
                self.assertEqual(len(chain.steps), 2)
                self.assertEqual(chain.certainty, 'possible')
                self.assertEqual(finding.usage_certainty, UsageCertainty.POSSIBLE)
                self.assertEqual([step.certainty for step in chain.steps],
                                 ['observed', 'possible'])
                connection = chain.steps[1].interface_connection
                self.assertEqual(connection.interface_type.qualified_name, 'shop.Port')
                self.assertEqual(connection.implementation_type.qualified_name,
                                 'shop.Gateway')
                self.assertEqual(connection.implementation_method,
                                 chain.steps[0].link.caller_method)
                self.assertIn('unverified', connection.reason)
                self.assertEqual(len(trace_usage(module).untraced_sites), 0)

    def test_ambiguous_interface_never_manufactures_an_upstream_step(self):
        for mechanism, declaration, field_type, operation, _ in CASES:
            with self.subTest(mechanism=mechanism):
                module = self.fixture(declaration, field_type, operation, 'ambiguous')
                finding, = discover_findings(module)
                chain, = finding.chains
                self.assertEqual(len(chain.steps), 1)
                self.assertEqual(chain.certainty, 'observed')
                self.assertIsNone(chain.boundary)
                self.assertTrue(trace_usage(module).interface_diagnostics)

    def test_same_library_type_fields_keep_separate_chains(self):
        for mechanism, _, field_type, operation, _ in CASES[2:]:
            with self.subTest(mechanism=mechanism):
                module = self.module(f'''class Gateway {{
 {field_type} remote;
 {field_type} other;
 void send() {{ {operation} }}
 void otherSend() {{ {operation.replace('remote.', 'this.other.')} }}
 void unrelated() {{}}
}}
class Service {{
 Gateway gateway;
 void first() {{ gateway.send(); }}
 void second() {{ gateway.otherSend(); }}
 void unrelated() {{ gateway.unrelated(); }}
}}''')
                findings = {f.declaration.field_name: f for f in discover_findings(module)}
                self.assertEqual(set(findings), {'remote', 'other'})
                for field, callers in (('remote', ['send', 'first']),
                                       ('other', ['otherSend', 'second'])):
                    chain, = findings[field].chains
                    self.assertEqual([s.link.caller_method.name for s in chain.steps],
                                     callers)
                    self.assertEqual(chain.steps[0].link.receiver_field.name, field)

    def test_repository_fields_share_one_finding_without_local_implementation(self):
        module = self.module('''interface Orders extends
org.springframework.data.jpa.repository.JpaRepository<Object, Long> {
 Object findSpecial(String key);
}
class Gateway {
 Orders first; Orders second;
 void save() { first.save(null); }
 void lookup() { this.second.findSpecial("key"); }
 void unrelated() { first.toString(); }
}
class Service {
 Gateway gateway;
 void save() { gateway.save(); }
 void lookup() { gateway.lookup(); }
 void unrelated() { gateway.unrelated(); }
}''')
        finding, = discover_findings(module)
        self.assertEqual(len(finding.chains), 2)
        self.assertEqual({c.client_type for c in finding.chains}, {'shop.Orders'})
        self.assertEqual({c.steps[0].link.receiver_field.name for c in finding.chains},
                         {'first', 'second'})
        self.assertEqual({tuple(s.link.caller_method.name for s in c.steps)
                          for c in finding.chains},
                         {('save', 'save'), ('lookup', 'lookup')})
        self.assertTrue(all(c.certainty == 'observed' for c in finding.chains))
        self.assertFalse(trace_usage(module).interface_diagnostics)


if __name__ == '__main__':
    unittest.main()
