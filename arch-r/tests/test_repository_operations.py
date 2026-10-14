"""Known repository endpoints do not require a local implementation."""

from pathlib import Path
import tempfile
import unittest

from archr.findings import discover_findings
from archr.indexing import index_source
from archr.interfaces import resolve_interface_index
from archr.module import load_module
from archr.resolution import REPOSITORY_OPERATIONS, resolve_index
from archr.traversal import trace_usage


class RepositoryOperationTests(unittest.TestCase):
    prefix = '''package shop;
interface Orders extends org.springframework.data.jpa.repository.JpaRepository<Order, Long> {
    Order findByCode(String code);
}
'''

    def resolve(self, body):
        index = index_source(self.prefix + body, 'src/main/java/shop/Gateway.java')
        return index, resolve_index(index)

    def test_inherited_and_declared_operations_on_both_receiver_forms(self):
        calls = ''.join(f'orders.{name}(); this.orders.{name}();'
                        for name in sorted(REPOSITORY_OPERATIONS | {'findByCode'}))
        # Declared methods retain name/arity matching; inherited endpoints do
        # not purport to validate Java overloads without the library source.
        calls = calls.replace('findByCode()', 'findByCode("code")')
        index, resolution = self.resolve(
            'class Gateway { Orders orders; void run() { ' + calls + ' } }')
        self.assertEqual(len(resolution.links), 20)
        self.assertEqual(resolution.diagnostics, ())
        self.assertTrue(all(link.target_type == 'shop.Orders' for link in resolution.links))
        self.assertEqual(resolve_interface_index(index).diagnostics, ())

    def test_inherited_operations_with_realistic_arguments_and_qualified_fields(self):
        _, result = self.resolve('''
class Gateway {
    shop.Orders orders;
    Gateway(shop.Orders orders) { this.orders = orders; }
    void run() {
        orders.save(null); this.orders.saveAll(null);
        orders.findById(1L); this.orders.findAll();
        orders.existsById(1L); this.orders.count();
        orders.delete(null); this.orders.deleteById(1L); orders.deleteAll();
    }
}
''')
        self.assertEqual(result.diagnostics, ())
        self.assertEqual({link.invocation.method_name for link in result.links},
                         REPOSITORY_OPERATIONS)
        self.assertEqual(len(result.links), 9)
        for link in result.links:
            self.assertEqual(link.receiver_field.name, 'orders')
            self.assertEqual(link.target_type, 'shop.Orders')
            self.assertEqual(link.target_method.parameter_count,
                             link.invocation.argument_count)

    def test_unknown_object_shadowed_and_indirect_calls_are_not_endpoints(self):
        _, resolution = self.resolve('''
interface Indirect extends Orders {}
class Gateway {
    Orders orders; Indirect indirect;
    void run(Orders orders) {
        orders.save(null); this.orders.toString(); this.orders.equals(null);
        this.orders.hashCode(); this.orders.unknown(); indirect.save(null);
        this.orders.save(null);
    }
}
''')
        self.assertEqual(len(resolution.links), 1)
        self.assertEqual(resolution.links[0].invocation.receiver, 'this.orders')
        self.assertEqual(len(resolution.diagnostics), 6)

    def test_declared_overload_ambiguity_is_not_guessed(self):
        index = index_source(self.prefix.replace(
            'Order findByCode(String code);',
            'Order findByCode(String code); Order findByCode(Long code);') +
            'class Gateway { Orders orders; void run() { orders.findByCode(null); } }',
            'src/main/java/shop/Gateway.java')
        result = resolve_index(index)
        self.assertEqual(result.links, ())
        self.assertEqual(result.diagnostics[0].code, 'ambiguous-overload')

    def test_redeclared_inherited_operation_retains_source_endpoint(self):
        index = index_source(self.prefix.replace(
            'Order findByCode(String code);',
            'Order save(Order entity);') +
            'class Gateway { Orders orders; void run() { orders.save(null); } }',
            'src/main/java/shop/Gateway.java')
        result = resolve_index(index)
        link, = result.links
        repository = next(item for item in index.types
                          if item.qualified_name == 'shop.Orders')
        self.assertEqual(link.target_method, repository.methods[0])
        self.assertEqual(result.diagnostics, ())

    def test_known_inherited_name_does_not_override_declared_ambiguity(self):
        index = index_source(self.prefix.replace(
            'Order findByCode(String code);',
            'Order save(Order entity); Order save(Other entity);') +
            'class Gateway { Orders orders; void run() { orders.save(null); } }',
            'src/main/java/shop/Gateway.java')
        result = resolve_index(index)
        self.assertEqual(result.links, ())
        diagnostic, = result.diagnostics
        self.assertEqual(diagnostic.code, 'ambiguous-overload')
        self.assertEqual(len(diagnostic.candidates), 2)

    def test_declared_repository_operation_requires_matching_arity(self):
        _, result = self.resolve(
            'class Gateway { Orders orders; void run() { orders.findByCode(); } }')
        self.assertEqual(result.links, ())
        diagnostic, = result.diagnostics
        self.assertEqual(diagnostic.code, 'unresolved-method')
        self.assertEqual(diagnostic.receiver_field.name, 'orders')

    def test_shared_finding_and_method_continuous_two_step_chains(self):
        source = self.prefix + '''
class Gateway {
    Orders first; Orders second;
    void store() { first.save(null); this.second.findByCode("code"); }
    void unrelated() { first.toString(); }
}
class Service {
    Gateway gateway;
    void place() { gateway.store(); }
    void other() { gateway.unrelated(); }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'src/main/java/shop/Gateway.java'
            path.parent.mkdir(parents=True)
            path.write_text(source)
            module = load_module(directory)
            before = path.read_bytes()
            finding, = discover_findings(module)
            self.assertEqual(finding.declaration.declaring_type, 'shop.Orders')
            self.assertTrue(finding.has_supported_caller)
            self.assertEqual(finding.destination.label, 'Destination unknown')
            self.assertEqual({op.method_name for op in finding.operations},
                             {'save', 'findByCode'})
            self.assertEqual(len(finding.chains), 2)
            for chain in finding.chains:
                self.assertEqual([s.link.caller_method.name for s in chain.steps],
                                 ['store', 'place'])
                self.assertEqual(chain.certainty, 'observed')
            self.assertEqual(trace_usage(module).interface_diagnostics, ())
            self.assertEqual(finding, discover_findings(module)[0])
            self.assertEqual(before, path.read_bytes())

    def test_explicit_imports_across_files_and_possible_upstream_interface(self):
        sources = {
            'shop/Orders.java': '''package shop;
