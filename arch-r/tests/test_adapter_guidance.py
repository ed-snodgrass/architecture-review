"""Objective report contracts for iteration 002's adapter-guidance task.

Uses the existing disposable, source-only CLI fixtures. No production changes,
Java compilation, target execution, or later diagram requirements are involved.
Assertions constrain meaning, not complete sentences or internal rendering APIs.
"""
import html
import re
import unittest

from tests import test_usage_report as fixtures


class AdapterGuidanceTests(unittest.TestCase):
    # Reuse fixture helpers, not its test methods (which would duplicate the suite).
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
        match = re.search(r'^### Where an adapter could fit:?\s*$', finding, re.M)
        self.assertIsNotNone(match, 'Missing adapter-guidance section in ' + system)
        section = re.split(r'^### ', finding[match.end():], maxsplit=1,
                           flags=re.M)[0]
        return html.unescape(section).replace('`', '').replace('*', '')

    def suggestion(self, text):
        self.assertRegex(text.lower(), r'\bsuggestion\b|\bsuggest(?:ed|ion|ing)?\b')
        self.assertRegex(text.lower(), r'\b(?:if|whether|could|may|might|consider|review)\b')
        # Reject affirmative defects/verdicts, not explicit denials of them.
        self.assertNotRegex(text.lower(),
                            r'\b(?:adapter|port|domain-facing interface)\s+'
                            r'(?:is|was)\s+(?:missing|required|necessary)\b')
        self.assertNotRegex(text.lower(),
                            r'\b(?:must|required to)\s+(?:add|introduce|create|extract)\b')

    def assert_definitions_once(self, report):
        plain = html.unescape(report).replace('`', '').replace('*', '').lower()
        # Definitions must explain both the external communication boundary and
        # the module's own work. Do not count mere mentions of "adapter".
        adapter = re.findall(
            r'[^\n.!?]*\badapter\b[^\n.!?]*(?:\bis\b|\bmeans\b|\bkeeps\b)'
            r'[^\n.!?]*', plain)
        definitions = [sentence for sentence in adapter
                       if re.search(r'communicat|http|external.service', sentence)
                       and re.search(r'separat|isolat', sentence)
                       and re.search(r'module|calling code|own work', sentence)]
        self.assertEqual(len(definitions), 1,
                         'Explain an adapter once as separating external-service '
                         'communication from the module\'s own work.\n' + report)
        # A mentioned domain-facing interface/port needs its plain-language
        # definition once, not repeated for every client finding.
        port = re.findall(
            r'[^\n.!?]*(?:domain-facing interface|domain-facing port)'
            r'[^\n.!?]*', plain)
        definitions = [sentence for sentence in port
                       if re.search(r'need|require', sentence)
                       and re.search(r'call(?:ing|er)', sentence)
                       and re.search(r'http', sentence)
                       and re.search(r'without|hid|keep.*out|not expos', sentence)]
        self.assertEqual(len(definitions), 1,
                         'Explain the domain-facing interface once in terms of '
                         'caller needs without exposed HTTP details.\n' + report)

    def test_direct_use_reviews_business_decisions_without_asserting_them(self):
        self.direct()
        text = self.guidance(self.report())
        self.suggestion(text)
        self.assertIn('Order', text)
        self.assertIn('Client', text)
        self.assertRegex(text.lower(), r'(review|consider|check|assess|examin)')
        self.assertRegex(text.lower(), r'(whether|if).*business')
        self.assertRegex(text.lower(), r'domain-facing (?:interface|port)')
        self.assertRegex(text.lower(), r'(isolat|separat|hid).*'
                         r'(http|external.service)|'
                         r'(http|external.service).*(isolat|separat|hid)')
        self.assertNotRegex(text, r'Order\s+(?:contains|handles|implements|has)\s+'
                            r'business (?:logic|decisions)')

    def test_intermediary_is_a_candidate_not_an_adequacy_verdict(self):
        self.gateway()
        self.order()
        text = self.guidance(self.report())
        self.suggestion(text)
        for name in ('Order', 'Gateway'):
            self.assertIn(name, text)
        self.assertRegex(text.lower(), r'candidate|potential|could.*adapter')
        self.assertRegex(text.lower(), r'(review|check|consider|assess|examin).*'
                         r'(interface|needs|http)')
        self.assertRegex(text.lower(), r'(call(?:er|ing).*needs|needs.*call(?:er|ing))')
        self.assertRegex(text.lower(), r'http.*(out|hid|isolat|separat)|'
                         r'(out|hid|isolat|separat).*http')
        self.assertNotRegex(text, r'Gateway\s+(?:is|provides)\s+'
                            r'(?:an?\s+)?(?:adequate|sufficient|proper)')

    def test_unique_interface_guidance_is_conditional_and_requests_wiring_verification(self):
        self.client('https://products.example')
        self.interface_route()
        text = self.guidance(self.report())
        self.suggestion(text)
        for name in ('Order', 'Port', 'HttpGateway'):
            self.assertIn(name, text)
        self.assertRegex(text.lower(), r'(if|conditional|assuming|subject to).*'
                         r'(wir|implementation|connect)|'
                         r'(wir|implementation|connect).*(if|conditional|assuming|subject to)')
        self.assertRegex(text.lower(), r'(verify|confirm|check).*'
                         r'(wir|implementation|runtime|inject)|'
                         r'(wir|implementation|runtime|inject).*(verify|confirm|check)')
        self.assertNotRegex(text, r'Order\s+(?:is wired to|uses at runtime)\s+HttpGateway')

    def test_unrelated_upstream_method_does_not_drive_adapter_placement(self):
        self.gateway()
        self.order('health')
        text = self.guidance(self.report())
        self.suggestion(text)
        self.assertIn('Gateway', text)
        self.assertNotIn('Order', text)
        # Gateway is the directly observed caller here, not an intermediary
        # on an invented Order -> Gateway -> Client chain.
        self.assertRegex(text.lower(), r'(whether|if).*business')

    def test_declarations_only_have_no_specific_placement_or_unused_verdict(self):
        self.put('Holder', '''package sample;
class Holder {
    Client client;
    Holder(Client client) { this.client = client; }
}
''')
        report = self.report()
        text = self.guidance(report)
        self.assertRegex(text.lower(), r'no.*(?:supported.*caller|caller.*found|supported.*call)')
        self.assertRegex(text.lower(), r'within|supported analysis|analysis boundary')
        self.assertRegex(text.lower(), r'no.*(?:specific.*(?:placement|location)|'
                         r'placement recommendation)|'
                         r'(?:cannot|can.t).*recommend.*(?:placement|location)')
        self.assertNotIn('Holder', text)
        self.assertEqual(fixtures.unused_claims(self.finding(report)), [])
        self.assertIn('GET /products/{id}', self.finding(report))
        self.assertIn('${product.url}', self.finding(report))

    def test_multiple_findings_explain_terminology_once_and_scope_advice(self):
        self.direct()
        self.extra_clients()
        self.put('BillingCaller', '''package sample;
class BillingCaller {
    BillingClient billing;
    String charge(String id) { return billing.get(id); }
}
''')
        report = self.report()
        product = self.guidance(report, 'products')
        billing = self.guidance(report, 'billing')
        stock = self.guidance(report, 'stock')
        self.suggestion(product)
        self.suggestion(billing)
        self.assertIn('Order', product)
        self.assertNotIn('BillingCaller', product)
        self.assertIn('BillingCaller', billing)
        self.assertNotIn('Order', billing)
        self.assertNotIn('Order', stock)
        self.assertNotIn('BillingCaller', stock)
        self.assert_definitions_once(report)
        self.assertEqual(report.encode('utf-8'), self.report().encode('utf-8'))


if __name__ == '__main__':
    unittest.main()
