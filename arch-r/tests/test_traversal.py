"""Objective contracts for the first pending iteration-002 task: traversal.

Proposed seam (not implemented here): archr.traversal.trace_usage(Module,
max_depth=DEFAULT_MAX_CALL_STEPS), with DEFAULT_MAX_CALL_STEPS == 2.
Result: max_depth and chains. Each chain exposes client_type (qualified name),
steps (nearest Feign first), certainty ('observed' or 'possible'), boundary
(None, 'depth', or 'cycle'), boundary_reason, and cycle_link (CallLink or None).
A step exposes link (existing CallLink), certainty, and interface_connection
(existing InterfaceConnection or None). Interface resolution changes the method
endpoint used for traversal, but costs no additional step. Chains are maximal
within the limit, per distinct call-site path; prefixes need not be duplicated.
Cycle identity is the qualified type plus method declaration, not class alone.
The closing cycle link is evidence, not another repeated node in steps.

These tests specify a testable traversal seam, not report prose or CLI changes.
All fixtures are source-only, confined to disposable modules; no Java is run.
"""

import importlib
from pathlib import Path
import tempfile
import unittest

from archr.module import load_module


class TraversalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='arch_r_traversal_')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'src/main/java').mkdir(parents=True)
        self.module = load_module(str(self.root))
        self.put('Client', '''import org.springframework.cloud.openfeign.FeignClient;
@FeignClient(name="products", url="${product.url}")
public interface Client {
    String get(String id);
    void ping();
}
''')

    def put(self, name, source, directory='src/main/java'):
        path = self.root / directory / 'sample' / (name + '.java')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('package sample;\n' + source, encoding='utf-8')
        return f'{directory}/sample/{name}.java'

    def trace(self, **kwargs):
        try:
            api = importlib.import_module('archr.traversal')
        except ModuleNotFoundError as exc:
            if exc.name != 'archr.traversal':
                raise
            self.fail('Missing traversal seam: archr.traversal.trace_usage')
        return api.trace_usage(self.module, **kwargs)

    @staticmethod
    def path(chain):
        return tuple((s.link.caller_type, s.link.caller_method.name,
                      s.link.target_type, s.link.target_method.name)
                     for s in chain.steps)

    def gateway(self):
        self.put('Gateway', '''class Gateway {
    Client client;
    String lookup(String id) { return client.get(id); }
    void health() {}
}
''')

    def order(self, method='lookup', name='Order'):
        self.put(name, f'''class {name} {{
    Gateway gateway;
    void place(String id) {{ gateway.{method}({'id' if method == 'lookup' else ''}); }}
}}
''')

    def test_default_is_one_named_setting_and_direct_call_is_one_step(self):
        self.put('Order', '''class Order {
    final Client client;
    Order(Client client) { this.client = client; }
    void place(String id) { this.client.get(id); }
}
''')
        result = self.trace()
        api = importlib.import_module('archr.traversal')
        self.assertEqual(api.DEFAULT_MAX_CALL_STEPS, 2)
        self.assertEqual(result.max_depth, 2)
        self.assertEqual(len(result.chains), 1)
        chain = result.chains[0]
        self.assertEqual(chain.client_type, 'sample.Client')
        self.assertEqual(self.path(chain), (('sample.Order', 'place', 'sample.Client', 'get'),))
        self.assertEqual(chain.certainty, 'observed')
        self.assertIsNone(chain.boundary)
        step = chain.steps[0]
        self.assertEqual(step.certainty, 'observed')
        self.assertIsNone(step.interface_connection)
        self.assertEqual((step.link.invocation.source_path, step.link.invocation.line),
                         ('src/main/java/sample/Order.java', 5))
        self.assertEqual((step.link.receiver_field.type_name, step.link.receiver_field.line),
                         ('sample.Client', 3))
        self.assertEqual((step.link.target_method.source_path, step.link.target_method.line),
                         ('src/main/java/sample/Client.java', 5))

    def test_two_step_intermediary_has_both_invocations_and_declarations(self):
        self.gateway()
        self.order()
        result = self.trace()
        self.assertEqual(len(result.chains), 1)
        chain = result.chains[0]
        self.assertEqual(self.path(chain), (
            ('sample.Gateway', 'lookup', 'sample.Client', 'get'),
            ('sample.Order', 'place', 'sample.Gateway', 'lookup')))
        self.assertEqual(chain.boundary, 'depth')
        self.assertTrue(chain.boundary_reason.strip())
        self.assertRegex(chain.boundary_reason.lower(), r'(may|might|could).*continu')
        self.assertEqual([(s.link.invocation.source_path, s.link.invocation.line,
                           s.link.receiver_field.line, s.link.target_method.line)
                          for s in chain.steps],
                         [('src/main/java/sample/Gateway.java', 4, 3, 5),
                          ('src/main/java/sample/Order.java', 4, 3, 4)])

    def test_depth_is_passed_to_traversal_and_http_is_not_a_step(self):
        self.gateway()
        self.order()
        self.put('Checkout', '''class Checkout {
    Order order;
    void checkout(String id) { order.place(id); }
}
''')
        for limit, callers in ((1, ['sample.Gateway']),
                               (2, ['sample.Gateway', 'sample.Order']),
                               (3, ['sample.Gateway', 'sample.Order', 'sample.Checkout']),
                               (4, ['sample.Gateway', 'sample.Order', 'sample.Checkout'])):
            with self.subTest(limit=limit):
                result = self.trace(max_depth=limit)
                self.assertEqual(result.max_depth, limit)
                self.assertEqual(len(result.chains), 1)
                chain = result.chains[0]
                self.assertEqual([s.link.caller_type for s in chain.steps], callers)
                self.assertEqual(chain.boundary, 'depth' if limit <= 3 else None)

    def test_unrelated_intermediary_method_and_same_class_helper_are_not_followed(self):
        self.gateway()
        self.order(method='health')
        self.put('HelperOrder', '''class HelperOrder {
    Gateway gateway;
    void place(String id) { helper(id); }
    void helper(String id) { gateway.lookup(id); }
}
''')
        paths = [self.path(c) for c in self.trace(max_depth=4).chains]
        self.assertEqual(paths, [(
            ('sample.Gateway', 'lookup', 'sample.Client', 'get'),
            ('sample.HelperOrder', 'helper', 'sample.Gateway', 'lookup'))])

    def interface_route(self, second=False):
        self.put('Port', 'public interface Port { String lookup(String id); void health(); }\n')
        for name in (('HttpGateway', 'OtherGateway') if second else ('HttpGateway',)):
            self.put(name, f'''class {name} implements Port {{
    Client client;
    public String lookup(String id) {{ return client.get(id); }}
    public void health() {{}}
}}
''')
        self.put('Order', '''class Order {
    Port port;
    void place(String id) { port.lookup(id); }
}
''')

    def test_interface_resolution_is_free_and_full_chain_is_possible(self):
        self.interface_route()
        chain, = self.trace().chains
        self.assertEqual(len(chain.steps), 2)
        self.assertEqual(self.path(chain), (
            ('sample.HttpGateway', 'lookup', 'sample.Client', 'get'),
            ('sample.Order', 'place', 'sample.Port', 'lookup')))
        self.assertEqual(chain.certainty, 'possible')
        self.assertEqual([s.certainty for s in chain.steps], ['observed', 'possible'])
        connection = chain.steps[1].interface_connection
        self.assertIsNotNone(connection)
        self.assertEqual(connection.link, chain.steps[1].link)
        self.assertEqual(connection.implementation_type.qualified_name, 'sample.HttpGateway')
        self.assertEqual(connection.implementation_type.line, 2)
        self.assertEqual(connection.implementation_method.line, 4)
        self.assertEqual(connection.link.target_method.line, 2)
        self.assertRegex(connection.reason.lower(), r'runtime.*(unverified|not verified)')
        self.assertEqual(chain.boundary, 'depth')

    def test_possible_certainty_propagates_to_another_observed_upstream_step(self):
        self.interface_route()
        self.put('Checkout', '''class Checkout {
    Order order;
    void checkout(String id) { order.place(id); }
}
''')
        chain, = self.trace(max_depth=4).chains
        self.assertEqual(len(chain.steps), 3)
        self.assertEqual([s.certainty for s in chain.steps], ['observed', 'possible', 'observed'])
        self.assertEqual(chain.certainty, 'possible')
        self.assertIsNone(chain.boundary)

    def test_ambiguous_interfaces_do_not_manufacture_upstream_paths(self):
        self.interface_route(second=True)
        chains = self.trace(max_depth=4).chains
        self.assertEqual(len(chains), 2)
        self.assertEqual(sorted(c.steps[0].link.caller_type for c in chains),
                         ['sample.HttpGateway', 'sample.OtherGateway'])
        for chain in chains:
            self.assertEqual(len(chain.steps), 1)
            self.assertEqual(chain.certainty, 'observed')
            self.assertIsNone(chain.boundary)

    def test_interface_unrelated_method_does_not_join_the_feign_method(self):
        self.interface_route()
        self.put('Order', '''class Order {
    Port port;
    void place() { port.health(); }
}
''')
        chain, = self.trace(max_depth=4).chains
        self.assertEqual(self.path(chain),
                         (('sample.HttpGateway', 'lookup', 'sample.Client', 'get'),))
        self.assertEqual(chain.certainty, 'observed')

    def test_no_calls_means_no_chains_including_out_of_boundary_sources(self):
        self.put('Holder', 'class Holder { Client client; Holder(Client c) { client = c; } }\n')
        for directory in ('src/test/java', 'target/generated-sources', 'sibling/src/main/java'):
            self.put('Outside', 'class Outside { Client client; void run() { client.ping(); } }\n',
                     directory=directory)
        self.assertEqual(tuple(self.trace().chains), ())

    def test_cycle_stops_without_repeated_methods_and_keeps_cutoff_evidence(self):
        self.put('A', '''class A {
    Client client;
    B b;
    void work(String id) { client.get(id); b.work(id); }
}
''')
        self.put('B', '''class B {
    A a;
    void work(String id) { a.work(id); }
}
''')
        chain, = self.trace(max_depth=6).chains
        self.assertEqual(self.path(chain), (
            ('sample.A', 'work', 'sample.Client', 'get'),
            ('sample.B', 'work', 'sample.A', 'work')))
        self.assertEqual(chain.boundary, 'cycle')
        self.assertIn('cycle', chain.boundary_reason.lower())
        self.assertEqual((chain.cycle_link.caller_type, chain.cycle_link.target_type,
                          chain.cycle_link.invocation.source_path, chain.cycle_link.invocation.line),
                         ('sample.A', 'sample.B', 'src/main/java/sample/A.java', 5))

    def test_two_methods_of_same_class_are_not_a_cycle(self):
        self.put('A', '''class A {
    Client client;
    B b;
    void first(String id) { client.get(id); }
    void second(String id) { b.work(id); }
}
''')
        self.put('B', '''class B {
    A a;
    void work(String id) { a.first(id); }
}
''')
        chain, = self.trace(max_depth=5).chains
        self.assertEqual([s.link.caller_method.name for s in chain.steps],
                         ['first', 'work', 'second'])
        self.assertIsNone(chain.boundary)

    def test_multiple_callers_and_call_sites_keep_evidence_and_stable_order(self):
        self.gateway()
        self.order(name='ZOrder')
        self.put('AOrder', '''class AOrder {
    Gateway gateway;
    void place(String id) {
        gateway.lookup(id);
        this.gateway.lookup(id);
    }
}
''')
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = self.trace()
        self.assertEqual(len(result.chains), 3)
        evidence = sorted((c.steps[1].link.caller_type, c.steps[1].link.invocation.line)
                          for c in result.chains)
        self.assertEqual(evidence, [('sample.AOrder', 5), ('sample.AOrder', 6), ('sample.ZOrder', 4)])
        for _ in range(3):
            self.assertEqual(self.trace(), result)
        # Changing filesystem enumeration/insertion order must not change traversal ordering.
        for relative, content in reversed(list(before.items())):
            (self.root / relative).unlink()
            (self.root / relative).write_bytes(content)
        self.assertEqual(self.trace(), result)
        self.assertEqual({p.relative_to(self.root): p.read_bytes()
                          for p in self.root.rglob('*') if p.is_file()}, before)

    def test_name_and_arity_select_only_the_method_reaching_feign(self):
        self.put('Gateway', '''class Gateway {
    Client client;
    String lookup(String id) { return client.get(id); }
    void lookup() {}
}
''')
        self.order()
        self.put('Unrelated', '''class Unrelated {
    Gateway gateway;
    void run() { gateway.lookup(); }
}
''')
        chain, = self.trace(max_depth=4).chains
        self.assertEqual(self.path(chain), (
            ('sample.Gateway', 'lookup', 'sample.Client', 'get'),
            ('sample.Order', 'place', 'sample.Gateway', 'lookup')))
        self.assertEqual(chain.steps[1].link.target_method.parameter_count, 1)

    def test_missing_local_implementation_does_not_create_a_route(self):
        self.gateway()
        self.put('Port', 'public interface Port { String lookup(String id); }\n')
        self.put('Order', '''class Order {
    Port port;
    void place(String id) { port.lookup(id); }
}
''')
        chain, = self.trace(max_depth=4).chains
        self.assertEqual(self.path(chain),
                         (('sample.Gateway', 'lookup', 'sample.Client', 'get'),))
        self.assertEqual(chain.certainty, 'observed')

    def test_ambiguous_overloads_cannot_supply_a_traversal_step(self):
        self.gateway()
        self.put('Gateway', '''class Gateway {
    Client client;
    String lookup(String id) { return client.get(id); }
    String lookup(Integer id) { return "local"; }
}
''')
        self.order()
        chain, = self.trace(max_depth=4).chains
        self.assertEqual(self.path(chain),
                         (('sample.Gateway', 'lookup', 'sample.Client', 'get'),))
        self.assertIsNone(chain.boundary)


if __name__ == '__main__':
    unittest.main()
