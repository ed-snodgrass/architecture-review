"""Conditional educational guidance, without prescribing adapter shape."""
import unittest

from tests import test_brief_finding_cards as fixtures


class ReviewGuidanceTests(unittest.TestCase):
    report = fixtures.BriefFindingCardTests.report

    def guidance(self, source):
        return self.report(source).split('## Adapter Review Guidance\n', 1)[1].split(
            '\n## Findings with Evidence', 1)[0]

    def assert_examples(self, text):
        self.assertEqual(text.count('```java'), 3)
        self.assertEqual(text.count('if your code looks like this'), 3)
        self.assertEqual(text.count('ArchR did not establish this behavior'), 3)
        self.assertNotRegex(text, r'domain-facing interface|candidate adapter location|wrapper|refactor')
        self.assertIn('same method both communicates', text)

    def test_http_conditions_have_separate_hypothetical_examples(self):
        text = self.guidance('''package shop;
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient("products") interface Client { String get(); }
class Service { Client client; String resolveItem() { return client.get(); } }
class Controller { Service service; String run() { return service.resolveItem(); } }
''')
        self.assert_examples(text)
        self.assertIn('shop.Service.resolveItem', text)
        self.assertIn('shop.Client.get', text)
        self.assertIn('external fields, statuses, or representations', text)
        self.assertIn('HTTP status codes', text)
        self.assertIn('timeouts', text)

    def test_database_conditions_do_not_borrow_http_examples(self):
        for declaration, invocation in [
            ('interface Orders extends JpaRepository<Order, Long> {}', 'orders.save(order)'),
            ('', 'orders.update("DELETE FROM orders")'),
        ]:
            field = 'Orders' if declaration else 'JdbcTemplate'
            text = self.guidance(f'''package shop;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.jdbc.core.JdbcTemplate;
{declaration}
class Service {{ {field} orders; void store(Order order) {{ {invocation}; }} }}
''')
            self.assert_examples(text)
            self.assertIn('shop.Service.store', text)
            self.assertIn('SQL errors', text)
            self.assertIn('persistence-library', text)
            self.assertNotRegex(text, r'HTTP|httpStatus|client response')

    def test_no_caller_or_unresolved_caller_does_not_invent_examples(self):
        for caller in ['', '''class Service { Client client;
String run() { return client.get(null); } }''']:
            text = self.guidance('''
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient("products") interface Client { String get(String id); String get(Long id); }
''' + caller)
            self.assertIn('ArchR cannot identify code to review', text)
            self.assertNotIn('```java', text)
            self.assertNotIn('Review Service.run', text)
            if caller:
                self.assertIn('connection is unresolved', text)

    def test_possible_interface_route_stays_conditional(self):
        text = self.guidance('''package shop;
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient("products") interface Client { String get(); }
interface Gateway { String fetch(); }
class HttpGateway implements Gateway {
 Client client; public String fetch() { return client.get(); }
}
class Service { Gateway gateway; String run() { return gateway.fetch(); } }
''')
        self.assertIn('possible, not confirmed', text)
        self.assertIn('First verify that runtime wiring connects shop.Gateway to shop.HttpGateway', text)
        self.assertIn('shop.HttpGateway.fetch', text)
        self.assertNotIn('candidate adapter', text)


if __name__ == '__main__':
    unittest.main()
