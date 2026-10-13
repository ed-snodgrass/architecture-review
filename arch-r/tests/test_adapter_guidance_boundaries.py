"""Additional black-box contracts for the first pending adapter-guidance task.

Analyze disposable Java sources only. Do not require later diagram changes or
select an implementation API. Existing guidance tests cover the main cases;
these cover uncertainty and multiple arrangements within one finding.
"""
import unittest

from tests import test_adapter_guidance as guidance_fixtures
from tests import test_usage_report as fixtures


class AdapterGuidanceBoundaryTests(unittest.TestCase):
    # Share helpers without inheriting (and rerunning) either existing suite.
    setUp = fixtures.UsageReportTests.setUp
    put = fixtures.UsageReportTests.put
    client = fixtures.UsageReportTests.client
    report = fixtures.UsageReportTests.report
    finding = fixtures.UsageReportTests.finding
    interface_route = fixtures.UsageReportTests.interface_route
    gateway = fixtures.UsageReportTests.gateway
    order = fixtures.UsageReportTests.order
    guidance = guidance_fixtures.AdapterGuidanceTests.guidance
    suggestion = guidance_fixtures.AdapterGuidanceTests.suggestion

    def test_ambiguous_interface_does_not_select_an_upstream_adapter_route(self):
        self.interface_route(second=True)
        report = self.report()
        text = self.guidance(report)
        self.suggestion(text)
        # Both implementations have observed Feign calls. Advice can review
        # those direct callers, but ambiguity cannot establish Order's wiring.
        for name in ('HttpGateway', 'OtherGateway'):
            self.assertIn(name, text)
        self.assertNotRegex(text, r'Order\s+(?:is wired to|uses at runtime|calls directly)\s+'
                            r'(?:HttpGateway|OtherGateway)')
        self.assertNotRegex(text, r'(?:HttpGateway|OtherGateway)[^\n.]*'
                            r'is an? (?:existing |confirmed )?adapter for Order')
        self.assertRegex(text.lower(), r'(whether|if).*business')
        self.assertRegex(self.finding(report).lower(), r'ambigu|multiple implementation')

    def test_unsupported_local_receiver_is_not_a_placement_recommendation(self):
        self.put('LocalCaller', '''package sample;
class LocalCaller {
    void work(String id) {
        Client local = null;
        local.get(id);
    }
}
''')
        report = self.report()
        text = self.guidance(report)
        # Local-variable receivers are outside the seed's supported forms:
        # lack of a supported chain is neither an unused verdict nor placement.
        self.assertRegex(text.lower(), r'no.*(?:supported.*caller|caller.*found|supported.*call)')
        self.assertRegex(text.lower(), r'within|analysis boundary|supported analysis')
        self.assertRegex(text.lower(), r'no.*specific.*(?:placement|location)|'
                         r'(?:cannot|can.t).*recommend.*(?:placement|location)')
        self.assertNotIn('LocalCaller', text)
        self.assertEqual(fixtures.unused_claims(self.finding(report)), [])
        self.assertIn('GET /products/{id}', self.finding(report))

    def test_one_finding_keeps_direct_and_intermediary_reviews_distinct(self):
        self.gateway()
        self.order()
        # A name ending in Adapter does not prove a responsibility or adequacy.
        self.put('NamedAdapter', '''package sample;
class NamedAdapter {
    Client client;
    String fetch(String id) { return client.get(id); }
}
''')
        text = self.guidance(self.report())
        self.suggestion(text)
        for name in ('Order', 'Gateway', 'NamedAdapter'):
            self.assertIn(name, text)
        direct_review = '\n'.join(line for line in text.splitlines()
                                  if 'NamedAdapter' in line)
        self.assertRegex(direct_review.lower(), r'(review|check|consider|assess)')
        self.assertRegex(direct_review.lower(), r'(whether|if).*business')
        self.assertRegex(text, r'(?i)Gateway[^\n]*'
                         r'(?:candidate|potential|could)[^\n]*adapter')
        self.assertNotRegex(text, r'NamedAdapter\s+(?:contains|handles|implements|has)\s+'
                            r'business (?:logic|decisions)')
        self.assertNotRegex(text, r'(?:NamedAdapter|Gateway)\s+(?:is|provides)\s+'
                            r'(?:an?\s+)?(?:adequate|sufficient|proper)')


if __name__ == '__main__':
    unittest.main()
