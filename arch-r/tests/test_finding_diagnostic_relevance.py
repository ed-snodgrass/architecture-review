"""Iteration 003: finding relevance requires evidence, not method proximity.

Use real disposable Java sources and CLI reports. No production changes or
new supported call forms are required by these contracts.
"""
import re
import unittest

from archr.module import load_module
from archr.traversal import trace_usage
from tests import test_untraced_call_coverage as coverage_fixtures


class FindingDiagnosticRelevanceTests(unittest.TestCase):
    setUp = coverage_fixtures.UntracedCallCoverageTests.setUp
    put = coverage_fixtures.UntracedCallCoverageTests.put
    client = coverage_fixtures.UntracedCallCoverageTests.client
    snapshot = coverage_fixtures.UntracedCallCoverageTests.snapshot
    run_cli = coverage_fixtures.UntracedCallCoverageTests.run_cli
    report = coverage_fixtures.UntracedCallCoverageTests.report
    architectural_sections = coverage_fixtures.UntracedCallCoverageTests.architectural_sections

    def finding(self, report, system):
        from tests.report_sections import finding
        return finding(report, system)

    def assert_modes_preserve_findings(self, default, detailed):
        self.assertEqual(self.architectural_sections(default),
                         self.architectural_sections(detailed))

    def test_unrelated_ambiguous_call_in_shared_method_is_not_a_client_concern(self):
        self.client()
        self.client('BillingClient', 'billing')
        self.put('Helper', '''package sample;
class Helper {
    String get(String id) { return id; }
    String get(Integer id) { return "id"; }
}
''')
        self.put('Shared', '''package sample;
class Shared {
    Client products;
    BillingClient billing;
    Helper helper;
    void work(String id) {
        products.get(id);
        billing.get(id);
        helper.get(id);
    }
}
''')
        usage = trace_usage(load_module(str(self.module)))
        self.assertEqual([d.code for d in usage.diagnostics], ['ambiguous-overload'])
        default, detailed = self.report(), self.report(details=True)
        for system in ('products', 'billing'):
            finding = self.finding(default, system)
            for unrelated in ('Helper', 'helper.get', 'ambiguous-overload',
                              'src/main/java/sample/Shared.java:9'):
                self.assertNotIn(unrelated, finding)
        self.assertNotIn('helper.get', default)
        self.assertIn('helper.get', detailed)
        self.assertIn('src/main/java/sample/Shared.java:9', detailed)
        self.assert_modes_preserve_findings(default, detailed)

    def test_unrelated_candidates_in_feign_source_file_are_not_client_evidence(self):
        # Java permits a package-private helper beside the Feign declaration.
        # Its overloads share a source path, not a receiver type or usage route.
        self.put('Client', '''package sample;
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient(name="products", url="https://products.example")
interface Client {
    String get(String id);
    String send(String id);
    String send(Integer id);
}
class Helper {
    String lookup(String id) { return id; }
    String lookup(Integer id) { return "id"; }
}
''')
        self.put('Order', '''package sample;
class Order {
    Client client;
    Helper helper;
    void work(String id) {
        client.get(id);
        client.send(id);
        helper.lookup(id);
    }
}
''')
        usage = trace_usage(load_module(str(self.module)))
        self.assertEqual(len(usage.diagnostics), 2)
        by_receiver = {d.invocation.receiver: d for d in usage.diagnostics}
        self.assertEqual(set(by_receiver), {'client', 'helper'})
        for receiver, type_name, lines in (('client', 'sample.Client', {6, 7}),
                                           ('helper', 'sample.Helper', {10, 11})):
            diagnostic = by_receiver[receiver]
            self.assertEqual(diagnostic.code, 'ambiguous-overload')
            self.assertEqual(diagnostic.receiver_field.type_name, type_name)
            self.assertEqual({m.source_path for m in diagnostic.candidates},
                             {'src/main/java/sample/Client.java'})
            self.assertEqual({m.line for m in diagnostic.candidates}, lines)

        default, detailed = self.report(), self.report(details=True)
        finding = self.finding(default, 'products')
        # Keep genuine client uncertainty while excluding colocated helpers.
        self.assertIn('client.send', finding)
        self.assertIn('ambiguous-overload', finding)
        for line in (6, 7):
            self.assertIn(f'src/main/java/sample/Client.java:{line}', finding)
        for unrelated in ('Helper', 'helper.lookup',
                          'src/main/java/sample/Order.java:8',
                          'src/main/java/sample/Client.java:10',
                          'src/main/java/sample/Client.java:11'):
            self.assertNotIn(unrelated, finding)
        self.assertNotIn('helper.lookup', default)
        self.assertIn('helper.lookup', detailed)
        self.assertIn('src/main/java/sample/Order.java:8', detailed)
        coverage_fixtures.UntracedCallCoverageTests.assert_coverage(self, default, 2)
        coverage_fixtures.UntracedCallCoverageTests.assert_coverage(self, detailed, 2)
        self.assert_modes_preserve_findings(default, detailed)

    def test_client_field_gap_is_relevant_only_to_its_client_without_supported_usage(self):
        self.client()
        self.client('BillingClient', 'billing')
        self.put('Shared', '''package sample;
class Shared {
    Client products;
    BillingClient billing;
    void work(String id) {
        products.missing(id);
        billing.get(id);
    }
}
''')
        usage = trace_usage(load_module(str(self.module)))
        self.assertEqual([d.code for d in usage.diagnostics], ['unresolved-method'])
        self.assertEqual(usage.diagnostics[0].receiver_field.type_name, 'sample.Client')
        default, detailed = self.report(), self.report(details=True)
        products = self.finding(default, 'products')
        self.assertIn('products.missing', products)
        self.assertIn('src/main/java/sample/Shared.java:6', products)
        self.assertRegex(products.lower(), r'no.*(?:declared|matching).*method')
        guidance = products.split('#### Review conditions', 1)[1].split('#### Declaration', 1)[0]
        self.assertIn('cannot identify code to review', guidance)
        billing = self.finding(default, 'billing')
        self.assertNotIn('products.missing', billing)
        self.assertNotIn('src/main/java/sample/Shared.java:6', billing)
        self.assert_modes_preserve_findings(default, detailed)

    def test_shadowed_field_name_is_not_evidence_but_explicit_this_field_is(self):
        self.client()
        self.put('Order', '''package sample;
class Order {
    Client client;
    void work(Request client) {
        this.client.get("id");
        client.getId();
        this.client.<String>get("id");
    }
}
''')
        usage = trace_usage(load_module(str(self.module)))
        self.assertEqual([d.code for d in usage.diagnostics],
                         ['unsupported-receiver', 'unsupported-syntax'])
        self.assertIsNone(usage.diagnostics[0].receiver_field)
        self.assertEqual(usage.diagnostics[1].receiver_field.type_name, 'sample.Client')
        default, detailed = self.report(), self.report(details=True)
        finding = self.finding(default, 'products')
        self.assertNotIn('getId', finding)
        self.assertNotIn('src/main/java/sample/Order.java:6', finding)
        self.assertNotIn('unsupported-receiver', finding)
        self.assertIn('src/main/java/sample/Order.java:7', finding)
        self.assertRegex(finding.lower(), r'generic.*not supported')
        guidance = finding.split('#### Review conditions', 1)[1].split('#### Declaration', 1)[0]
        self.assertNotIn('getId', guidance)
        self.assertNotIn('generic', guidance)
        self.assertIn('getId', detailed)
        self.assertIn('src/main/java/sample/Order.java:6', detailed)
        self.assert_modes_preserve_findings(default, detailed)

    def test_relevant_overload_and_interface_ambiguity_keep_evidence_by_default(self):
        self.put('Client', '''package sample;
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient(name="products", url="${products.url}")
interface Client {
    String get(String id);
    String get(Integer id);
    String send(String id);
}
''')
        self.put('Port', '''package sample;
interface Port { String lookup(String id); }
''')
        for name in ('FirstGateway', 'SecondGateway'):
            self.put(name, f'''package sample;
class {name} implements Port {{
    Client client;
    public String lookup(String id) {{ return client.send(id); }}
}}
''')
        self.put('Order', '''package sample;
class Order {
    Port port;
    Client client;
    void work(Request request) {
        port.lookup("id");
        client.get("id");
        request.getId();
    }
}
''')
        usage = trace_usage(load_module(str(self.module)))
        self.assertEqual({d.code for d in usage.diagnostics},
                         {'ambiguous-overload', 'unsupported-receiver'})
        self.assertEqual({d.code for d in usage.interface_diagnostics},
                         {'ambiguous-implementation'})
        default, detailed = self.report(), self.report(details=True)
        finding = self.finding(default, 'products')
        self.assertIn('destination unresolved', finding)
        self.assertIn('${products.url}', finding)
        self.assertIn('ambiguous-overload', finding)
        self.assertIn('ambiguous-implementation', finding)
        for path, line in (('Order', 6), ('Order', 7), ('Client', 5), ('Client', 6),
                           ('FirstGateway', 2), ('SecondGateway', 2)):
            self.assertIn(f'src/main/java/sample/{path}.java:{line}', finding)
        self.assertNotIn('request.getId', default)
        self.assertNotIn('src/main/java/sample/Order.java:8', default)
        self.assertIn('request.getId', detailed)
        self.assert_modes_preserve_findings(default, detailed)


if __name__ == '__main__':
    unittest.main()