import org.springframework.data.jpa.repository.JpaRepository;
interface Orders extends JpaRepository<Order, Long> { Order findByCode(String code); }
''',
            'shop/Gateway.java': '''package shop;
interface Store { void store(); }
class Gateway implements Store {
    Orders orders;
    public void store() { this.orders.save(null); }
    void unrelated() { orders.hashCode(); }
}
''',
            'shop/Service.java': '''package shop;
class Service { Store store; void place() { store.store(); } }
''',
        }
        with tempfile.TemporaryDirectory() as directory:
            for name, source in sources.items():
                path = Path(directory) / 'src/main/java' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding='utf-8')
            finding, = discover_findings(load_module(directory))
            self.assertEqual(finding.declaration.declaring_type, 'shop.Orders')
            self.assertEqual(len(finding.operations), 1)
            self.assertEqual(finding.operations[0].method_name, 'save')
            chain, = finding.chains
            self.assertEqual([step.link.caller_method.name for step in chain.steps],
                             ['store', 'place'])
            self.assertEqual(chain.certainty, 'possible')
            self.assertIsNotNone(chain.steps[1].interface_connection)
            self.assertEqual(chain.steps[0].link.receiver_field.name, 'orders')
            self.assertEqual(finding.destination.label, 'Destination unknown')

    def test_declaring_object_methods_does_not_make_them_persistence_calls(self):
        index = index_source(self.prefix.replace(
            'Order findByCode(String code);',
            'String toString(); boolean equals(Object other); int hashCode();') +
            'class Gateway { Orders orders; void run() { '
            'orders.toString(); orders.equals(null); orders.hashCode(); } }',
            'src/main/java/shop/Gateway.java')
        result = resolve_index(index)
        self.assertEqual(result.links, ())
        self.assertEqual([item.code for item in result.diagnostics],
                         ['unsupported-operation'] * 3)

    def test_multiple_repository_types_keep_calls_with_their_declarations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'src/main/java/shop/Gateway.java'
            path.parent.mkdir(parents=True)
            path.write_text(self.prefix + '''
