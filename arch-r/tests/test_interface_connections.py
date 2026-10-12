"""Objective contracts for iteration 002's interface-resolution task.

Proposed seam: archr.interfaces.resolve_interfaces(Module) -> result exposing
connections and diagnostics. This seam is not implemented by these tests.
Existing archr.resolution links remain source calls to declared endpoints.

A connection exposes link (the existing CallLink to the interface method),
interface_type and implementation_type (indexed JavaType declaration evidence),
implementation_method (indexed Method), certainty='possible', and a nonempty
reason explicitly stating runtime wiring is unverified. A diagnostic exposes
link, code, message, and candidates (concrete JavaType declarations). Codes:
no-local-implementation, ambiguous-implementation, ambiguous-implementation-method,
unresolved-implementation-method. Candidate selection is declaration-only;
method absence must not be used to choose between multiple implementations.

Only ordinary non-generic interfaces/direct concrete implements are required.
Traversal, report prose, diagram rendering, and adapter advice are later tasks.
All Java fixtures are read as source, never compiled or executed.
"""

import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from archr.module import load_module
from archr.resolution import resolve_calls


class InterfaceConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='arch_r_interfaces_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'src/main/java').mkdir(parents=True)
        self.module = load_module(str(self.root))

    def put(self, relative, source):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')
        return relative

    def resolve(self):
        try:
            api = importlib.import_module('archr.interfaces')
        except ModuleNotFoundError as exc:
            if exc.name != 'archr.interfaces':
                raise
            self.fail('Interface resolution is not implemented: missing '
                      'archr.interfaces.resolve_interfaces')
        return api.resolve_interfaces(self.module)

    def base(self, calls='gateway.lookup(id);'):
        self.interface_path = self.put('src/main/java/api/ProductGateway.java', '''package api;
public interface ProductGateway {
    String lookup(String id);
    void health();
}
''')
        self.client_path = self.put('src/main/java/remote/ProductClient.java', '''package remote;
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient(name = "product-service", url = "${product.url}")
public interface ProductClient {
    String getProduct(String id);
}
''')
        self.caller_path = self.put('src/main/java/shop/Order.java', '''package shop;
import api.ProductGateway;
class Order {
    private final ProductGateway gateway;
    Order(ProductGateway gateway) { this.gateway = gateway; }
    void place(String id) {
        ''' + calls + '''
    }
}
''')

    def implementation(self, name='HttpProductGateway', directory='src/main/java',
                       modifier='', declaration='implements ProductGateway'):
        return self.put(f'{directory}/adapters/{name}.java', '''package adapters;
import api.ProductGateway;
import remote.ProductClient;
public ''' + modifier + 'class ' + name + ' ' + declaration + ''' {
    private final ProductClient client;
    public ''' + name + '''(ProductClient client) { this.client = client; }
    public String lookup(String id) {
        return client.getProduct(id);
    }
    public void health() {}
}
''')

    @staticmethod
    def endpoint(link):
        return (link.caller_type, link.caller_method.name, link.target_type,
                link.target_method.name, link.target_method.parameter_count)

    def test_unique_implementation_is_possible_and_retains_four_required_citations(self):
        self.base()
        implementation_path = self.implementation()
        result = self.resolve()
        self.assertEqual(tuple(result.diagnostics), ())
        self.assertEqual(len(result.connections), 1)
        connection = result.connections[0]
        self.assertEqual(connection.certainty, 'possible')
        self.assertRegex(connection.reason.lower(), r'runtime.*(unverified|not verified)')
        self.assertEqual(self.endpoint(connection.link),
                         ('shop.Order', 'place', 'api.ProductGateway', 'lookup', 1))
        self.assertEqual((connection.link.invocation.source_path,
                          connection.link.invocation.line), (self.caller_path, 7))
        self.assertEqual((connection.link.receiver_field.type_name,
                          connection.link.receiver_field.source_path,
                          connection.link.receiver_field.line),
                         ('api.ProductGateway', self.caller_path, 4))
        self.assertEqual((connection.link.target_method.source_path,
                          connection.link.target_method.line), (self.interface_path, 3))
        self.assertEqual((connection.interface_type.qualified_name,
                          connection.interface_type.source_path,
                          connection.interface_type.line),
                         ('api.ProductGateway', self.interface_path, 2))
        self.assertEqual((connection.implementation_type.qualified_name,
                          connection.implementation_type.source_path,
                          connection.implementation_type.line),
                         ('adapters.HttpProductGateway', implementation_path, 4))
        self.assertEqual((connection.implementation_method.name,
                          connection.implementation_method.parameter_count,
                          connection.implementation_method.source_path,
                          connection.implementation_method.line),
                         ('lookup', 1, implementation_path, 7))
        # The candidate's Feign call remains independently observed, not wiring proof.
        direct = [link for link in resolve_calls(self.module).links
                  if link.target_type == 'remote.ProductClient']
        self.assertEqual(len(direct), 1)
        self.assertEqual((direct[0].caller_type, direct[0].invocation.line),
                         ('adapters.HttpProductGateway', 8))

    def test_multiple_implementations_name_all_candidates_without_selecting_route(self):
        self.base()
        second = self.implementation('SecondGateway')
        first = self.implementation()
        result = self.resolve()
        self.assertEqual(tuple(result.connections), ())
        self.assertEqual(len(result.diagnostics), 1)
        diagnostic = result.diagnostics[0]
        self.assertEqual(diagnostic.code, 'ambiguous-implementation')
        self.assertEqual((diagnostic.link.invocation.source_path,
                          diagnostic.link.invocation.line), (self.caller_path, 7))
        self.assertTrue(diagnostic.message.strip())
        self.assertEqual([(c.qualified_name, c.source_path, c.line)
                          for c in diagnostic.candidates],
                         [('adapters.HttpProductGateway', first, 4),
                          ('adapters.SecondGateway', second, 4)])
        self.assertEqual(sorted(link.caller_type for link in resolve_calls(self.module).links
                                if link.target_type == 'remote.ProductClient'),
                         ['adapters.HttpProductGateway', 'adapters.SecondGateway'])

    def test_no_implementation_is_explicitly_scoped_to_analysis_boundary(self):
        self.base()
        self.implementation(directory='src/test/java')
        self.implementation('GeneratedGateway', directory='target/generated-sources')
        self.implementation('SiblingGateway', directory='sibling/src/main/java')
        result = self.resolve()
        self.assertEqual(tuple(result.connections), ())
        self.assertEqual(len(result.diagnostics), 1)
        diagnostic = result.diagnostics[0]
        self.assertEqual(diagnostic.code, 'no-local-implementation')
        self.assertEqual(tuple(diagnostic.candidates), ())
        self.assertEqual(diagnostic.link.target_type, 'api.ProductGateway')
        self.assertIn('src/main/java', diagnostic.message)
        self.assertRegex(diagnostic.message.lower(), r'(within|boundary|analy[sz]ed module)')

    def test_abstract_direct_implementor_is_not_a_concrete_candidate(self):
        self.base()
        self.implementation('AbstractGateway', modifier='abstract ')
        path = self.implementation()
        result = self.resolve()
        self.assertEqual(tuple(result.diagnostics), ())
        self.assertEqual([c.implementation_type.source_path for c in result.connections], [path])

    def test_type_identity_uses_packages_imports_fully_qualified_and_multiple_implements(self):
        self.base()
        self.put('src/main/java/other/ProductGateway.java',
                 'package other; public interface ProductGateway { String lookup(String id); }')
        self.put('src/main/java/adapters/Marker.java',
                 'package adapters; interface Marker {}')
        self.implementation('WrongGateway', declaration='implements other.ProductGateway')
        self.implementation(declaration='implements Marker, api.ProductGateway')
        self.put('src/main/java/api/LocalOrder.java', '''package api;
class LocalOrder {
    ProductGateway gateway;
    void place(String id) { this.gateway.lookup(id); }
}
''')
        self.put('src/main/java/shop/QualifiedOrder.java', '''package shop;
class QualifiedOrder {
    api.ProductGateway gateway;
    void place(String id) { gateway.lookup(id); }
}
''')
        result = self.resolve()
        self.assertEqual(tuple(result.diagnostics), ())
        self.assertEqual(sorted((c.link.caller_type, c.interface_type.qualified_name,
                                 c.implementation_type.qualified_name)
                                for c in result.connections),
                         [('api.LocalOrder', 'api.ProductGateway', 'adapters.HttpProductGateway'),
                          ('shop.Order', 'api.ProductGateway', 'adapters.HttpProductGateway'),
                          ('shop.QualifiedOrder', 'api.ProductGateway', 'adapters.HttpProductGateway')])

    def test_interface_health_call_does_not_select_feign_calling_lookup_method(self):
        self.base('gateway.health();')
        path = self.implementation()
        result = self.resolve()
        self.assertEqual(tuple(result.diagnostics), ())
        self.assertEqual(len(result.connections), 1)
        connection = result.connections[0]
        self.assertEqual((connection.link.target_method.name,
                          connection.implementation_method.name,
                          connection.implementation_method.parameter_count,
                          connection.implementation_method.source_path,
                          connection.implementation_method.line), ('health', 'health', 0, path, 10))
        self.assertEqual(tuple(connection.implementation_method.invocations), ())

    def test_implementation_methods_match_name_and_arity_not_same_named_overload(self):
        self.base()
        self.put('src/main/java/adapters/Overloaded.java', '''package adapters;
public class Overloaded implements api.ProductGateway {
    public String lookup() { return "none"; }
    public String lookup(String id) { return id; }
    public void health() {}
}
''')
        result = self.resolve()
        self.assertEqual(tuple(result.diagnostics), ())
        self.assertEqual([(c.implementation_method.name, c.implementation_method.parameter_count,
                           c.implementation_method.line) for c in result.connections],
                         [('lookup', 1, 4)])

    def test_same_arity_implementation_overloads_are_not_guessed(self):
        self.base()
        self.put('src/main/java/adapters/Overloaded.java', '''package adapters;
public class Overloaded implements api.ProductGateway {
    public String lookup(String id) { return id; }
    public String lookup(int id) { return "number"; }
    public void health() {}
}
''')
        result = self.resolve()
        self.assertEqual(tuple(result.connections), ())
        self.assertEqual(len(result.diagnostics), 1)
        self.assertEqual(result.diagnostics[0].code, 'ambiguous-implementation-method')
        self.assertEqual([c.qualified_name for c in result.diagnostics[0].candidates],
                         ['adapters.Overloaded'])
        self.assertTrue(result.diagnostics[0].message.strip())

    def test_inherited_implementation_method_is_unresolved_with_candidate_evidence(self):
        self.base()
        self.put('src/main/java/adapters/BaseGateway.java', '''package adapters;
public class BaseGateway {
    public String lookup(String id) { return id; }
    public void health() {}
}
''')
        path = self.put('src/main/java/adapters/InheritedGateway.java', '''package adapters;
public class InheritedGateway extends BaseGateway implements api.ProductGateway {
}
''')
        result = self.resolve()
        self.assertEqual(tuple(result.connections), ())
        self.assertEqual(len(result.diagnostics), 1)
        diagnostic = result.diagnostics[0]
        self.assertEqual(diagnostic.code, 'unresolved-implementation-method')
        self.assertEqual(self.endpoint(diagnostic.link),
                         ('shop.Order', 'place', 'api.ProductGateway', 'lookup', 1))
        self.assertEqual((diagnostic.link.invocation.source_path,
                          diagnostic.link.invocation.line), (self.caller_path, 7))
        self.assertEqual([(c.qualified_name, c.source_path, c.line)
                          for c in diagnostic.candidates],
                         [('adapters.InheritedGateway', path, 2)])
        self.assertIn('lookup', diagnostic.message)
        self.assertIn('inherited', diagnostic.message.lower())

    def test_multiple_candidates_are_not_filtered_by_declared_method_availability(self):
        self.base()
        direct = self.implementation()
        self.put('src/main/java/adapters/BaseGateway.java', '''package adapters;
public class BaseGateway {
    public String lookup(String id) { return id; }
    public void health() {}
}
''')
        inherited = self.put('src/main/java/adapters/InheritedGateway.java', '''package adapters;
public class InheritedGateway extends BaseGateway implements api.ProductGateway {
}
''')
        result = self.resolve()
        self.assertEqual(tuple(result.connections), ())
        self.assertEqual(len(result.diagnostics), 1)
        diagnostic = result.diagnostics[0]
        self.assertEqual(diagnostic.code, 'ambiguous-implementation')
        self.assertEqual((diagnostic.link.invocation.source_path,
                          diagnostic.link.invocation.line), (self.caller_path, 7))
        expected = [('adapters.HttpProductGateway', direct, 4),
                    ('adapters.InheritedGateway', inherited, 2)]
        self.assertEqual([(c.qualified_name, c.source_path, c.line)
                          for c in diagnostic.candidates], expected)
        for name, path, line in expected:
            self.assertIn(name, diagnostic.message)
            self.assertIn(f'{path}:{line}', diagnostic.message)
        # Ambiguous wiring must not erase the independently observed Feign call.
        self.assertEqual([(link.caller_type, link.invocation.source_path,
                           link.invocation.line) for link in resolve_calls(self.module).links
                          if link.target_type == 'remote.ProductClient'],
                         [('adapters.HttpProductGateway', direct, 8)])

    def test_indirect_implementations_do_not_become_direct_candidates(self):
        self.base()
        self.put('src/main/java/adapters/BaseGateway.java', '''package adapters;
public abstract class BaseGateway implements api.ProductGateway {
    public String lookup(String id) { return id; }
    public void health() {}
}
''')
        self.put('src/main/java/adapters/InheritedGateway.java', '''package adapters;
public class InheritedGateway extends BaseGateway {}
''')
        self.put('src/main/java/api/SpecialGateway.java', '''package api;
public interface SpecialGateway extends ProductGateway {}
''')
        self.put('src/main/java/adapters/SpecialGatewayImpl.java', '''package adapters;
public class SpecialGatewayImpl implements api.SpecialGateway {
    public String lookup(String id) { return id; }
    public void health() {}
}
''')
        result = self.resolve()
        self.assertEqual(tuple(result.connections), ())
        self.assertEqual(len(result.diagnostics), 1)
        diagnostic = result.diagnostics[0]
        self.assertEqual(diagnostic.code, 'no-local-implementation')
        self.assertEqual(tuple(diagnostic.candidates), ())
        self.assertEqual(diagnostic.link.target_type, 'api.ProductGateway')
        self.assertIn('src/main/java', diagnostic.message)
        self.assertRegex(diagnostic.message.lower(), r'(within|boundary|analy[sz]ed module)')

    def test_generic_implementor_is_excluded_even_for_non_generic_interface(self):
        self.base()
        self.put('src/main/java/adapters/GenericGateway.java', '''package adapters;
public class GenericGateway<T> implements api.ProductGateway {
    public String lookup(String id) { return id; }
    public void health() {}
}
''')
        result = self.resolve()
        self.assertEqual(tuple(result.connections), ())
        self.assertEqual(len(result.diagnostics), 1)
        self.assertEqual(result.diagnostics[0].code, 'no-local-implementation')
        self.assertEqual(tuple(result.diagnostics[0].candidates), ())
        self.assertIn('src/main/java', result.diagnostics[0].message)
        # An excluded generic declaration must not manufacture ambiguity either.
        path = self.implementation()
        result = self.resolve()
        self.assertEqual(tuple(result.diagnostics), ())
        self.assertEqual([(c.implementation_type.qualified_name,
                           c.implementation_type.source_path, c.certainty)
                          for c in result.connections],
                         [('adapters.HttpProductGateway', path, 'possible')])

    def test_generic_interface_is_unresolved_not_a_possible_connection(self):
        self.interface_path = self.put('src/main/java/api/GenericGateway.java', '''package api;
public interface GenericGateway<T> {
    String lookup(String id);
}
''')
        caller = self.put('src/main/java/shop/Order.java', '''package shop;
class Order {
    api.GenericGateway gateway;
    void place(String id) { gateway.lookup(id); }
}
''')
        self.put('src/main/java/adapters/StringGateway.java', '''package adapters;
public class StringGateway implements api.GenericGateway<String> {
    public String lookup(String id) { return id; }
}
''')
        result = self.resolve()
        self.assertEqual(tuple(result.connections), ())
        self.assertEqual(len(result.diagnostics), 1)
        diagnostic = result.diagnostics[0]
        self.assertEqual(diagnostic.code, 'unsupported-interface')
        self.assertEqual(tuple(diagnostic.candidates), ())
        self.assertEqual((diagnostic.link.invocation.source_path,
                          diagnostic.link.invocation.line), (caller, 4))
        self.assertEqual((diagnostic.link.target_method.source_path,
                          diagnostic.link.target_method.line), (self.interface_path, 3))
        self.assertIn('api.GenericGateway', diagnostic.message)
        self.assertIn('generic', diagnostic.message.lower())

    def test_declarations_without_invocation_do_not_create_possible_connections(self):
        self.base('')
        self.implementation()
        result = self.resolve()
        self.assertEqual(tuple(result.connections), ())
        self.assertEqual(tuple(result.diagnostics), ())

    def test_feign_is_terminal_even_if_a_local_implementation_is_visible(self):
        self.base('')
        self.implementation()
        self.put('src/main/java/adapters/LocalClient.java', '''package adapters;
public class LocalClient implements remote.ProductClient {
    public String getProduct(String id) { return id; }
}
''')
        result = self.resolve()
        self.assertEqual(tuple(result.connections), ())
        self.assertEqual(tuple(result.diagnostics), ())
        self.assertEqual([link.target_type for link in resolve_calls(self.module).links],
                         ['remote.ProductClient'])

    def test_multiple_call_sites_keep_evidence_and_resolution_is_read_only_and_stable(self):
        self.base('gateway.lookup(id);\n        this.gateway.lookup(id);')
        self.implementation()
        paths = sorted(p for p in self.root.rglob('*') if p.is_file())
        before = {p: p.read_bytes() for p in paths}
        with patch('subprocess.run', side_effect=AssertionError('Do not run Java')), \
             patch('subprocess.Popen', side_effect=AssertionError('Do not compile Java')):
            first = self.resolve()
            second = self.resolve()
        self.assertEqual(first, second)
        self.assertEqual(tuple(first.diagnostics), ())
        self.assertEqual([(c.link.invocation.source_path, c.link.invocation.line,
                           c.certainty) for c in first.connections],
                         [(self.caller_path, 7, 'possible'), (self.caller_path, 8, 'possible')])
        self.assertEqual(sorted(p for p in self.root.rglob('*') if p.is_file()), paths)
        self.assertEqual({p: p.read_bytes() for p in paths}, before)


if __name__ == '__main__':
    unittest.main()
