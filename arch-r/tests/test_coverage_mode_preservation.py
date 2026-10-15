"""Iteration 005: report replacement and coverage-only mode changes.

Exercise the public CLI with disposable modules. Compare every report section
outside coverage, including summary counts, evidence, guidance and diagrams.
"""
import re
import unittest

from archr.module import load_module
from tests import test_untraced_call_coverage as fixtures


class CoverageModePreservationTests(unittest.TestCase):
    setUp = fixtures.UntracedCallCoverageTests.setUp
    put = fixtures.UntracedCallCoverageTests.put
    client = fixtures.UntracedCallCoverageTests.client
    snapshot = fixtures.UntracedCallCoverageTests.snapshot
    run_cli = fixtures.UntracedCallCoverageTests.run_cli
    report = fixtures.UntracedCallCoverageTests.report
    assert_coverage = fixtures.UntracedCallCoverageTests.assert_coverage

    def split_coverage(self, report):
        self.assertNotRegex(report, r'(?m)^## Analysis coverage$')
        architecture, limitations = report.split('## Limitations\n', 1)
        return limitations, architecture

    def rich_module(self):
        self.client(url='${products.url}')
        self.client('BillingClient', 'billing', 'https://billing.example')
        self.put('Port', '''package sample;
interface Port { String lookup(String id); }
''')
        self.put('Gateway', '''package sample;
class Gateway implements Port {
    Client client;
    BillingClient billing;
    public String lookup(String id) {
        billing.get(id);
        client.missing(id);
        return client.get(id);
    }
}
''')
        self.put('Order', '''package sample;
class Order {
    Port port;
    String place(Request request) {
        request.coverageOnlyGap();
        return port.lookup("id");
    }
}
''')

    def test_flag_changes_only_coverage_not_any_other_report_content(self):
        self.rich_module()
        default = self.report()
        brief, architecture = self.split_coverage(default)
        self.assert_coverage(default, 2)
        # Guard against a vacuous equality check on an empty report: this
        # fixture must actually exercise counts, chains, relevant uncertainty,
        # guidance, evidence and a diagram before comparing modes.
        self.assertIn('Found 2 statically declared Feign outbound HTTP dependencies.',
                      architecture)
        for section in ('Findings', 'Adapter Review Guidance', 'Findings with Evidence'):
            content = architecture.split(f'## {section}\n', 1)[1].split('\n## ', 1)[0]
            self.assertEqual(len(re.findall(r'^### Finding ', content, re.M)), 2)
        for text in ('Possible chain', 'Observed source call',
                     'destination unresolved', 'client.missing',
                     'src/main/java/sample/Gateway.java:',
                     '**Adapter Recommendation:**', '**Interpreting a client response**',
                     '```mermaid', 'Rel('):
            self.assertIn(text, architecture)
        self.assertNotIn('coverageOnlyGap', default)
        for before in (False, True):
            with self.subTest(flag_before_path=before):
                detailed = self.report(details=True, before=before)
                coverage, unchanged = self.split_coverage(detailed)
                self.assertEqual(architecture, unchanged,
                                 'Only module-wide coverage may change with the flag')
                summary, details = coverage.split('### Untraced call sites\n', 1)
                self.assertEqual(brief.rstrip(), summary.rstrip())
                self.assertIn('coverageOnlyGap', details)
                self.assertIn('client.missing', architecture)
                self.assert_coverage(detailed, 2)

    def test_modes_replace_custom_named_report_in_caller_directory(self):
        # The artifact name, not the module folder, determines the established
        # filename. A space in the folder also exercises CLI path handling.
        self.module = self.module.rename(self.work / 'source module')
        (self.module / 'pom.xml').write_text(
            '<project><artifactId>Orders / API</artifactId></project>',
            encoding='utf-8')
        self.output = self.work / 'arch-r-report-Orders-API.md'
        self.assertEqual(load_module(str(self.module)).report_filename,
                         self.output.name)
        self.put('Plain', '''package sample;
class Plain {
    void run(Request request) { request.coverageOnlyGap(); }
}
''')
        module_before = self.snapshot()
        outputs = {}
        # Include both directions and both flag positions. Read bytes from
        # disk so the test checks replacement, not merely renderer return values.
        for details, before in ((False, False), (True, False),
                                (False, False), (True, True), (False, False)):
            with self.subTest(details=details, flag_before_path=before):
                report = self.report(details=details, before=before)
                data = self.output.read_bytes()
                self.assertEqual('coverageOnlyGap' in report, details)
                self.assertEqual('src/main/java/sample/Plain.java:3' in report,
                                 details)
                self.assert_coverage(report, 1)
                if details in outputs:
                    self.assertEqual(outputs[details], data)
                outputs[details] = data
                self.assertEqual(set(self.work.iterdir()),
                                 {self.module, self.output},
                                 'Modes must not create separate detail artifacts')
                self.assertEqual(module_before, self.snapshot())
        self.assertNotEqual(outputs[False], outputs[True])
        self.assertNotIn(b'coverageOnlyGap', self.output.read_bytes())


if __name__ == '__main__':
    unittest.main()