interface Customers extends org.springframework.data.jpa.repository.JpaRepository<Customer, Long> {}
class Gateway {
    Orders first; Orders second; Customers customers;
    void store() { first.save(null); second.findAll(); customers.count(); }
}
''', encoding='utf-8')
            findings = {finding.declaration.declaring_type: finding
                        for finding in discover_findings(load_module(directory))}
            self.assertEqual(set(findings), {'shop.Orders', 'shop.Customers'})
            self.assertEqual({op.method_name for op in findings['shop.Orders'].operations},
                             {'save', 'findAll'})
            self.assertEqual({op.method_name for op in findings['shop.Customers'].operations},
                             {'count'})
            self.assertEqual({chain.steps[0].link.receiver_field.name
                              for chain in findings['shop.Orders'].chains},
                             {'first', 'second'})
            self.assertTrue(all(finding.destination.value is None
                                for finding in findings.values()))

    def test_upstream_branches_do_not_duplicate_operation_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'src/main/java/shop/Gateway.java'
            path.parent.mkdir(parents=True)
            path.write_text(self.prefix + '''
class Gateway {
    Orders orders;
    void store() { orders.save(null); this.orders.save(null); }
}
class Service {
    Gateway gateway;
    void first() { gateway.store(); }
    void second() { gateway.store(); }
}
''', encoding='utf-8')
            finding, = discover_findings(load_module(directory))
            # Two same-line integration sites, each with two upstream routes.
            self.assertEqual(len(finding.chains), 4)
            self.assertEqual(len(finding.operations), 2)
            self.assertEqual(len({operation.invocation.site_identity
                                  for operation in finding.operations}), 2)
            self.assertEqual(len(finding.supported_call_evidence), 1)
            for operation in finding.operations:
                self.assertEqual(operation.method_name, 'save')
                self.assertEqual(operation.evidence[0].source_path,
                                 'src/main/java/shop/Gateway.java')
                self.assertEqual(operation.evidence[0].line,
                                 operation.invocation.line)
                self.assertIsNone(operation.destination.value)
                self.assertIsNone(operation.http_method)

    def test_local_shadowing_and_explicit_generic_calls_remain_outside_scope(self):
        _, result = self.resolve('''
class Gateway {
    Orders orders;
    void run() {
        Orders orders = null;
        orders.save(null);
        this.orders.<Order>save(null);
        this.orders.save(null);
    }
}
''')
        self.assertEqual(len(result.links), 1)
        self.assertEqual(result.links[0].invocation.receiver, 'this.orders')
        self.assertEqual(result.links[0].invocation.method_name, 'save')
        self.assertEqual({item.code for item in result.diagnostics},
                         {'unsupported-receiver', 'unsupported-syntax'})
        self.assertEqual(len(result.diagnostics), 2)

    def test_unrelated_source_repository_is_not_a_library_endpoint(self):
        index = index_source('''package shop;
