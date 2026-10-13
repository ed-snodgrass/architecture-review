"""CLI contracts for the iteration 002 Mermaid diagram task.

Fixtures are disposable source only. Node IDs, declaration order, and exact
relationship prose are deliberately not prescribed. No Java is compiled/run.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ENTRY_POINT = Path(__file__).resolve().parents[1] / 'arch-r'


class Diagram:
    """Read the small C4 declaration/relationship subset, ignoring chosen IDs."""

    def __init__(self, testcase, report):
        blocks = re.findall(r'^```mermaid\s*\n(.*?)^```\s*$', report,
                            re.M | re.S)
        testcase.assertEqual(len(blocks), 1, 'Report must contain one diagram')
        self.text = blocks[0]
        testcase.assertRegex(self.text, r'\bC4(?:Context|Container|Component)\b')
        self.nodes = {}
        self.edges = []
        self.boundaries = {}
        stack = []
        for line in self.text.splitlines():
            boundary = re.match(
                r'\s*(?:System|Container|Enterprise)_Boundary\(\s*(\w+)\s*,', line)
            if boundary:
                stack.append(boundary[1])
                continue
            if line.strip() == '}':
                if stack:
                    stack.pop()
                continue
            node = re.match(
                r'\s*(System(?:_Ext)?|Container(?:_Ext)?|Component(?:_Ext)?)'
                r'\(\s*(\w+)\s*,\s*"([^"]*)"', line)
            if node:
                testcase.assertNotIn(node[2], self.nodes, 'Duplicate node ID')
                self.nodes[node[2]] = (node[1], node[3])
                self.boundaries[node[2]] = tuple(stack)
            edge = re.match(
                r'\s*Rel(?:_[A-Za-z]+)?\(\s*(\w+)\s*,\s*(\w+)\s*,\s*"([^"]*)"',
                line)
            if edge:
                self.edges.append((edge[1], edge[2], edge[3]))
        for source, target, _ in self.edges:
            testcase.assertIn(source, self.nodes, 'Undeclared relationship source')
            testcase.assertIn(target, self.nodes, 'Undeclared relationship target')

    def named(self, testcase, name):
        matches = [key for key, (_, label) in self.nodes.items()
                   if re.search(r'(?<![\w$])' + re.escape(name) + r'(?![\w$])', label)]
        testcase.assertEqual(len(matches), 1,
                             f'{name} must have exactly one shared node: {self.text}')
        return matches[0]

    def labels(self, source, target):
        return [label for start, end, label in self.edges
                if (start, end) == (source, target)]

    def paths(self, source, target, seen=()):
        if source == target:
            return [()]
        if source in seen:
            return []
        return [(label,) + rest for start, end, label in self.edges if start == source
                for rest in self.paths(end, target, seen + (source,))]


class UsageDiagramTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='arch_r_diagram_')
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.module = self.work / 'orders'
        (self.module / 'src/main/java/sample').mkdir(parents=True)
        self.client('Client', 'products')

    def put(self, name, source):
        path = self.module / 'src/main/java/sample' / (name + '.java')
        path.write_text(source, encoding='utf-8')

    def client(self, name, system):
        self.put(name, f'''package sample;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
@FeignClient(name="{system}", url="https://{system}.example")
public interface {name} {{
    @GetMapping("/items/{{id}}")
    String get(String id);
}}
''')

    def report(self):
        before = {p.relative_to(self.module): p.read_bytes()
                  for p in self.module.rglob('*') if p.is_file()}
        result = subprocess.run([str(ENTRY_POINT), 'analyze', str(self.module)],
                                cwd=self.work, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertEqual(before, {p.relative_to(self.module): p.read_bytes()
                                 for p in self.module.rglob('*') if p.is_file()})
        report = (self.work / 'arch-r-report-orders.md').read_text(encoding='utf-8')
        return report, Diagram(self, report)

    def observed(self, diagram, source, target):
        labels = diagram.labels(source, target)
        self.assertEqual(len(labels), 1, 'Share one edge for the class relationship')
        self.assertRegex(labels[0].lower(), r'observed')
        self.assertNotRegex(labels[0].lower(), r'possible|suggest')

    def contained(self, diagram, *nodes):
        common = set(diagram.boundaries[nodes[0]])
        for node in nodes[1:]:
            common.intersection_update(diagram.boundaries[node])
        self.assertTrue(common, 'Calling classes and Feign points belong inside the module')
        for node, (kind, _) in diagram.nodes.items():
            if kind.endswith('_Ext'):
                self.assertFalse(common.intersection(diagram.boundaries[node]),
                                 'External systems must be outside the module')

    def clean_nodes(self, diagram, *method_names):
        for _, label in diagram.nodes.values():
            self.assertNotRegex(label, r'\.java|src/main/java|:\d+|\(')
            for name in method_names:
                self.assertNotRegex(label, r'\b' + re.escape(name) + r'\b')
        self.assertNotRegex(diagram.text.lower(), r'suggested adapter|proposed adapter')

    def gateway(self):
        self.put('Gateway', '''package sample;
class Gateway {
    Client client;
    String lookup(String id) { return client.get(id); }
    void health() {}
}
''')

    def order(self, method='lookup'):
        argument = 'id' if method == 'lookup' else ''
        self.put('Order', f'''package sample;
class Order {{
    Gateway gateway;
    void place(String id) {{ gateway.{method}({argument}); }}
}}
''')

    def test_direct_usage_is_inside_module_and_connected_to_external_system(self):
        self.put('Order', '''package sample;
class Order {
    final Client client;
    Order(Client client) { this.client = client; }
    void place(String id) { this.client.get(id); }
}
''')
        _, diagram = self.report()
        order, client, external = [diagram.named(self, name)
                                   for name in ('Order', 'Client', 'products')]
        self.observed(diagram, order, client)
        self.assertTrue(diagram.labels(client, external))
        self.assertTrue(diagram.nodes[external][0].endswith('_Ext'))
        self.contained(diagram, order, client)
        self.clean_nodes(diagram, 'place', 'get')
        # Guidance must not create extra existing adapter components.
        self.assertEqual({node for node, (kind, label) in diagram.nodes.items()
                          if not kind.endswith('_Ext') and label != 'orders'},
                         {order, client})

    def test_intermediary_chain_stops_at_two_steps(self):
        self.gateway()
        self.order()
        self.put('Checkout', '''package sample;
class Checkout {
    Order order;
    void checkout(String id) { order.place(id); }
}
''')
        _, diagram = self.report()
        order, gateway, client = [diagram.named(self, name)
                                  for name in ('Order', 'Gateway', 'Client')]
        self.observed(diagram, order, gateway)
        self.observed(diagram, gateway, client)
        self.contained(diagram, order, gateway, client)
        self.assertNotIn('Checkout', diagram.text)
        self.clean_nodes(diagram, 'lookup', 'place', 'get', 'checkout')

    def test_unrelated_intermediary_method_does_not_create_a_route(self):
        self.gateway()
        self.order('health')
        _, diagram = self.report()
        gateway, client = [diagram.named(self, name) for name in ('Gateway', 'Client')]
        self.observed(diagram, gateway, client)
        orders = [node for node, (_, label) in diagram.nodes.items() if 'Order' in label]
        for order in orders:
            self.assertEqual(diagram.paths(order, client), [])

    def interface_route(self, multiple=False):
        self.put('Port', '''package sample;
public interface Port {
    String lookup(String id);
}
''')
        for name in (('HttpGateway', 'OtherGateway') if multiple else ('HttpGateway',)):
            self.put(name, f'''package sample;
class {name} implements Port {{
    Client client;
    public String lookup(String id) {{ return client.get(id); }}
}}
''')
        self.put('Order', '''package sample;
class Order {
    Port port;
    void place(String id) { port.lookup(id); }
}
''')

    def test_unique_interface_connection_is_labeled_possible_not_observed_wiring(self):
        self.interface_route()
        _, diagram = self.report()
        order, gateway, client = [diagram.named(self, name)
                                  for name in ('Order', 'HttpGateway', 'Client')]
        # The interface may be a separate node, a combined label, or link context.
        self.assertRegex(diagram.text, r'\bPort\b')
        paths = diagram.paths(order, gateway)
        self.assertTrue(paths, 'Show the candidate interface route')
        for path in paths:
            self.assertTrue(any(re.search(r'possible', label, re.I) for label in path),
                            'Never present runtime interface wiring as fully observed')
        self.observed(diagram, gateway, client)
        self.contained(diagram, order, gateway, client)
        self.clean_nodes(diagram, 'lookup', 'place', 'get')

    def test_ambiguous_interface_does_not_establish_upstream_route(self):
        self.interface_route(multiple=True)
        _, diagram = self.report()
        client = diagram.named(self, 'Client')
        for name in ('HttpGateway', 'OtherGateway'):
            self.observed(diagram, diagram.named(self, name), client)
        for node, (_, label) in diagram.nodes.items():
            if re.search(r'\b(?:Order|Port)\b', label):
                self.assertEqual(diagram.paths(node, client), [],
                                 'Ambiguous interface must not select an implementation')

    def test_declarations_without_calls_do_not_create_usage_edges(self):
        self.put('Holder', '''package sample;
class Holder {
    Client client;
    Holder(Client client) { this.client = client; }
}
''')
        _, diagram = self.report()
        client, external = [diagram.named(self, name) for name in ('Client', 'products')]
        self.assertTrue(diagram.labels(client, external))
        for node, (_, label) in diagram.nodes.items():
            if 'Holder' in label:
                self.assertEqual(diagram.paths(node, client), [])

    def repeated_clients(self, called_packages=()):
        """Public clients in separate packages, with optional supported callers."""
        for package in ('products', 'billing', 'archive'):
            root = self.module / 'src/main/java' / package
            root.mkdir(parents=True)
            (root / 'RemoteClient.java').write_text(f'''package {package};
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
@FeignClient(name="{package}-api", url="https://{package}.example")
public interface RemoteClient {{
    @GetMapping("/items/{{id}}")
    String get(String id);
}}
''', encoding='utf-8')
            if package in called_packages:
                self.put(package.title() + 'Caller', f'''package sample;
import {package}.RemoteClient;
class {package.title()}Caller {{
    RemoteClient client;
    void fetch(String id) {{ client.get(id); }}
}}
''')

    def assert_repeated_client_routes(self, diagram):
        clients = [diagram.named(self, package + '.RemoteClient')
                   for package in ('products', 'billing', 'archive')]
        self.assertEqual(len(set(clients)), 3, 'Distinct declarations need distinct nodes')
        for package, client in zip(('products', 'billing', 'archive'), clients):
            self.assertEqual(diagram.nodes[client][1], package + '.RemoteClient')
            external = diagram.named(self, package + '-api')
            self.assertTrue(diagram.nodes[external][0].endswith('_Ext'))
            self.assertTrue(diagram.labels(client, external))
            # Never associate a declaration with the other same-named client's system.
            outgoing = {target for source, target, _ in diagram.edges if source == client}
            self.assertEqual(outgoing, {external})
        # Non-colliding Feign labels should stay short.
        unique = diagram.named(self, 'Client')
        self.assertEqual(diagram.nodes[unique][1], 'Client')
        return clients

    def test_same_named_clients_keep_distinct_observed_routes_and_uncalled_node(self):
        self.repeated_clients(('products', 'billing'))
        report, diagram = self.report()
        clients = self.assert_repeated_client_routes(diagram)
        callers = [diagram.named(self, package.title() + 'Caller')
                   for package in ('products', 'billing')]
        self.contained(diagram, *clients, *callers)
        for caller, client in zip(callers, clients):
            self.observed(diagram, caller, client)
            for other in clients:
                if other != client:
                    self.assertEqual(diagram.paths(caller, other), [])
        for package in ('products', 'billing', 'archive'):
            self.assertIn(f'src/main/java/{package}/RemoteClient.java:4', report)
        for package in ('products', 'billing'):
            self.assertIn(f'src/main/java/sample/{package.title()}Caller.java:5', report)
        self.assertFalse(any(source in callers and target == clients[2]
                             for source, target, _ in diagram.edges))
        self.clean_nodes(diagram, 'fetch', 'get')
        repeated, _ = self.report()
        self.assertEqual(report, repeated)

    def test_same_named_clients_are_qualified_even_when_none_have_callers(self):
        self.repeated_clients()
        report, diagram = self.report()
        clients = self.assert_repeated_client_routes(diagram)
        self.contained(diagram, *clients)
        self.assertFalse(any(kind == 'Component' for kind, _ in diagram.nodes.values()))
        repeated, _ = self.report()
        self.assertEqual(report, repeated)

    def test_declaration_only_renderer_disambiguates_same_named_clients(self):
        # Exercise the public renderer without a usage inventory as well as the CLI.
        from archr.discovery import extract_clients
        from archr.module import Module
        from archr.report import render_report

        self.repeated_clients()
        clients = []
        for path in self.module.rglob('*.java'):
            clients.extend(extract_clients(path.read_text(encoding='utf-8'),
                                           path.relative_to(self.module).as_posix()))
        module = Module(self.module, self.module / 'src/main/java', 'orders')
        report = render_report(module, clients)
        self.assert_repeated_client_routes(Diagram(self, report))
        self.assertEqual(report, render_report(module, reversed(clients)))

    def test_shared_edge_preserves_observed_and_possible_connections(self):
        self.interface_route()
        self.put('Order', '''package sample;
class Order {
    Port port;
    HttpGateway gateway;
    void place(String id) {
        port.lookup(id);
        gateway.lookup(id);
        port.lookup(id);
    }
}
''')
        report, diagram = self.report()
        order, gateway, client = [diagram.named(self, name)
                                  for name in ('Order', 'HttpGateway', 'Client')]
        # Class-level deduplication cannot erase either method-level certainty.
        paths = diagram.paths(order, gateway)
        self.assertTrue(paths)
        labels = ' '.join(label for path in paths for label in path).lower()
        self.assertIn('observed', labels)
        self.assertIn('possible', labels)
        self.assertIn('Port', diagram.text)
        pairs = [(source, target) for source, target, _ in diagram.edges]
        self.assertEqual(len(pairs), len(set(pairs)))
        self.observed(diagram, gateway, client)
        self.contained(diagram, order, gateway, client)
        supporting = report.replace('```mermaid\n' + diagram.text + '```', '')
        for line in (6, 7, 8):
            self.assertIn(f'src/main/java/sample/Order.java:{line}', supporting)
        self.assertIn('src/main/java/sample/Port.java:3', supporting)
        self.assertIn('src/main/java/sample/HttpGateway.java:2', supporting)
        self.assertIn('src/main/java/sample/HttpGateway.java:4', supporting)
        self.clean_nodes(diagram, 'lookup', 'place', 'get')
        repeated, _ = self.report()
        self.assertEqual(report, repeated)

    def test_missing_interface_implementation_does_not_invent_diagram_route(self):
        self.interface_route()
        (self.module / 'src/main/java/sample/HttpGateway.java').unlink()
        # An unrelated supported call keeps the usage diagram nonempty.
        self.put('DirectCaller', '''package sample;
class DirectCaller {
    Client client;
    void fetch(String id) { client.get(id); }
}
''')
        _, diagram = self.report()
        direct, client = [diagram.named(self, name)
                          for name in ('DirectCaller', 'Client')]
        self.observed(diagram, direct, client)
        for node, (_, label) in diagram.nodes.items():
            if re.search(r'\b(?:Order|Port)\b', label):
                self.assertEqual(diagram.paths(node, client), [],
                                 'No local implementation means no candidate route')
        self.assertNotIn('HttpGateway', diagram.text)
        self.contained(diagram, direct, client)
        self.clean_nodes(diagram, 'lookup', 'place', 'fetch', 'get')

    def test_test_source_callers_never_become_diagram_components(self):
        self.gateway()
        self.order()
        test_root = self.module / 'src/test/java/sample'
        test_root.mkdir(parents=True)
        (test_root / 'TestCaller.java').write_text('''package sample;
class TestCaller {
    Client client;
    Gateway gateway;
    void exercise(String id) {
        client.get(id);
        gateway.lookup(id);
    }
}
''', encoding='utf-8')
        report, diagram = self.report()
        order, gateway, client = [diagram.named(self, name)
                                  for name in ('Order', 'Gateway', 'Client')]
        self.observed(diagram, order, gateway)
        self.observed(diagram, gateway, client)
        self.assertNotIn('TestCaller', diagram.text)
        self.assertNotIn('src/test/java/sample/TestCaller.java', report)
        self.contained(diagram, order, gateway, client)
        self.clean_nodes(diagram, 'lookup', 'place', 'exercise', 'get')

    def test_shared_nodes_edges_and_all_callsite_evidence_remain_stable(self):
        self.client('BillingClient', 'billing')
        self.put('Gateway', '''package sample;
class Gateway {
    Client client;
    BillingClient billing;
    void lookup(String id) {
        client.get(id);
        client.get(id);
        billing.get(id);
    }
}
''')
        self.put('Order', '''package sample;
class Order {
    Gateway gateway;
    void place(String id) {
        gateway.lookup(id);
        gateway.lookup(id);
    }
}
''')
        self.put('OtherOrder', '''package sample;
class OtherOrder {
    Gateway gateway;
    void place(String id) { gateway.lookup(id); }
}
''')
        report, diagram = self.report()
        order, other, gateway, client, billing = [diagram.named(self, name)
            for name in ('Order', 'OtherOrder', 'Gateway', 'Client', 'BillingClient')]
        for source, target in ((order, gateway), (other, gateway),
                               (gateway, client), (gateway, billing)):
            self.observed(diagram, source, target)
        self.contained(diagram, order, other, gateway, client, billing)
        pairs = [(source, target) for source, target, _ in diagram.edges]
        self.assertEqual(len(pairs), len(set(pairs)), 'Deduplicate diagram relationships')
        # Edge deduplication must not discard supporting invocation evidence.
        supporting = report.replace('```mermaid\n' + diagram.text + '```', '')
        for name, lines in (('Gateway', (6, 7, 8)), ('Order', (5, 6)),
                            ('OtherOrder', (4,))):
            for line in lines:
                self.assertIn(f'src/main/java/sample/{name}.java:{line}', supporting)
        self.clean_nodes(diagram, 'lookup', 'place', 'get')
        repeated, repeated_diagram = self.report()
        self.assertEqual(report, repeated)
        self.assertEqual(diagram.text, repeated_diagram.text)


if __name__ == '__main__':
    unittest.main()
