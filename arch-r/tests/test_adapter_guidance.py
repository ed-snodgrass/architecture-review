"""Guidance regression contracts, adapted to iteration 005's review-only scope."""
import html
import re
import unittest
from tests import test_usage_report as fixtures


class AdapterGuidanceTests(unittest.TestCase):
    setUp = fixtures.UsageReportTests.setUp
    put = fixtures.UsageReportTests.put
    client = fixtures.UsageReportTests.client
    report = fixtures.UsageReportTests.report
    finding = fixtures.UsageReportTests.finding
    direct = fixtures.UsageReportTests.direct
    gateway = fixtures.UsageReportTests.gateway
    order = fixtures.UsageReportTests.order
    interface_route = fixtures.UsageReportTests.interface_route
    extra_clients = fixtures.UsageReportTests.extra_clients

    def guidance(self, report, system='products'):
        finding = self.finding(report, system)
        return html.unescape(finding.split('#### Review conditions', 1)[1]
                             .split('#### Declaration', 1)[0]).replace('`', '').replace('*', '')

    def suggestion(self, text):
        self.assertRegex(text.lower(), r'\b(?:inspect|review|check)\b')
        self.assertRegex(text.lower(), r'\b(?:if|whether)\b')
        self.assertIn('ArchR did not establish this behavior', text)
        self.assertNotRegex(text.lower(), r'\b(?:adapter|port)\s+is\s+(?:missing|required|necessary)\b')
        self.assertNotRegex(text.lower(), r'\b(?:must|required to)\s+(?:add|introduce|create|extract)\b')
        self.assertNotIn('domain-facing', text)

    def assert_definitions_once(self, report):
        self.assertEqual(report.count('An adapter is code that keeps'), 1)
        self.assertIn("separate from the module's own work", report)
        self.assertNotIn('domain-facing', report)

    def test_direct_use_reviews_business_decisions_without_asserting_them(self):
        self.direct()
        text = self.guidance(self.report())
        self.suggestion(text)
        self.assertIn('Order.place', text)
        self.assertIn('Client.get', text)
        self.assertIn('decides what the module should do', text)
        self.assertNotRegex(text, r'Order\s+(?:contains|handles|implements|has)\s+business')

    def test_intermediary_is_reviewed_not_given_an_adequacy_verdict(self):
        self.gateway()
        self.order()
        report = self.report()
        text = self.guidance(report)
        self.suggestion(text)
        self.assertIn('Gateway.lookup', text)
        self.assertIn('Order.place → sample.Gateway.lookup', self.finding(report))
        self.assertIn('HTTP status codes', text)
        self.assertIn('translates external fields', text)
        self.assertNotRegex(text, r'Gateway\s+(?:is|provides)\s+(?:an?\s+)?(?:adequate|sufficient|proper)')

    def test_unique_interface_guidance_is_conditional_and_requests_wiring_verification(self):
        self.client('https://products.example')
        self.interface_route()
        report = self.report()
        text = self.guidance(report)
        self.suggestion(text)
        self.assertIn('HttpGateway.lookup', text)
        self.assertIn('possible, not confirmed', text)
        self.assertRegex(text.lower(), r'if.*connection.*verified')
        self.assertIn('verify that runtime wiring connects sample.Port to sample.HttpGateway', text)
        for name in ('Order', 'Port', 'HttpGateway'):
            self.assertIn(name, self.finding(report))
        self.assertNotRegex(text, r'Order\s+(?:is wired to|uses at runtime)\s+HttpGateway')

    def test_unrelated_upstream_method_does_not_drive_review(self):
        self.gateway()
        self.order('health')
        text = self.guidance(self.report())
        self.suggestion(text)
        self.assertIn('Gateway.lookup', text)
        self.assertNotIn('Order', text)

    def test_declarations_only_have_no_recommendation_or_unused_verdict(self):
        self.put('Holder', '''package sample;
class Holder { Client client; Holder(Client client) { this.client = client; } }
''')
        report = self.report()
        text = self.guidance(report)
        self.assertIn('No supported caller was found within the analysis boundary', text)
        self.assertIn('cannot identify code to review', text)
        self.assertNotIn('```java', text)
        self.assertNotIn('Holder', text)
        self.assertEqual(fixtures.unused_claims(self.finding(report)), [])
        self.assertIn('GET /products/{id}', self.finding(report))
        self.assertIn('${product.url}', self.finding(report))

    def test_multiple_findings_explain_terminology_once_and_scope_advice(self):
        self.direct()
        self.extra_clients()
        self.put('BillingCaller', '''package sample;
class BillingCaller { BillingClient billing;
 String charge(String id) { return billing.get(id); } }
''')
        report = self.report()
        product = self.guidance(report, 'products')
        billing = self.guidance(report, 'billing')
        stock = self.guidance(report, 'stock')
        self.suggestion(product)
        self.suggestion(billing)
        self.assertIn('Order.place', product)
        self.assertNotIn('BillingCaller', product)
        self.assertIn('BillingCaller.charge', billing)
        self.assertNotIn('Order', billing)
        self.assertNotIn('Order', stock)
        self.assertNotIn('BillingCaller', stock)
        self.assert_definitions_once(report)
        self.assertEqual(report.encode(), self.report().encode())