interface JpaRepository<T, ID> {}
interface Orders extends JpaRepository<Order, Long> {}
class Gateway { Orders orders; void run() { orders.save(null); } }
''', 'src/main/java/shop/Gateway.java')
        result = resolve_index(index)
        self.assertEqual(result.links, ())
        self.assertEqual(len(result.diagnostics), 1)
        self.assertEqual(result.diagnostics[0].code, 'unresolved-method')

    def test_source_defined_spring_parent_does_not_enable_repository_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            sources = {
                'org/springframework/data/jpa/repository/JpaRepository.java': '''
package org.springframework.data.jpa.repository;
interface JpaRepository<T, ID> {}
''',
                'shop/Gateway.java': self.prefix + '''
class Gateway { Orders orders; void store() { this.orders.save(null); } }
''',
            }
            for name, source in sources.items():
                path = Path(directory) / 'src/main/java' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding='utf-8')
            module = load_module(directory)
            usage = trace_usage(module)
            self.assertEqual(usage.chains, ())
            self.assertEqual([item.code for item in usage.diagnostics],
                             ['unresolved-method'])
            self.assertEqual(discover_findings(module), ())

    def test_ambiguous_repository_type_does_not_create_library_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            sources = {
                'First.java': self.prefix,
                'Second.java': self.prefix,
                'Gateway.java': '''package shop;
class Gateway { Orders orders; void store() { orders.save(null); } }
''',
            }
            for name, source in sources.items():
                path = Path(directory) / 'src/main/java/shop' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding='utf-8')
            module = load_module(directory)
            usage = trace_usage(module)
            self.assertEqual(usage.chains, ())
            self.assertEqual([item.code for item in usage.diagnostics],
                             ['unresolved-type'])
            finding, = discover_findings(module)
            self.assertEqual(finding.operations, ())
            self.assertEqual(finding.status_label,
                             'Declared integration — No supported caller found')

    def test_known_operation_names_do_not_enable_general_inherited_resolution(self):
        index = index_source('''package shop;
interface Parent { void save(Object entity); }
interface Ordinary extends Parent {}
class Gateway { Ordinary ordinary; void run() { ordinary.save(null); } }
''', 'src/main/java/shop/Gateway.java')
        result = resolve_index(index)
        self.assertEqual(result.links, ())
        self.assertEqual([item.code for item in result.diagnostics],
                         ['unresolved-method'])

    def test_repository_does_not_resolve_custom_inherited_methods(self):
        index = index_source('''package shop;
interface CustomQueries { Order findSpecial(String code); }
interface Orders extends org.springframework.data.jpa.repository.JpaRepository<Order, Long>, CustomQueries {}
class Gateway {
    Orders orders;
    void run() { orders.findSpecial("code"); this.orders.save(null); }
}
''', 'src/main/java/shop/Gateway.java')
        result = resolve_index(index)
        link, = result.links
        self.assertEqual(link.invocation.method_name, 'save')
        self.assertEqual(link.target_type, 'shop.Orders')
        diagnostic, = result.diagnostics
        self.assertEqual(diagnostic.code, 'unresolved-method')
        self.assertEqual(diagnostic.invocation.method_name, 'findSpecial')
        self.assertEqual(diagnostic.receiver_field.name, 'orders')
        self.assertEqual(resolve_interface_index(index).diagnostics, ())

    def test_declared_repository_method_keeps_source_endpoint_without_sql_inference(self):
        source = self.prefix.replace('findByCode', 'deleteByStatus') + '''
class Gateway {
    Orders orders;
    void purge() { this.orders.deleteByStatus("expired"); }
}
'''
        index = index_source(source, 'src/main/java/shop/Gateway.java')
        result = resolve_index(index)
        link, = result.links
        repository = next(item for item in index.types
                          if item.qualified_name == 'shop.Orders')
        self.assertEqual(link.target_method, repository.methods[0])
        self.assertEqual(link.invocation.method_name, 'deleteByStatus')
        self.assertEqual(result.diagnostics, ())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'src/main/java/shop/Gateway.java'
            path.parent.mkdir(parents=True)
            path.write_text(source, encoding='utf-8')
            finding, = discover_findings(load_module(directory))
            operation, = finding.operations
            self.assertEqual(operation.method_name, 'deleteByStatus')
            self.assertEqual(operation.evidence[0].line, link.invocation.line)
            self.assertIsNone(operation.http_method)
            self.assertIsNone(operation.destination.value)
            self.assertEqual(finding.destination.label, 'Destination unknown')
            self.assertEqual(len(finding.chains), 1)
            self.assertEqual(len(finding.chains[0].steps), 1)

    def test_repository_is_terminal_even_with_multiple_local_implementations(self):
        source = self.prefix + '''
