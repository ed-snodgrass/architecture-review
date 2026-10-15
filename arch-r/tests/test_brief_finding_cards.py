"""Iteration 005 compact cards; supporting analysis remains unchanged."""
from pathlib import Path
import re
import tempfile
import unittest

from archr.discovery import discover_clients, extract_clients
from archr.findings import discover_findings
from archr.module import Module, load_module
from archr.report import render_report
from archr.traversal import trace_usage


class BriefFindingCardTests(unittest.TestCase):
    def report(self, source):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            java = root / 'src/main/java/Example.java'
            java.parent.mkdir(parents=True)
            java.write_text(source)
            module = load_module(root)
            return render_report(module, discover_clients(module), trace_usage(module),
                                 findings=discover_findings(module))

    def cards(self, report):
        brief = report.split('## Findings\n', 1)[1].split('\n## ', 1)[0]
        return [part for part in re.split(r'\n(?=### Finding )', brief) if part.strip()]

    def test_uniform_order_identity_links_and_no_supporting_detail(self):
        report = self.report('''package shop;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.data.jpa.repository.JpaRepository;
@FeignClient(name="product-service", url="${product-service.url}")
interface ProductServiceClient { @GetMapping("/products") String getProduct(); }
interface OrderRepository extends JpaRepository<Order, Long> {}
class OrderService {
 ProductServiceClient client;
 String resolveItem() { return client.getProduct(); }
}
''')
        cards = self.cards(report)
        self.assertEqual(len(cards), 2)
        for number, card in enumerate(cards, 1):
            self.assertEqual(re.findall(r'\*\*([^*]+):\*\*', card), [
                'Destination', 'Status', 'External system', 'Mechanism',
                'Adapter Recommendation'])
            for kind in ('guidance', 'evidence'):
                self.assertIn(f'](#finding-{number}-{kind})', card)
                self.assertEqual(report.count(f'<a id="finding-{number}-{kind}"></a>'), 1)
            for forbidden in ('src/main/java', 'Confidence', '→', 'GET /products',
                              'runtime', 'call steps', 'Declaration evidence'):
                self.assertNotIn(forbidden, card)
        self.assertIn('Finding 1: ProductServiceClient', cards[0])
        self.assertIn('${product-service.url} (destination unresolved)', cards[0])
        self.assertIn('**Status:** Caller found', cards[0])
        self.assertIn('**External system:** product-service', cards[0])
        self.assertIn('**Mechanism:** OpenFeign HTTP client', cards[0])
        self.assertIn('shop.OrderService.resolveItem', cards[0])
        self.assertIn('OrderRepository', cards[1])
        self.assertIn('**Destination:** Unknown', cards[1])
        self.assertIn('**External system:** Unknown', cards[1])
        self.assertIn('**Status:** No caller found', cards[1])
        self.assertIn('No recommendation: no supported caller was found', cards[1])

    def test_relevant_unresolved_caller_is_not_absence_or_unrelated_diagnostic(self):
        report = self.report('''
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient("products") interface Client { String get(String id); String get(Long id); }
@FeignClient("other") interface Unused { String get(); }
class Service { Client client; String run() { return client.get(null); } }
''')
        cards = self.cards(report)
        self.assertIn('**Status:** Caller unresolved', cards[0])
        self.assertIn('**Status:** No caller found', cards[1])
        self.assertIn('**Destination:** Unknown', cards[0])

    def recommendation(self, card):
        return card.split('**Adapter Recommendation:** ', 1)[1].split(' [Review guidance]', 1)[0]

    def test_recommendation_names_direct_observed_method_and_conditional_review(self):
        report = self.report('''package shop;
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient("products") interface Client { String get(); }
class Gateway { Client client; String fetch() { return client.get(); } }
class Controller { Gateway gateway; String run() { return gateway.fetch(); } }
''')
        recommendation = self.recommendation(self.cards(report)[0])
        self.assertEqual(recommendation,
                         'Inspect shop.Gateway.fetch to determine whether it handles '
                         'integration-specific failures or mixes integration details '
                         'with module decisions.')
        self.assertNotIn('Controller', recommendation)
        self.assertNotRegex(recommendation, r'interface|wrapper|refactor|must|required')

    def test_repository_recommendation_uses_observed_method_without_http_assumptions(self):
        report = self.report('''package shop;
import org.springframework.data.jpa.repository.JpaRepository;
interface Orders extends JpaRepository<Order, Long> {}
class Service { Orders orders; void store(Order order) { orders.save(order); } }
''')
        recommendation = self.recommendation(self.cards(report)[0])
        self.assertIn('Inspect shop.Service.store to determine whether', recommendation)
        self.assertIn('integration-specific failures', recommendation)
        self.assertNotRegex(recommendation, r'HTTP|response|status code')

    def test_no_recommendation_explains_unresolved_or_unavailable_caller_evidence(self):
        report = self.report('''
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient("products") interface Client { String get(String id); String get(Long id); }
class Service { Client client; String run() { return client.get(null); } }
''')
        recommendation = self.recommendation(self.cards(report)[0])
        self.assertEqual(recommendation,
                         'No recommendation: the caller connection is unresolved, '
                         'so ArchR cannot identify supported caller code to inspect.')
        clients = extract_clients('''
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient("products") interface Client {}
''', 'src/main/java/Client.java')
        module = Module(Path('/module'), Path('/module/src/main/java'), 'module')
        card = self.cards(render_report(module, clients))[0]
        self.assertIn('No recommendation: no usage traversal was supplied', card)
        self.assertIn('ArchR cannot identify code to inspect.', card)

    def test_field_identity_distinguishes_same_typed_clients(self):
        report = self.report('''package shop;
class Gateway {
 org.springframework.web.client.RestTemplate first;
 org.springframework.web.client.RestTemplate second;
}
''')
        cards = self.cards(report)
        self.assertIn('Finding 1: shop.Gateway.first', cards[0])
        self.assertIn('Finding 2: shop.Gateway.second', cards[1])

    def test_duplicate_feign_names_use_qualified_identity_and_are_deterministic(self):
        clients = []
        for package in ('one', 'two'):
            clients.extend(extract_clients(f'''package {package};
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient("external") interface Client {{}}
''', f'src/main/java/{package}/Client.java'))
        module = Module(Path('/module'), Path('/module/src/main/java'), 'module')
        report = render_report(module, clients)
        cards = self.cards(report)
        self.assertIn('Finding 1: one.Client', cards[0])
        self.assertIn('Finding 2: two.Client', cards[1])
        self.assertEqual(report, render_report(module, reversed(clients)))


if __name__ == '__main__':
    unittest.main()
