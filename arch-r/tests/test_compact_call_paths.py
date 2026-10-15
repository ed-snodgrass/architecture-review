"""Iteration 005: compact, grouped paths without changing analysis evidence."""
from dataclasses import replace
import html
from pathlib import Path
import tempfile
import unittest

from archr.discovery import discover_clients
from archr.findings import discover_findings
from archr.module import load_module
from archr.report import _compact_call_lines, render_report
from archr.traversal import trace_usage


class CompactCallPathTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        java = Path(self.directory.name) / 'src/main/java'
        java.mkdir(parents=True)
        (java / 'Example.java').write_text('''
import org.springframework.data.jpa.repository.JpaRepository;
interface Orders extends JpaRepository<Order, Long> {}
class Service {
 Orders orders;
 void place() { orders.findById(1L); orders.save(null); orders.save(null); }
 void other() { orders.save(null); }
}
class Controller {
 Service service;
 void place() { service.place(); }
 void other() { service.other(); }
}
''')
        self.module = load_module(self.directory.name)
        self.usage = trace_usage(self.module)

    def test_shared_path_once_operations_remain_and_output_is_deterministic(self):
        findings = discover_findings(self.module)
        def report():
            return render_report(self.module, discover_clients(self.module),
                                 self.usage, findings=findings)
        text = report()
        self.assertEqual(text, report())
        calls = html.unescape(text.split('#### Observed Call Chains', 1)[1]
                             .split('## Limitations', 1)[0])
        self.assertEqual(calls.count('Controller.place → Service.place'), 1)
        self.assertEqual(calls.count('→ Orders.findById'), 1)
        self.assertEqual(calls.count('→ Orders.save'), 2)  # one per upstream method
        self.assertIn('Controller.other → Service.other → Orders.save', calls)
        for excluded in ('receiver ', 'Invocation in', 'method name at',
                         'Chain 1', 'intermediary', 'src/main/java'):
            self.assertNotIn(excluded, calls)
        operations = text.split('#### Operations', 1)[1].split('#### Observed Call Chains')[0]
        self.assertIn('findById', operations)
        self.assertEqual(operations.count('**Observed source operation call:** save'), 3)

    def test_deduplication_ignores_sites_not_method_identity_or_cutoffs(self):
        chain = next(c for c in self.usage.chains
                     if c.steps[0].link.target_method.name == 'save')
        rendered = lambda chains: '\n'.join(_compact_call_lines(chains))
        original = rendered([chain])
        self.assertEqual(rendered([chain, chain]), original)
        terminal = chain.steps[0]
        moved = replace(terminal, link=replace(terminal.link, invocation=replace(
            terminal.link.invocation, line=999, source_offset=999)))
        self.assertEqual(rendered([chain, replace(chain, steps=(moved, *chain.steps[1:]))]),
                         original)
        variants = [replace(chain, certainty='possible'),
                    replace(chain, boundary='depth', boundary_reason='Depth limit; may continue.'),
                    replace(chain, boundary='cycle', boundary_reason='Cycle cutoff.',
                            cycle_link=terminal.link)]
        for variant in variants:
            with self.subTest(variant=variant.boundary or variant.certainty):
                self.assertEqual(rendered([chain, variant]).count('source chain:') +
                                 rendered([chain, variant]).count('Possible chain:'), 2)
        overload = replace(terminal.link.target_method, parameter_count=2)
        variant = replace(chain, steps=(replace(terminal, link=replace(
            terminal.link, target_method=overload)), *chain.steps[1:]))
        # Same displayed name, but distinct retained method identities.
        self.assertEqual(rendered([chain, variant]).count('→ Orders.save'), 2)

    def test_interface_and_unresolved_evidence_remain_local(self):
        java = Path(self.directory.name) / 'src/main/java/Example.java'
        java.write_text('''
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient(name="products") interface Products { String get(); }
interface Port { String fetch(); }
class Gateway implements Port {
 Products products;
 public String fetch() { return products.get(); }
}
class Controller { Port port; String call() { return port.fetch(); } }
''')
        usage = trace_usage(self.module)
        chains = list(usage.chains)
        possible = next(c for c in chains if c.certainty == 'possible')
        text = '\n'.join(_compact_call_lines(chains))
        self.assertIn('Possible chain: Controller.call → Gateway.fetch → Products.get', text)
        self.assertIn('Possible interface connection: Port → Gateway.fetch', text)
        self.assertIn('runtime wiring is unverified', text)
        step = next(s for s in possible.steps if s.interface_connection)
        altered = replace(step, interface_connection=replace(
            step.interface_connection, reason='Different interface resolution.'))
        variant = replace(possible, steps=tuple(altered if s is step else s
                                               for s in possible.steps))
        text = '\n'.join(_compact_call_lines([possible, variant]))
        self.assertEqual(text.count('Possible chain:'), 2)


if __name__ == '__main__':
    unittest.main()