class First implements Orders {
    public Order findByCode(String code) { return null; }
}
class Second implements Orders {
    public Order findByCode(String code) { return null; }
}
class Gateway {
    Orders orders;
    void lookup() { orders.findByCode("code"); }
}
'''
        index = index_source(source, 'src/main/java/shop/Gateway.java')
        interfaces = resolve_interface_index(index)
        self.assertEqual(interfaces.connections, ())
        self.assertEqual(interfaces.diagnostics, ())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'src/main/java/shop/Gateway.java'
            path.parent.mkdir(parents=True)
            path.write_text(source, encoding='utf-8')
            finding, = discover_findings(load_module(directory))
            chain, = finding.chains
            self.assertEqual(chain.certainty, 'observed')
            self.assertEqual(len(chain.steps), 1)
            self.assertEqual(chain.steps[0].link.target_type, 'shop.Orders')
            self.assertIsNone(chain.steps[0].interface_connection)
            self.assertEqual(finding.operations[0].method_name, 'findByCode')

    def test_inherited_endpoint_cites_repository_but_operation_cites_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'src/main/java'
            repository = root / 'data/Orders.java'
            repository.parent.mkdir(parents=True)
            repository.write_text('''package data;
import org.springframework.data.jpa.repository.JpaRepository;
interface Orders extends JpaRepository<Order, Long> {}
''', encoding='utf-8')
            gateway = root / 'shop/Gateway.java'
            gateway.parent.mkdir(parents=True)
            gateway.write_text('''package shop;
import data.Orders;
class Gateway {
    Orders orders;
    void store() {
        this.orders.save(null);
    }
}
''', encoding='utf-8')
            finding, = discover_findings(load_module(directory))
            chain, = finding.chains
            link = chain.steps[0].link
            self.assertEqual(link.target_type, 'data.Orders')
            self.assertEqual(link.target_method.source_path,
                             'src/main/java/data/Orders.java')
            self.assertEqual(link.target_method.line, 3)
            self.assertEqual(link.receiver_field.type_name, 'data.Orders')
            self.assertEqual(link.receiver_field.line, 4)
            operation, = finding.operations
            self.assertEqual(operation.evidence[0].source_path,
                             'src/main/java/shop/Gateway.java')
            self.assertEqual(operation.evidence[0].line, 6)
            self.assertEqual(operation.invocation, link.invocation)
            self.assertEqual(finding.declaration_evidence.line, 3)
            self.assertEqual(finding.destination.label, 'Destination unknown')

    def test_fields_in_separate_classes_share_repository_finding(self):
        with tempfile.TemporaryDirectory() as directory:
            sources = {
                'data/Orders.java': '''package data;
import org.springframework.data.jpa.repository.JpaRepository;
interface Orders extends JpaRepository<Order, Long> {}
''',
                'shop/Writer.java': '''package shop;
import data.Orders;
class Writer {
    Orders writes;
    void store() { this.writes.save(null); }
    void unrelated() { writes.toString(); }
}
''',
                'shop/Reader.java': '''package shop;
class Reader {
    data.Orders reads;
    void load() { reads.findAll(); }
}
''',
                'shop/Service.java': '''package shop;
