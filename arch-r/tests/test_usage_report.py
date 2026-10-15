"""Finding-level usage/evidence contracts, updated for iteration 003 coverage.

Unrelated diagnostics are now checked in optional details, not default output.
Only disposable Java source fixtures are analyzed; no Java is compiled or run.
Assertions cover report semantics and citations, not a proposed internal API,
exact prose, adapter advice, or the later diagram/limitations tasks.
"""
from pathlib import Path
import html
import re
import subprocess
import tempfile
import unittest


ENTRY_POINT = Path(__file__).resolve().parents[1] / 'arch-r'


def unused_claims(text):
    """Ignore explicit denials of an unused verdict, not affirmative verdicts."""
    text = re.sub(
        r'\b(?:does not|doesn\x27t|cannot|can\x27t)\s+'
        r'(?:establish|prove|mean|imply|show)\s+that\s+'
        r'(?:the\s+)?(?:Feign\s+)?client\s+(?:is|was|remains)\s+unused\b',
        '', text, flags=re.I)
    return re.findall(r'\b(?:is|was|remains)\s+unused\b', text, flags=re.I)


class UnusedClaimAssertionTests(unittest.TestCase):
    def test_explicit_denials_are_not_unused_verdicts(self):
        for text in (
            'This does not establish that the client is unused.',
            'This does not prove that the client is unused.',
            'The client is not unused.',
        ):
            with self.subTest(text=text):
                self.assertEqual(unused_claims(text), [])

    def test_affirmative_verdicts_are_rejected_even_after_a_denial(self):
        for text in (
            'The client is unused.',
            'The client was unused.',
            'The client remains unused.',
            'This does not establish that the client is unused. '
            'Nevertheless, the client is unused.',
        ):
            with self.subTest(text=text):
                self.assertTrue(unused_claims(text))


class UsageReportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='arch_r_usage_')
        self.addCleanup(temp.cleanup)
        self.caller = Path(temp.name)
        self.module = self.caller / 'orders'
        (self.module / 'src/main/java').mkdir(parents=True)
        self.client()

    def put(self, name, source):
        path = self.module / 'src/main/java/sample' / (name + '.java')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')

    def client(self, url='${product.url}'):
        self.put('Client', f'''package sample;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
@FeignClient(name="products", url="{url}")
public interface Client {{
    @GetMapping("/products/{{id}}")
    String get(String id);
}}
''')

    def report(self, details=False):
        before = {p.relative_to(self.module): p.read_bytes()
                  for p in self.module.rglob('*') if p.is_file()}
        result = subprocess.run([str(ENTRY_POINT), 'analyze', str(self.module)]
                                + (['--show-analysis-limitations'] if details else []),
                                cwd=self.caller, capture_output=True, text=True,
                                timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertEqual(before, {p.relative_to(self.module): p.read_bytes()
                                 for p in self.module.rglob('*') if p.is_file()})
        return (self.caller / 'arch-r-report-orders.md').read_text(encoding='utf-8')

    def finding(self, report, system='products'):
        from tests.report_sections import finding
        return finding(report, system)

    def module_diagnostics(self, report):
        # Optional coverage is module-wide; its heading is not prescribed.
        from tests.report_sections import section
        return section(report, 'Limitations')

    def extra_clients(self):
        for name, system in (('BillingClient', 'billing'), ('StockClient', 'stock')):
            self.put(name, f'''package sample;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
@FeignClient(name="{system}", url="https://{system}.example")
public interface {name} {{
    @GetMapping("/items")
    String get(String id);
}}
''')

    def usage_and_evidence(self, report):
        return self.finding(report)

    def citations(self, text, name, *lines):
        # Verbose receiver/target citations moved out of the report; the
        # underlying resolution evidence must still retain their locations.
        from tests.analysis_evidence import locations
        retained = locations(self.module)
        for line in lines:
            self.assertIn(f'src/main/java/sample/{name}.java:{line}', retained)

    def chain(self, text, *names):
        # Ignore Markdown emphasis/code spans and accept common arrow spellings.
        plain = html.unescape(text).replace('`', '').replace('*', '')
        arrow = r'\s*(?:→|->|-->)\s*'
        pattern = arrow.join(r'(?:sample\.)?' + re.escape(name) + r'(?:\.\w+)?' for name in names)
        self.assertRegex(plain, pattern)

    def direct(self):
        self.put('Order', '''package sample;
class Order {
    final Client client;
    Order(Client client) { this.client = client; }
    void place(String id) { this.client.get(id); }
}
''')

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

    def test_direct_call_has_receiver_and_call_evidence_despite_unresolved_url(self):
        self.direct()
        report = self.report()
        text = self.usage_and_evidence(report)
        for name in ('Order', 'Client'):
            self.assertIn(name, text)
        self.chain(text, 'Order', 'Client')
        self.assertRegex(text.lower(), r'direct')
        self.assertRegex(text.lower(), r'observed')
        self.citations(text, 'Order', 3, 5)
        self.citations(text, 'Client', 7)
        self.assertIn('do not prove runtime wiring, execution', report)
        finding = self.finding(report)
        self.assertIn('${product.url}', finding)
        self.assertIn('destination unresolved', finding)
        self.assertIn('Lower confidence', finding)
        self.assertIn('GET /products/{id}', finding)

    def test_two_steps_explain_intermediary_and_boundary_with_all_link_evidence(self):
        self.gateway()
        self.order()
        self.put('Checkout', '''package sample;
class Checkout {
    Order order;
    void checkout(String id) { order.place(id); }
}
''')
        text = self.usage_and_evidence(self.report())
        for name in ('Order', 'Gateway', 'Client'):
            self.assertIn(name, text)
        self.chain(text, 'Order', 'Gateway', 'Client')
        self.assertIn('Gateway.lookup', text)
        self.citations(text, 'Order', 3, 4)
        self.citations(text, 'Gateway', 3, 4)
        self.citations(text, 'Client', 7)
        self.assertNotIn('Checkout', text)
        self.assertIn('2 call steps', self.report())
        self.assertRegex(text.lower(), r'(boundary|limit)')
        self.assertRegex(text.lower(), r'(may|might|could).*continu')

    def test_unrelated_method_does_not_become_upstream_usage(self):
        self.gateway()
        self.order('health')
        text = self.usage_and_evidence(self.report())
        self.assertIn('Gateway', text)
        self.chain(text, 'Gateway', 'Client')
        self.citations(text, 'Gateway', 3, 4)
        self.assertNotIn('Order', text)
        self.assertNotIn('sample/Order.java:4', text)

    def interface_route(self, second=False):
        self.put('Port', '''package sample;
public interface Port {
    String lookup(String id);
}
''')
        for name in (('HttpGateway', 'OtherGateway') if second else ('HttpGateway',)):
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

    def test_unique_interface_wiring_is_possible_even_with_literal_destination(self):
        self.client('https://products.example')
        self.interface_route()
        report = self.report()
        text = self.usage_and_evidence(report)
        for name in ('Order', 'Port', 'HttpGateway', 'Client'):
            self.assertIn(name, text)
        self.assertRegex(text.lower(), r'possible (connection|chain)')
        self.assertIn('runtime wiring', report)
        self.citations(text, 'Order', 3, 4)
        self.citations(text, 'Port', 3)
        self.citations(text, 'HttpGateway', 2, 3, 4)
        self.assertIn('High confidence', self.finding(report))
        self.assertIn('https://products.example', self.finding(report))

    def test_multiple_implementations_name_candidates_and_report_ambiguity(self):
        self.interface_route(second=True)
        text = self.usage_and_evidence(self.report())
        self.assertRegex(text.lower(), r'ambigu|multiple implementation')
        for name in ('HttpGateway', 'OtherGateway'):
            self.assertIn(name, text)
            self.citations(text, name, 2, 4)
        self.citations(text, 'Order', 4)
        self.assertRegex(text.lower(), r'(not|no|cannot|can.t|unresolved|unverified).*(select|choos|resolv|confirm|wir)|ambiguous')

    def test_missing_interface_implementation_is_boundary_qualified_and_evidenced(self):
        self.put('Port', '''package sample;
public interface Port {
    String lookup(String id);
}
''')
        self.put('Order', '''package sample;
class Order {
    Port port;
    void place(String id) { port.lookup(id); }
}
''')
        report = self.report(details=True)
        finding = self.usage_and_evidence(report)
        self.assertRegex(finding.lower(), r'no.*caller.*found|no.*supported.*call')
        self.assertRegex(finding.lower(), r'(within|supported|boundary|analy)')
        self.assertNotIn('Order', finding)
        self.assertNotIn('Port', finding)
        text = self.module_diagnostics(report)
        self.assertRegex(text.lower(), r'no.*implementation.*(found|visible)|'
                         r'implementation.*not.*found')
        self.assertRegex(text.lower(), r'(within|boundary|analyzed module|local)')
        self.citations(text, 'Order', 4)
        self.assertIn('lookup', text)
        self.assertNotRegex(html.unescape(text), r'Order\s*(?:→|->|-->)')

    def test_three_clients_share_unrelated_diagnostics_once_with_stable_output(self):
        self.extra_clients()
        self.put('MissingPort', '''package sample;
public interface MissingPort {
    String lookup(String id);
}
''')
        self.put('AmbiguousPort', '''package sample;
public interface AmbiguousPort {
    String lookup(String id);
}
''')
        for name in ('FirstLocal', 'SecondLocal'):
            self.put(name, f'''package sample;
class {name} implements AmbiguousPort {{
    public String lookup(String id) {{ return id; }}
}}
''')
        self.put('Unrelated', '''package sample;
class Unrelated {
    MissingPort missing;
    AmbiguousPort ambiguous;
    OutsideModule outside;
    void work(String id) {
        missing.lookup(id);
        ambiguous.lookup(id);
        outside.fetch(id);
    }
}
''')
        default = self.report()
        for line in (7, 8, 9):
            self.assertNotIn(f'src/main/java/sample/Unrelated.java:{line}', default)
        first = self.report(details=True)
        for system in ('products', 'billing', 'stock'):
            self.assertEqual(self.finding(default, system), self.finding(first, system))
        context = self.module_diagnostics(first)
        for line in (7, 8, 9):
            citation = f'src/main/java/sample/Unrelated.java:{line}'
            self.assertEqual(first.count(citation), 1, first)
            self.assertIn(citation, context)
        self.assertIn('lookup', context)
        self.assertIn('fetch', context)
        self.assertRegex(context.lower(), r'no.*implementation.*(found|visible)|'
                         r'implementation.*not.*found')
        self.assertRegex(context.lower(), r'(within|boundary|analyzed module|local)')
        self.assertRegex(context.lower(), r'ambigu|multiple implementation')
        self.assertIn('OutsideModule', context)
        for system in ('products', 'billing', 'stock'):
            finding = self.finding(first, system)
            self.assertRegex(finding.lower(), r'no.*caller.*found|no.*supported.*call')
            for name in ('Unrelated', 'MissingPort', 'AmbiguousPort',
                         'FirstLocal', 'SecondLocal', 'OutsideModule'):
                self.assertNotIn(name, finding)
        self.assertEqual(first.encode('utf-8'), self.report(details=True).encode('utf-8'))

    def test_three_clients_keep_relevant_interface_and_overload_uncertainty_scoped(self):
        self.extra_clients()
        self.interface_route(second=True)
        self.put('BillingGateway', '''package sample;
class BillingGateway {
    BillingClient client;
    String lookup(String id) { return client.get(id); }
    String lookup(Integer id) { return client.get("fallback"); }
}
''')
        self.put('BillingOrder', '''package sample;
class BillingOrder {
    BillingGateway gateway;
    void place(String id) { gateway.lookup(id); }
}
''')
        # Same class, different method: relevance must not be inferred from a name.
        self.put('HttpGateway', '''package sample;
class HttpGateway implements Port {
    Client client;
    OutsideModule outside;
    public String lookup(String id) { return client.get(id); }
    void health() { outside.fetch(); }
}
''')
        default = self.report()
        self.assertNotIn('src/main/java/sample/HttpGateway.java:6', default)
        first = self.report(details=True)
        for system in ('products', 'billing', 'stock'):
            self.assertEqual(self.finding(default, system), self.finding(first, system))
        product = self.finding(first, 'products')
        billing = self.finding(first, 'billing')
        stock = self.finding(first, 'stock')
        context = self.module_diagnostics(first)
        self.assertRegex(product.lower(), r'ambigu|multiple implementation')
        self.citations(product, 'Order', 3, 4)
        self.citations(product, 'Port', 3)
        self.citations(product, 'HttpGateway', 2, 5)
        self.citations(product, 'OtherGateway', 2, 4)
        self.assertNotRegex(html.unescape(product), r'Order\s*(?:→|->|-->)')
        self.assertRegex(billing.lower(), r'ambigu')
        self.citations(billing, 'BillingOrder', 4)
        self.citations(billing, 'BillingGateway', 4, 5)
        self.assertNotRegex(html.unescape(billing), r'BillingOrder\s*(?:→|->|-->)')
        for section in (billing, stock):
            self.assertNotIn('sample/Order.java:4', section)
            self.assertNotIn('OtherGateway', section)
        for section in (product, stock):
            self.assertNotIn('BillingOrder', section)
            self.assertNotIn('BillingGateway', section)
        citation = 'src/main/java/sample/HttpGateway.java:6'
        self.assertEqual(first.count(citation), 1, first)
        self.assertIn(citation, context)
        self.assertIn('OutsideModule', context)
        for section in (product, billing, stock):
            self.assertNotIn(citation, section)
            self.assertNotIn('OutsideModule', section)
        self.assertEqual(first.encode('utf-8'), self.report(details=True).encode('utf-8'))

    def test_shared_overload_uncertainty_stays_in_each_affected_finding(self):
        self.extra_clients()
        self.put('SharedGateway', '''package sample;
class SharedGateway {
    Client products;
    BillingClient billing;
    String lookup(String id) {
        products.get(id);
        return billing.get(id);
    }
    String lookup(Integer id) {
        products.get("fallback");
        return billing.get("fallback");
    }
    OutsideModule missing;
    void health() { missing.fetch(); }
}
''')
        self.put('Order', '''package sample;
class Order {
    SharedGateway gateway;
    void place(String id) { gateway.lookup(id); }
}
''')
        default = self.report()
        self.assertNotIn('src/main/java/sample/SharedGateway.java:14', default)
        first = self.report(details=True)
        for system in ('products', 'billing', 'stock'):
            self.assertEqual(self.finding(default, system), self.finding(first, system))
        context = self.module_diagnostics(first)
        for system in ('products', 'billing'):
            finding = self.finding(first, system)
            self.assertRegex(finding.lower(), r'ambigu')
            self.citations(finding, 'Order', 4)
            self.citations(finding, 'SharedGateway', 5, 9)
            self.assertNotRegex(html.unescape(finding), r'Order\s*(?:→|->|-->)')
            self.assertNotIn('sample/SharedGateway.java:14', finding)
        stock = self.finding(first, 'stock')
        self.assertNotIn('sample/Order.java:4', stock)
        self.assertNotIn('sample/SharedGateway.java:5', stock)
        self.assertNotIn('sample/SharedGateway.java:9', stock)
        # Relevant ambiguity remains beside both affected findings; optional
        # coverage also counts and lists that recorded invocation once.
        self.assertEqual(context.count('src/main/java/sample/Order.java:4'), 1)
        self.assertEqual(first.count('src/main/java/sample/SharedGateway.java:14'), 1)
        self.citations(context, 'SharedGateway', 14)
        self.assertEqual(first.encode('utf-8'), self.report(details=True).encode('utf-8'))

    def test_shared_interface_ambiguity_keeps_each_clients_observed_methods_separate(self):
        self.extra_clients()
        self.interface_route(second=True)
        # One candidate reaches products only through health(), not the invoked lookup().
        self.put('OtherGateway', '''package sample;
class OtherGateway implements Port {
    StockClient stock;
    Client products;
    public String lookup(String id) { return stock.get(id); }
    String health(String id) { return products.get(id); }
}
''')
        first = self.report()
        product = self.finding(first, 'products')
        stock = self.finding(first, 'stock')
        billing = self.finding(first, 'billing')
        for section in (product, stock):
            self.assertRegex(section.lower(), r'ambigu|multiple implementation')
            self.citations(section, 'Order', 4)
            self.citations(section, 'Port', 3)
            self.citations(section, 'HttpGateway', 2)
            self.citations(section, 'OtherGateway', 2)
            self.assertNotRegex(html.unescape(section), r'Order\s*(?:→|->|-->)')
        self.citations(product, 'OtherGateway', 6)
        self.assertNotIn('sample/OtherGateway.java:6', stock)
        self.assertNotIn('sample/Order.java:4', billing)
        self.assertNotIn('Port', billing)
        self.assertNotIn('## Module-wide unresolved connections', first)
        self.assertEqual(first.encode('utf-8'), self.report().encode('utf-8'))

    def test_declarations_alone_retain_dependency_without_claiming_unused(self):
        self.put('Holder', '''package sample;
class Holder {
    Client client;
    Holder(Client client) { this.client = client; }
}
''')
        report = self.report()
        text = self.usage_and_evidence(report)
        self.assertRegex(text.lower(), r'no.*caller.*found|no.*supported.*call')
        self.assertRegex(text.lower(), r'(within|supported|boundary|analy)')
        self.assertEqual(unused_claims(text), [], text)
        self.assertIn('products', self.finding(report))
        self.assertIn('GET /products/{id}', self.finding(report))

    def test_ambiguous_overload_is_evidenced_not_silently_absent(self):
        self.gateway()
        self.put('Gateway', '''package sample;
class Gateway {
    Client client;
    String lookup(String id) { return client.get(id); }
    String lookup(Integer id) { return client.get("x"); }
}
''')
        self.order()
        text = self.usage_and_evidence(self.report())
        self.assertRegex(text.lower(), r'ambigu')
        self.citations(text, 'Order', 4)
        self.citations(text, 'Gateway', 4, 5)

    def test_cycle_and_repeated_call_sites_keep_evidence_and_stable_output(self):
        self.put('Order', '''package sample;
class Order {
    Client client;
    Order other;
    void place(String id) {
        client.get(id);
        client.get("backup");
        other.place(id);
    }
}
''')
        first = self.report()
        text = self.usage_and_evidence(first)
        self.citations(text, 'Order', 3, 6, 7, 8)
        self.assertRegex(text.lower(), r'cycle')
        self.assertRegex(text.lower(), r'(stop|cut|limit|repeat)')
        self.assertEqual(first.encode('utf-8'), self.report().encode('utf-8'))


if __name__ == '__main__':
    unittest.main()
