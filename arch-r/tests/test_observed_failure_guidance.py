"""Observed failure guidance replaces only the matching conditional example."""
import unittest

from tests import test_usage_report as fixtures


class ObservedFailureGuidanceTests(unittest.TestCase):
    setUp = fixtures.UsageReportTests.setUp
    put = fixtures.UsageReportTests.put
    client = fixtures.UsageReportTests.client
    report = fixtures.UsageReportTests.report

    def failure_sections(self, report):
        guidance = report.split('## Adapter Review Guidance', 1)[1].split(
            '## Findings with Evidence', 1)[0]
        return [part.split('**Mixing integration details', 1)[0]
                for part in guidance.split('**Handling integration-specific failures**')[1:]]

    def test_imported_and_qualified_observations_with_citations_in_both_modes(self):
        for exception, imports in (
            ('FeignException', 'import feign.FeignException;'),
            ('feign.FeignException', ''),
        ):
            with self.subTest(exception=exception):
                self.put('Order', f'''package sample;
{imports}
class Order {{
    Client client;
    String place(String id) {{
        try {{
            return client.get(id);
        }} catch ({exception} failure) {{ return "unknown"; }}
    }}
}}
''')
                report = self.report()
                self.assertIn('distinguishes observed source structure', report)
                self.assertIn('ArchR observed the Feign-specific catch structure', report)
                self.assertIn('remaining review conditions are conditional', report)
                self.assertNotIn('that any of them occurs', report)
                self.assertNotIn('not observed behavior', report)
                sections = self.failure_sections(report)
                self.assertEqual(len(sections), 1)
                section = sections[0]
                for text in ('sample.Order.place calls sample.Client.get',
                             'feign.FeignException catch',
                             'Call: src/main/java/sample/Order.java:7',
                             'catch: src/main/java/sample/Order.java:8',
                             'application-level failure',
                             'without depending on Feign exception types',
                             'application contract', 'may already serve as that adapter',
                             'before adding another layer'):
                    self.assertIn(text, section)
                for text in ('Illustrative only', '```java', '503', 'retry',
                             'product unavailable', 'adapter is required'):
                    self.assertNotIn(text, section)
                self.assertEqual(sections, self.failure_sections(self.report(details=True)))
                self.assertEqual(report, self.report())

    def test_distinct_calls_retained_but_upstream_routes_do_not_repeat_them(self):
        self.put('Order', '''package sample;
class Order {
    Client client;
    void place(String id) {
        try { client.get(id); } catch (feign.FeignException e) {}
        try { client.get(id); } catch (feign.FeignException e) {}
    }
}
''')
        self.put('Entry', '''package sample;
class Entry {
    Order order;
    void first() { order.place("a"); }
    void second() { order.place("b"); }
}
''')
        sections = self.failure_sections(self.report())
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].count('sample.Order.place calls sample.Client.get'), 2)
        self.assertIn('Order.java:5', sections[0])
        self.assertIn('Order.java:6', sections[0])

    def test_observations_stay_with_the_correct_integration_and_operation(self):
        self.put('Billing', '''package sample;
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient(name="billing") interface Billing { String charge(String id); }
''')
        self.put('Order', '''package sample;
class Order {
    Client client;
    Billing billing;
    void place(String id) {
        try { client.get(id); } catch (feign.FeignException e) {}
        billing.charge(id);
    }
    void pay(String id) {
        try { billing.charge(id); } catch (feign.FeignException e) {}
        client.get(id);
    }
}
''')
        report = self.report()
        sections = self.failure_sections(report)
        observed = [section for section in sections if 'inside a try' in section]
        self.assertEqual(len(observed), 2)
        product, = [s for s in observed if 'sample.Client.get' in s]
        billing, = [s for s in observed if 'sample.Billing.charge' in s]
        self.assertIn('sample.Order.place calls sample.Client.get', product)
        self.assertIn('Order.java:6', product)
        self.assertNotIn('sample.Order.pay calls', product)
        self.assertNotIn('sample.Billing', product)
        self.assertIn('sample.Order.pay calls sample.Billing.charge', billing)
        self.assertIn('Order.java:10', billing)
        self.assertNotIn('sample.Order.place calls', billing)
        self.assertNotIn('sample.Client', billing)
        self.assertEqual(len([s for s in sections if 'Illustrative only' in s]), 2)
        guidance = report.split('## Adapter Review Guidance', 1)[1].split(
            '## Findings with Evidence', 1)[0]
        for title, statement, other in (
            ('Billing', 'sample.Order.pay calls sample.Billing.charge',
             'sample.Order.place calls sample.Client.get'),
            ('Client', 'sample.Order.place calls sample.Client.get',
             'sample.Order.pay calls sample.Billing.charge'),
        ):
            matching, = [part for part in guidance.split('### Finding ')[1:]
                         if part.splitlines()[0].endswith(': ' + title)]
            self.assertIn(statement, matching)
            self.assertNotIn(other, matching)
        self.assertEqual(sections, self.failure_sections(self.report(details=True)))

    def test_no_match_keeps_conditional_failure_example(self):
        self.put('Order', '''package sample;
class Order {
    Client client;
    void place(String id) { client.get(id); }
}
''')
        report = self.report()
        self.assertIn('ArchR has not established that any of them occurs', report)
        self.assertNotIn('ArchR observed the Feign-specific catch structure', report)
        self.assertNotIn('failure handling is absent', report)
        section, = self.failure_sections(report)
        self.assertIn('Check whether', section)
        self.assertIn('Illustrative only', section)
        self.assertNotIn('inside a try', section)

    def test_observation_intro_is_scoped_to_matching_caller(self):
        self.put('Order', '''package sample;
class Order {
    Client client;
    void place(String id) {
        try { client.get(id); } catch (feign.FeignException e) {}
    }
    void other(String id) { client.get(id); }
}
''')
        report = self.report()
        self.assertEqual(report.count('ArchR observed the Feign-specific catch structure'), 1)
        self.assertEqual(report.count('ArchR has not established that any of them occurs'), 1)
        self.assertEqual(self.failure_sections(report),
                         self.failure_sections(self.report(details=True)))

    def test_missing_caller_keeps_scoped_no_recommendation(self):
        report = self.report()
        self.assertIn('No supported caller was found within the analysis boundary', report)
        self.assertIn('no recommendation or example is provided', report)
        self.assertNotIn('ArchR observed the Feign-specific catch structure', report)
        self.assertEqual(self.failure_sections(report), [])


if __name__ == '__main__':
    unittest.main()