class Service {
    Writer writer; Reader reader;
    void place() { writer.store(); }
    void list() { reader.load(); }
    void other() { writer.unrelated(); }
}
''',
            }
            for name, source in sources.items():
                path = Path(directory) / 'src/main/java' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding='utf-8')
            finding, = discover_findings(load_module(directory))
            self.assertEqual(finding.declaration.declaring_type, 'data.Orders')
            self.assertEqual({operation.method_name for operation in finding.operations},
                             {'save', 'findAll'})
            self.assertEqual({tuple(step.link.caller_method.name for step in chain.steps)
                              for chain in finding.chains},
                             {('store', 'place'), ('load', 'list')})
            self.assertEqual({chain.steps[0].link.receiver_field.name
                              for chain in finding.chains}, {'writes', 'reads'})
            self.assertTrue(all(chain.certainty == 'observed'
                                for chain in finding.chains))
            self.assertEqual(finding.destination.label, 'Destination unknown')

    def test_unknown_operation_does_not_hide_supported_calls_or_create_a_caller(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'src/main/java/shop/Gateway.java'
            path.parent.mkdir(parents=True)
            path.write_text(self.prefix + '''
interface Customers extends org.springframework.data.jpa.repository.JpaRepository<Customer, Long> {}
class Gateway {
    Orders orders; Customers customers;
    void store() { orders.unknown(); this.orders.save(null); }
    void unrelated() { customers.unknown(); }
}
''', encoding='utf-8')
            module = load_module(directory)
            findings = {finding.declaration.declaring_type: finding
                        for finding in discover_findings(module)}
            orders = findings['shop.Orders']
            self.assertTrue(orders.has_supported_caller)
            operation, = orders.operations
            self.assertEqual(operation.method_name, 'save')
            chain, = orders.chains
            self.assertEqual(chain.steps[0].link.caller_method.name, 'store')
            customers = findings['shop.Customers']
            self.assertEqual(customers.status_label,
                             'Declared integration — No supported caller found')
            self.assertEqual(customers.operations, ())
            self.assertEqual(customers.chains, ())
            self.assertEqual(customers.destination.label, 'Destination unknown')
            usage = trace_usage(module)
            self.assertEqual([item.code for item in usage.diagnostics],
                             ['unresolved-method', 'unresolved-method'])
            self.assertEqual(usage.interface_diagnostics, ())
            self.assertEqual(len(usage.untraced_sites), 2)

    def test_repository_and_feign_roots_remain_separate(self):
        source = '''package shop;
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient(name = "products") interface Products { String fetch(); }
interface Orders extends org.springframework.data.jpa.repository.JpaRepository<Order, Long> {}
class Gateway {
    Products products; Orders orders;
    void fetch() { products.fetch(); }
    void store() { this.orders.save(null); }
}
class Service {
    Gateway gateway;
    void browse() { gateway.fetch(); }
    void place() { gateway.store(); }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'src/main/java/shop/Gateway.java'
            path.parent.mkdir(parents=True)
            path.write_text(source, encoding='utf-8')
            module = load_module(directory)
            usage = trace_usage(module)
            self.assertEqual({(chain.client_type,
                               tuple(step.link.caller_method.name for step in chain.steps))
                              for chain in usage.chains},
                             {('shop.Products', ('fetch', 'browse')),
                              ('shop.Orders', ('store', 'place'))})
            repository, = (finding for finding in discover_findings(module)
                           if finding.declaration.mechanism == 'Spring Data JPA')
            self.assertEqual([operation.method_name for operation in repository.operations],
                             ['save'])
            self.assertEqual(len(repository.chains), 1)
            self.assertEqual(repository.chains[0].client_type, 'shop.Orders')
            self.assertEqual(repository.destination.label, 'Destination unknown')

    def test_only_unknown_calls_keep_no_caller_label(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'src/main/java/shop/Gateway.java'
            path.parent.mkdir(parents=True)
            path.write_text(self.prefix +
                            'class Gateway { Orders orders; void run() { orders.toString(); } }')
            finding, = discover_findings(load_module(directory))
            self.assertEqual(finding.status_label,
                             'Declared integration — No supported caller found')
            self.assertEqual(finding.operations, ())


if __name__ == '__main__':
    unittest.main()
