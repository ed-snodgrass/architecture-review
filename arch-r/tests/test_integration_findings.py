"""Independent evidence dimensions for iteration 004 findings."""

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from archr.findings import (DestinationCertainty, DestinationEvidence,
                            IntegrationFinding, OperationEvidence, SourceEvidence,
                            UsageCertainty, discover_findings)
from archr.indexing import Invocation
from archr.integrations import extract_declarations
from archr.module import load_module
from archr.traversal import trace_usage


class IntegrationFindingTests(unittest.TestCase):
    path = 'src/main/java/shop/Gateway.java'

    def finding(self):
        declaration, = extract_declarations(
            'package shop; class Gateway { '
            'org.springframework.jdbc.core.JdbcTemplate jdbc; }', self.path)
        return IntegrationFinding(declaration)

    def operation(self, **kwargs):
        return OperationEvidence('query', (SourceEvidence(self.path, 5),), **kwargs)

    def test_declaration_is_retained_with_independent_unknown_defaults(self):
        finding = self.finding()
        self.assertEqual(finding.declaration_evidence, SourceEvidence(self.path, 1))
        self.assertEqual(finding.status_label,
                         'Declared integration — No supported caller found')
        self.assertEqual(finding.destination.label, 'Destination unknown')
        self.assertEqual(finding.usage_certainty, UsageCertainty.NO_SUPPORTED_CALLER)
        self.assertEqual(finding.operations, ())
        self.assertEqual(finding.chains, ())

    def test_declared_operation_or_builder_does_not_establish_caller(self):
        invocation = Invocation('web', 'get', 0, self.path, 5)
        for operation in (self.operation(),
                          self.operation(invocation=invocation,
                                         is_request_operation=False)):
            finding = replace(self.finding(), operations=(operation,))
            self.assertFalse(finding.has_supported_caller)
            self.assertEqual(finding.supported_call_evidence, ())
            self.assertEqual(finding.usage_certainty,
                             UsageCertainty.NO_SUPPORTED_CALLER)

    def test_source_call_does_not_require_known_destination(self):
        invocation = Invocation('jdbc', 'query', 1, self.path, 5)
        operation = self.operation(invocation=invocation)
        finding = replace(self.finding(), operations=(operation,))
        self.assertTrue(finding.has_supported_caller)
        self.assertEqual(finding.usage_certainty, UsageCertainty.OBSERVED)
        self.assertEqual(finding.destination.label, 'Destination unknown')
        self.assertEqual(operation.destination.certainty, DestinationCertainty.UNKNOWN)
        self.assertEqual(finding.declaration_evidence, self.finding().declaration_evidence)

    def test_supported_call_citations_are_separate_sorted_and_deduplicated(self):
        # The operation's annotation/configuration citation is not the call site.
        later = self.operation(invocation=Invocation('jdbc', 'query', 1, self.path, 9))
        earlier = self.operation(invocation=Invocation('jdbc', 'update', 1, self.path, 3))
        builder = self.operation(invocation=Invocation('jdbc', 'other', 0, self.path, 2),
                                 is_request_operation=False)
        finding = replace(self.finding(), operations=(later, earlier, later, builder))
        self.assertEqual(finding.supported_call_evidence,
                         (SourceEvidence(self.path, 3), SourceEvidence(self.path, 9)))
        self.assertEqual(finding.declaration_evidence, SourceEvidence(self.path, 1))
        self.assertEqual(finding.destination.certainty, DestinationCertainty.UNKNOWN)

    def test_destination_evidence_does_not_establish_usage(self):
        for certainty, value, label in (
            (DestinationCertainty.LITERAL, 'https://example.test', 'Literal destination'),
            (DestinationCertainty.PATH, '/items', 'Host unknown'),
            (DestinationCertainty.UNRESOLVED, '${products.url}', 'Destination unresolved'),
        ):
            with self.subTest(certainty=certainty):
                destination = DestinationEvidence(
                    certainty, value, (SourceEvidence(self.path, 6),))
                finding = replace(self.finding(), destination=destination)
                self.assertIn(label, finding.destination.label)
                self.assertIn(value, finding.destination.label)
                self.assertEqual(finding.usage_certainty,
                                 UsageCertainty.NO_SUPPORTED_CALLER)
                self.assertEqual(finding.declaration_evidence.line, 1)

    def test_operation_destinations_remain_independent(self):
        first = self.operation(
            destination=DestinationEvidence(DestinationCertainty.PATH, '/items'))
        second = self.operation()
        finding = replace(self.finding(), operations=(first, second))
        self.assertEqual(finding.operations[0].destination.value, '/items')
        self.assertEqual(finding.operations[1].destination.label, 'Destination unknown')
        self.assertEqual(finding.destination.label, 'Destination unknown')

    def test_all_mechanisms_have_declaration_only_findings(self):
        source = '''package shop;
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient(name = "products") interface Products {}
interface Orders extends org.springframework.data.jpa.repository.JpaRepository<Order, Long> {}
class Gateway {
    org.springframework.jdbc.core.JdbcTemplate jdbc;
    org.springframework.web.client.RestTemplate rest;
    org.springframework.web.reactive.function.client.WebClient web;
    void other() { jdbc.toString(); }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / self.path
            path.parent.mkdir(parents=True)
            path.write_text(source, encoding='utf-8')
            module = load_module(directory)
            before = path.read_bytes()
            findings = discover_findings(module)
            self.assertEqual(len(findings), 5)
            self.assertEqual(len({f.declaration.identity for f in findings}), 5)
            self.assertTrue(all(not f.has_supported_caller for f in findings))
            self.assertTrue(all(f.destination.label == 'Destination unknown'
                                for f in findings))
            self.assertEqual(findings, discover_findings(module))
            self.assertEqual(path.read_bytes(), before)

    def test_possible_chain_does_not_weaken_declaration_or_destination(self):
        source = '''package shop;
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient(name = "products") interface Products { String get(); }
class Gateway { Products products; String load() { return products.get(); } }
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / self.path
            path.parent.mkdir(parents=True)
            path.write_text(source, encoding='utf-8')
            module = load_module(directory)
            finding = discover_findings(module)[0]
            chain, = trace_usage(module).chains
            observed = replace(finding, chains=(chain,))
            possible = replace(finding, chains=(replace(chain, certainty='possible'),))
            self.assertEqual(observed.usage_certainty, UsageCertainty.OBSERVED)
            self.assertEqual(possible.usage_certainty, UsageCertainty.POSSIBLE)
            self.assertEqual(possible.declaration_evidence, observed.declaration_evidence)
            self.assertEqual(possible.destination, observed.destination)
            self.assertTrue(possible.has_supported_caller)
            invocation = chain.steps[0].link.invocation
            citation = SourceEvidence(invocation.source_path, invocation.line)
            self.assertEqual(possible.supported_call_evidence, (citation,))
            operation = OperationEvidence(invocation.method_name, (citation,),
                                          invocation=invocation)
            combined = replace(possible, operations=(operation,))
            self.assertEqual(combined.supported_call_evidence, (citation,))
            # Remove independently recorded operation calls as well as chain
            # steps: either evidence dimension can establish a supported caller.
            empty = replace(finding, operations=(),
                            chains=(replace(chain, steps=(), certainty='possible'),))
            self.assertFalse(empty.has_supported_caller)
            self.assertEqual(empty.usage_certainty, UsageCertainty.NO_SUPPORTED_CALLER)
            self.assertEqual(empty.status_label,
                             'Declared integration — No supported caller found')


if __name__ == '__main__':
    unittest.main()
