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

    def test_no_match_keeps_conditional_failure_example(self):
        self.put('Order', '''package sample;
class Order {
    Client client;
    void place(String id) { client.get(id); }
}
''')
        section, = self.failure_sections(self.report())
        self.assertIn('Check whether', section)
        self.assertIn('Illustrative only', section)
        self.assertNotIn('inside a try', section)


if __name__ == '__main__':
    unittest.main()
