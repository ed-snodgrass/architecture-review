"""End-to-end iteration 002 contracts, using only disposable Java source.

Run the public executable, not indexing/traversal APIs. Existing focused suites
cover the individual acceptance examples; these tests cover combined behavior
and cross-package/type-identity regressions at the command/report boundary.
"""
from pathlib import Path
import html
import re
import subprocess
import tempfile
import unittest

from tests.test_usage_diagram import Diagram


ENTRY_POINT = Path(__file__).resolve().parents[1] / 'arch-r'


class Iteration002AcceptanceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='arch_r_002_acceptance_')
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.module = self.work / 'orders'
        (self.module / 'src/main/java').mkdir(parents=True)
        self.output = self.work / 'arch-r-report-orders.md'

    def put(self, path, source):
        target = self.module / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding='utf-8')

    def java(self, package, name, body, imports=''):
        self.put('src/main/java/' + package.replace('.', '/') + '/' + name + '.java',
                 f'package {package};\n{imports}{body}\n')

    def client(self, package='remote', name='Client', system='products',
               url='https://products.example'):
        self.java(package, name, f'''@FeignClient(name="{system}", url="{url}")
public interface {name} {{
    @GetMapping("/items")
    String get(String id);
}}''', 'import org.springframework.cloud.openfeign.FeignClient;\n'
             'import org.springframework.web.bind.annotation.GetMapping;\n')

    def analyze(self, details=False):
        before = {str(p.relative_to(self.module)): p.read_bytes()
                  for p in self.module.rglob('*') if p.is_file()}
        args = [str(ENTRY_POINT), 'analyze', str(self.module)]
        if details:
            args.append('--show-analysis-limitations')
        result = subprocess.run(args,
                                cwd=self.work, capture_output=True, text=True,
                                timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertEqual(before, {str(p.relative_to(self.module)): p.read_bytes()
                                 for p in self.module.rglob('*') if p.is_file()})
        self.assertEqual(sorted(p.name for p in self.work.iterdir()),
                         ['arch-r-report-orders.md', 'orders'])
        report = self.output.read_text(encoding='utf-8')
        return report, Diagram(self, report)

    def stable(self, details=False):
        report, diagram = self.analyze(details=details)
        first = self.output.read_bytes()
        self.analyze(details=details)
        self.assertEqual(first, self.output.read_bytes())
        return report, diagram

    def finding(self, report, system):
        match = re.search(r'^## Finding \d+: ' + re.escape(system) + r'\s*$',
                          report, re.M)
        self.assertIsNotNone(match, report)
        return re.split(r'^## ', report[match.end():], maxsplit=1, flags=re.M)[0]

    def chain(self, text, *names):
        text = html.unescape(text).replace('`', '').replace('*', '')
        self.assertRegex(text, r'\s*(?:→|->|-->)\s*'.join(map(re.escape, names)))

    def external(self, diagram, name):
        matches = [key for key, (kind, label) in diagram.nodes.items()
                   if kind.endswith('_Ext') and label == name]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def citation(self, text, package, name, line):
        self.assertIn(f'src/main/java/{package.replace(".", "/")}/{name}.java:{line}',
                      text)

    def test_direct_calls_resolve_packages_imports_and_fully_qualified_fields(self):
        self.client(url='${product.url}')
        self.java('remote', 'SamePackage', '''class SamePackage {
    Client client;
    void work(String id) { client.get(id); }
}''')
        self.java('shop', 'Imported', '''class Imported {
    final Client client;
    Imported(Client client) { this.client = client; }
    void work(String id) { this.client.get(id); }
}''', 'import remote.Client;\n')
        self.java('shop', 'Qualified', '''class Qualified {
    remote.Client client;
    void work(String id) { client.get(id); }
}''')
        report, diagram = self.stable()
        finding = self.finding(report, 'products')
        for package, name, field, call in (
                ('remote', 'SamePackage', 3, 4),
                ('shop', 'Imported', 4, 6), ('shop', 'Qualified', 3, 4)):
            with self.subTest(caller=name):
                self.chain(finding, package + '.' + name, 'remote.Client')
                self.citation(finding, package, name, field)
                self.citation(finding, package, name, call)
                source = diagram.named(self, name)
                target = diagram.named(self, 'Client')
                labels = diagram.labels(source, target)
                self.assertEqual(len(labels), 1)
                self.assertRegex(labels[0].lower(), 'observed')
                self.assertNotRegex(labels[0].lower(), 'possible')
        self.assertIn('destination unresolved', finding)
        self.assertIn('${product.url}', finding)
        self.assertRegex(finding.lower(), r'observed.*chain')
        self.assertRegex(finding.lower(), r'suggestion.*review whether')
        self.assertRegex(finding.lower(), r'if so')

    def test_depth_and_method_matching_exclude_unrelated_and_third_step_callers(self):
        self.client()
        self.java('shop', 'Gateway', '''class Gateway {
    remote.Client client;
    String lookup(String id) { return client.get(id); }
    void health() {}
}''')
        self.java('shop', 'Order', '''class Order {
    Gateway gateway;
    void place(String id) { gateway.lookup(id); }
}''')
        self.java('shop', 'Checkout', '''class Checkout {
    Order order;
    void checkout(String id) { order.place(id); }
}''')
        self.java('shop', 'Monitor', '''class Monitor {
    Gateway gateway;
    void poll() { gateway.health(); }
}''')
        report, diagram = self.stable()
        finding = self.finding(report, 'products')
        self.chain(finding, 'shop.Order', 'shop.Gateway', 'remote.Client')
        self.citation(finding, 'shop', 'Gateway', 4)
        self.citation(finding, 'shop', 'Order', 4)
        self.assertRegex(finding.lower(), r'(boundary|limit).*')
        self.assertRegex(finding.lower(), r'(may|might|could).*continu')
        self.assertRegex(finding.lower(), r'(2|two).*call steps')
        self.assertRegex(finding.lower(), r'candidate.*adapter location')
        self.assertRegex(finding.lower(), r'review whether.*interface')
        for absent in ('Checkout', 'Monitor'):
            self.assertNotIn(absent, finding)
            self.assertNotIn(absent, diagram.text)

    def interface_fixture(self, implementations):
        self.client()
        self.java('shop', 'Port', '''public interface Port {
    String lookup(String id);
}''')
        self.java('shop', 'Order', '''class Order {
    Port port;
    void place(String id) { port.lookup(id); }
}''')
        for name in implementations:
            self.java('shop', name, f'''class {name} implements Port {{
    remote.Client client;
    public String lookup(String id) {{ return client.get(id); }}
}}''')

    def test_unique_interface_route_is_possible_with_conditional_guidance(self):
        self.interface_fixture(['HttpGateway'])
        report, diagram = self.stable()
        finding = self.finding(report, 'products')
        self.chain(finding, 'shop.Order', 'shop.HttpGateway', 'remote.Client')
        self.assertRegex(finding.lower(), r'possible chain')
        self.assertRegex(finding.lower(), r'runtime wiring.*unverified')
        self.assertIn('High confidence', finding)
        for name, lines in (('Order', (3, 4)), ('Port', (3,)),
                            ('HttpGateway', (2, 4))):
            for line in lines:
                self.citation(finding, 'shop', name, line)
        labels = diagram.labels(diagram.named(self, 'Order'),
                                diagram.named(self, 'HttpGateway'))
        self.assertEqual(len(labels), 1)
        self.assertRegex(labels[0].lower(), r'possible')
        guidance = finding.split('### Where an adapter could fit')[1]
        self.assertRegex(guidance.lower(), r'verify.*runtime wiring')
        self.assertRegex(guidance.lower(), r'if.*(confirmed|wiring)')

    def test_multiple_implementations_keep_direct_calls_but_no_upstream_route(self):
        self.interface_fixture(['HttpGateway', 'OtherGateway'])
        report, diagram = self.stable()
        finding = self.finding(report, 'products')
        self.assertRegex(finding.lower(), r'ambigu|multiple implementation')
        for name in ('HttpGateway', 'OtherGateway'):
            self.chain(finding, 'shop.' + name, 'remote.Client')
            self.citation(finding, 'shop', name, 2)
            self.citation(finding, 'shop', name, 4)
        self.citation(finding, 'shop', 'Order', 4)
        self.assertNotRegex(html.unescape(finding), r'shop.Order\s*→')
        self.assertNotIn('Order', diagram.text)

    def test_missing_implementation_and_declarations_are_not_usage(self):
        self.interface_fixture([])
        self.java('shop', 'Holder', '''class Holder {
    final remote.Client client;
    Holder(remote.Client client) { this.client = client; }
}''')
        report, diagram = self.stable()
        finding = self.finding(report, 'products')
        self.assertRegex(finding.lower(), r'no supported caller.*within')
        self.assertRegex(finding.lower(), r'no specific adapter placement')
        self.assertNotIn('Holder', diagram.text)
        self.assertNotIn('Order', diagram.text)
        self.assertNotIn('Observed source chain', finding)
        # With no implementation there is no receiver/type evidence linking
        # this Port call to the Feign client. Iteration 003 keeps this gap in
        # module-wide coverage, not the default architectural finding.
        self.assertRegex(report, r'1 call site was not traced')
        self.assertIn('--show-analysis-limitations', report)
        for name, line in (('Order', 4), ('Port', 3)):
            self.assertNotIn(f'src/main/java/shop/{name}.java:{line}', report)
        self.assertNotIn('no implementation', report.lower())
        self.assertIn('GET /items', finding)

        detailed, detailed_diagram = self.stable(details=True)
        self.assertRegex(detailed, r'1 call site was not traced')
        self.assertRegex(detailed.lower(), r'no.*implementation.*within')
        self.citation(detailed, 'shop', 'Order', 4)
        # Coverage requires the invocation location and a readable reason,
        # not a citation for every supporting type declaration.
        self.assertIn('shop.Port', detailed)
        self.assertIn('port.lookup', detailed)
        self.assertEqual(finding, self.finding(detailed, 'products'))
        self.assertEqual(diagram.text, detailed_diagram.text)
        # Returning to default removes optional evidence from the same report.
        restored, _ = self.analyze()
        self.assertEqual(report, restored)

    def test_cycles_multiple_sites_and_overloads_preserve_evidence_not_false_routes(self):
        self.client()
        self.java('shop', 'Gateway', '''class Gateway {
    remote.Client client;
    Gateway peer;
    String lookup(String id) {
        client.get(id);
        client.get("backup");
        return peer.lookup(id);
    }
    String lookup(Integer id) { return client.get("fallback"); }
}''')
        self.java('shop', 'Order', '''class Order {
    Gateway gateway;
    void work(String id) { gateway.lookup(id); }
}''')
        report, diagram = self.stable()
        finding = self.finding(report, 'products')
        self.assertRegex(finding.lower(), r'ambigu')
        for line in (5, 6, 7, 10):
            self.citation(finding, 'shop', 'Gateway', line)
        self.citation(finding, 'shop', 'Order', 4)
        self.assertNotIn('Order', diagram.text)
        gateway = diagram.named(self, 'Gateway')
        client = diagram.named(self, 'Client')
        self.assertEqual(len(diagram.labels(gateway, client)), 1)
        # A separate uniquely matchable self-cycle exercises the cycle cutoff.
        self.java('shop', 'Loop', '''class Loop {
    remote.Client client;
    Loop peer;
    void run(String id) {
        client.get(id);
        peer.run(id);
    }
}''')
        report, _ = self.stable()
        finding = self.finding(report, 'products')
        self.assertRegex(finding.lower(), r'cycle.*(stop|cut|limit)|(?:stop|cut).*cycle')
        self.citation(finding, 'shop', 'Loop', 6)

    def test_same_named_clients_have_distinct_routes_including_declaration_only_client(self):
        for package, system in (('products', 'products'), ('billing', 'billing'),
                                ('stock', 'stock')):
            self.client(package, system=system)
        self.java('shop', 'Order', '''class Order {
    products.Client products;
    billing.Client billing;
    void work(String id) {
        products.get(id);
        billing.get(id);
    }
}''')
        report, diagram = self.stable()
        order = diagram.named(self, 'Order')
        for package, call in (('products', 6), ('billing', 7)):
            finding = self.finding(report, package)
            self.chain(finding, 'shop.Order', package + '.Client')
            self.citation(finding, 'shop', 'Order', call)
            self.citation(finding, package, 'Client', 7)
            node = diagram.named(self, package + '.Client')
            external = self.external(diagram, package)
            self.assertEqual(len(diagram.labels(order, node)), 1)
            self.assertEqual(len(diagram.labels(node, external)), 1)
        stock = diagram.named(self, 'stock.Client')
        self.assertEqual(diagram.labels(order, stock), [])
        self.assertRegex(self.finding(report, 'stock').lower(), r'no supported caller')
        self.assertEqual(len([n for n in diagram.nodes.values()
                              if n[1].endswith('.Client')]), 3)

    def test_same_named_clients_are_disambiguated_without_any_supported_usage(self):
        self.client('products', system='products')
        self.client('billing', system='billing')
        report, diagram = self.stable()
        for package in ('products', 'billing'):
            self.assertRegex(self.finding(report, package).lower(), r'no supported caller')
            node = diagram.named(self, package + '.Client')
            external = self.external(diagram, package)
            self.assertEqual(len(diagram.labels(node, external)), 1)


if __name__ == '__main__':
    unittest.main()
