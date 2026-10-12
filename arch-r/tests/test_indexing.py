"""Objective contract tests for iteration 002's source-indexing task only.

Proposed seam: archr.indexing.index_module(Module) returns an index with `types`.
Types expose qualified_name, kind ('class'/'interface'), source_path, line,
fields and methods. Fields expose name, type_name (resolved qualified name),
source_path and line. Methods expose name, parameter_count, source_path, line
and invocations. Invocations expose receiver (including an optional `this.`),
method_name, argument_count, source_path and line.

This is a source inventory, not a resolved call graph: overload selection,
interface wiring, traversal and rendered guidance belong to later tasks.
Citations use 1-based declaration/call lines and module-relative POSIX paths.
"""

import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from archr.module import AnalysisError, load_module


class SourceIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='arch_r_index_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'src/main/java').mkdir(parents=True)
        self.module = load_module(str(self.root))

    def put(self, relative, source):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')
        return path

    def index(self):
        try:
            indexing = importlib.import_module('archr.indexing')
        except ModuleNotFoundError as exc:
            if exc.name != 'archr.indexing':
                raise
            self.fail('Source indexing is not implemented: missing archr.indexing.index_module')
        return indexing.index_module(self.module)

    def types(self):
        types = self.index().types
        names = [t.qualified_name for t in types]
        self.assertEqual(len(names), len(set(names)), 'Type identities must be distinct')
        return {t.qualified_name: t for t in types}

    def test_constructor_injected_field_and_method_call_have_exact_evidence(self):
        relative = 'src/main/java/shop/OrderService.java'
        self.put(relative, '''package shop;
import remote.ProductClient;
public class OrderService {
    private final ProductClient client;
    public OrderService(ProductClient client) {
        this.client = client;
    }
    public void placeOrder(String id) {
        this.client.getProduct(id);
    }
}
''')
        self.put('src/main/java/remote/ProductClient.java',
                 'package remote; public interface ProductClient { void getProduct(String id); }')
        order = self.types()['shop.OrderService']
        self.assertEqual((order.kind, order.source_path, order.line), ('class', relative, 3))
        self.assertEqual([(f.name, f.type_name, f.source_path, f.line) for f in order.fields],
                         [('client', 'remote.ProductClient', relative, 4)])
        method = next(m for m in order.methods if m.name == 'placeOrder')
        self.assertEqual((method.parameter_count, method.source_path, method.line), (1, relative, 8))
        self.assertEqual([(c.receiver, c.method_name, c.argument_count, c.source_path, c.line)
                          for c in method.invocations],
                         [('this.client', 'getProduct', 1, relative, 9)])

    def test_package_import_and_fully_qualified_field_types_remain_distinct(self):
        self.put('src/main/java/local/Client.java', 'package local; interface Client {}')
        self.put('src/main/java/remote/Client.java', 'package remote; interface Client {}')
        self.put('src/main/java/local/SamePackage.java',
                 'package local; class SamePackage { Client client; }')
        self.put('src/main/java/caller/Imported.java',
                 'package caller; import remote.Client; class Imported { Client client; }')
        self.put('src/main/java/caller/Qualified.java',
                 'package caller; class Qualified { local.Client local; remote.Client remote; }')
        types = self.types()
        self.assertEqual(types['local.SamePackage'].fields[0].type_name, 'local.Client')
        self.assertEqual(types['caller.Imported'].fields[0].type_name, 'remote.Client')
        self.assertEqual({f.name: f.type_name for f in types['caller.Qualified'].fields},
                         {'local': 'local.Client', 'remote': 'remote.Client'})

    def test_interface_methods_include_unmapped_methods_and_overload_declarations(self):
        relative = 'src/main/java/remote/Client.java'
        self.put(relative, '''package remote;
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient(name = "products")
public interface Client {
    String lookup(String id);
    String lookup(int id);
    void refresh();
    void refresh(String id, int count);
}
''')
        client = self.types()['remote.Client']
        self.assertEqual((client.kind, client.source_path, client.line), ('interface', relative, 4))
        self.assertEqual(sorted((m.name, m.parameter_count, m.source_path, m.line)
                                for m in client.methods),
                         [('lookup', 1, relative, 5), ('lookup', 1, relative, 6),
                          ('refresh', 0, relative, 7), ('refresh', 2, relative, 8)])
        self.assertTrue(all(not m.invocations for m in client.methods))

    def test_invocations_are_owned_by_method_and_keep_all_call_sites(self):
        relative = 'src/main/java/shop/Gateway.java'
        self.put(relative, '''package shop;
class Gateway {
    remote.Client client;
    void lookup(String id) {
        client.getProduct(id);
        this.client.getProduct(id);
        client.batch("a,b", nested(1, 2));
        client.refresh();
    }
    void health() {}
}
''')
        gateway = self.types()['shop.Gateway']
        lookup = next(m for m in gateway.methods if m.name == 'lookup')
        calls = [c for c in lookup.invocations if c.receiver in ('client', 'this.client')]
        self.assertEqual([(c.receiver, c.method_name, c.argument_count, c.source_path, c.line)
                          for c in calls],
                         [('client', 'getProduct', 1, relative, 5),
                          ('this.client', 'getProduct', 1, relative, 6),
                          ('client', 'batch', 2, relative, 7),
                          ('client', 'refresh', 0, relative, 8)])
        self.assertEqual(list(next(m for m in gateway.methods if m.name == 'health').invocations), [])

    def test_import_field_annotation_and_constructor_assignment_are_not_calls(self):
        self.put('src/main/java/shop/Holder.java', '''package shop;
import remote.Client;
@Deprecated
class Holder {
    private final Client client;
    Holder(Client client) { this.client = client; }
    void idle() {}
}
''')
        holder = self.types()['shop.Holder']
        self.assertEqual([(f.name, f.type_name) for f in holder.fields], [('client', 'remote.Client')])
        self.assertTrue(any(m.name == 'idle' for m in holder.methods))
        self.assertEqual([c for m in holder.methods for c in m.invocations], [])

    def test_comments_strings_and_text_blocks_do_not_create_declarations_or_calls(self):
        self.put('src/main/java/shop/Real.java', '''package shop;
// class Fake { remote.Client client; void run() { client.fake(); } }
/* interface Phantom { void fake(); } */
class Real {
    remote.Client client;
    void run() {
        String s = "client.fake()";
        String text = """
            class Ghost { void fake() { client.fake(); } }
            """;
        // client.fake();
        /* this.client.fake(); */
        client.real();
    }
}
''')
        types = self.types()
        self.assertEqual(set(types), {'shop.Real'})
        real = types['shop.Real']
        self.assertEqual([f.name for f in real.fields], ['client'])
        calls = [c for m in real.methods for c in m.invocations]
        self.assertEqual([(c.receiver, c.method_name, c.line) for c in calls], [('client', 'real', 13)])

    def test_class_literals_do_not_hide_calls_and_local_type_bodies_are_not_owned(self):
        relative = 'src/main/java/shop/Literals.java'
        self.put(relative, '''package shop;
class Literals {
    remote.Client client;
    void run() {
        Class<?> type = remote.Client.class;
        client.before();
        class Local {
            void run() { client.localOnly(); }
        }
        this.client.after(remote.Client.class);
        client.last();
    }
}
''')
        owner = self.types()['shop.Literals']
        method = next(m for m in owner.methods if m.name == 'run')
        self.assertEqual([(c.receiver, c.method_name, c.argument_count, c.source_path, c.line)
                          for c in method.invocations],
                         [('client', 'before', 0, relative, 6),
                          ('this.client', 'after', 1, relative, 10),
                          ('client', 'last', 0, relative, 11)])

    def test_class_literal_forms_preserve_subsequent_supported_calls(self):
        relative = 'src/main/java/shop/LiteralForms.java'
        # A literal before a block must not cause that block to be skipped as
        # though it were a local class body. Calls after it retain exact lines.
        for literal in ('Client.class', 'remote.Client.class', 'int.class',
                        'remote.Client[].class', 'int[][].class'):
            with self.subTest(literal=literal):
                self.put(relative, f'''package shop;
import remote.Client;
class LiteralForms {{
    Client client;
    void run() {{
        Class<?> type = {literal};
        if (type != null) {{
            client.inside();
        }}
        this.client.after();
    }}
    void later() {{ client.later(); }}
}}
''')
                owner = self.types()['shop.LiteralForms']
                self.assertEqual([(m.name, m.parameter_count, m.line)
                                  for m in owner.methods],
                                 [('run', 0, 5), ('later', 0, 12)])
                self.assertEqual([(c.receiver, c.method_name, c.argument_count,
                                   c.source_path, c.line)
                                  for c in owner.methods[0].invocations],
                                 [('client', 'inside', 0, relative, 8),
                                  ('this.client', 'after', 0, relative, 10)])
                self.assertEqual([(c.receiver, c.method_name, c.line)
                                  for c in owner.methods[1].invocations],
                                 [('client', 'later', 12)])

    def test_class_literals_in_arguments_do_not_hide_nested_or_following_calls(self):
        relative = 'src/main/java/shop/LiteralArguments.java'
        self.put(relative, '''package shop;
class LiteralArguments {
    remote.Client client;
    void run() {
        this.client.inspect(remote.Client.class, client.prepare());
        client.inspect(int[].class, remote.Client.class);
        client.finish();
    }
}
''')
        owner = self.types()['shop.LiteralArguments']
        method = next(m for m in owner.methods if m.name == 'run')
        self.assertEqual([(c.receiver, c.method_name, c.argument_count, c.source_path, c.line)
                          for c in method.invocations],
                         [('this.client', 'inspect', 2, relative, 5),
                          ('client', 'prepare', 0, relative, 5),
                          ('client', 'inspect', 2, relative, 6),
                          ('client', 'finish', 0, relative, 7)])

    def test_anonymous_bodies_are_not_owned_but_constructor_arguments_and_trailing_calls_are(self):
        relative = 'src/main/java/shop/Anonymous.java'
        self.put(relative, '''package shop;
class Anonymous {
    remote.Client client;
    void run() {
        Object worker = new Worker(client.prepare(), new Worker(client.nestedArgument()) {
            { client.nestedInitializer(); }
            public void work() { client.nestedBody(); }
        }) {
            { client.initializerOnly(); }
            public void work() {
                client.bodyOnly();
                Object nested = new Worker(client.bodyArgument()) {
                    public void work() { client.deepBody(); }
                };
            }
        };
        this.client.after();
    }
}
''')
        owner = self.types()['shop.Anonymous']
        method = next(m for m in owner.methods if m.name == 'run')
        self.assertEqual([(c.receiver, c.method_name, c.argument_count, c.source_path, c.line)
                          for c in method.invocations],
                         [('client', 'prepare', 0, relative, 5),
                          ('client', 'nestedArgument', 0, relative, 5),
                          ('this.client', 'after', 0, relative, 17)])

    def test_anonymous_field_initializers_preserve_fields_and_member_ownership(self):
        relative = 'src/main/java/shop/Holder.java'
        self.put(relative, '''package shop;
import remote.Client;
class Holder {
    final Client first = new Client() {
        public void lookup() { first.initializerBody(); }
    }, second = null;
    remote.Client third;
    void run() {
        second.lookup();
        this.third.refresh();
    }
}
''')
        holder = self.types()['shop.Holder']
        self.assertEqual([(f.name, f.type_name, f.source_path, f.line)
                          for f in holder.fields],
                         [('first', 'remote.Client', relative, 4),
                          ('second', 'remote.Client', relative, 4),
                          ('third', 'remote.Client', relative, 7)])
        self.assertEqual([(m.name, m.parameter_count, m.source_path, m.line)
                          for m in holder.methods], [('run', 0, relative, 8)])
        self.assertEqual([(c.receiver, c.method_name, c.argument_count, c.source_path, c.line)
                          for c in holder.methods[0].invocations],
                         [('second', 'lookup', 0, relative, 9),
                          ('this.third', 'refresh', 0, relative, 10)])

    def test_named_annotation_arguments_do_not_hide_method_declarations(self):
        relative = 'src/main/java/shop/Annotated.java'
        self.put(relative, '''package shop;
class Annotated {
    remote.Client client;
    @Mapping(value = "/lookup", tags = {"a", "b"})
    public void lookup(String id, int count) {
        client.lookup(id, count);
    }
    @Mapping(value = "/refresh")
    public void refresh() {
        this.client.refresh();
    }
}
''')
        owner = self.types()['shop.Annotated']
        self.assertEqual([(m.name, m.parameter_count, m.source_path, m.line)
                          for m in owner.methods],
                         [('lookup', 2, relative, 4), ('refresh', 0, relative, 8)])
        self.assertEqual([(c.receiver, c.method_name, c.argument_count, c.source_path, c.line)
                          for m in owner.methods for c in m.invocations],
                         [('client', 'lookup', 2, relative, 6),
                          ('this.client', 'refresh', 0, relative, 10)])

    def test_java_only_module_boundary_stability_and_read_only_analysis(self):
        self.put('src/main/java/z/Z.java', 'package z; class Z {}')
        self.put('src/main/java/a/A.java', 'package a; class A {}')
        for relative in ('src/main/java/Ignored.txt', 'src/test/java/Test.java',
                         'target/generated-sources/Generated.java', 'other/Other.java'):
            self.put(relative, 'package excluded; class Outside {}')
        outside = self.put('outside/External.java', 'package outside; class External {}')
        (self.module.source_root / 'Link.java').symlink_to(outside)
        (self.module.source_root / 'linked').symlink_to(outside.parent, target_is_directory=True)
        before = {p.relative_to(self.root): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file()}
        # Indexing must not launch javac, Maven, Java, or any other subprocess.
        with patch('subprocess.Popen', side_effect=AssertionError('Source analysis must not execute tools')), \
             patch('os.system', side_effect=AssertionError('Source analysis must not execute tools')):
            first = self.index()
            second = self.index()
        self.assertEqual({t.qualified_name for t in first.types}, {'a.A', 'z.Z'})
        self.assertEqual([t.source_path for t in first.types],
                         ['src/main/java/a/A.java', 'src/main/java/z/Z.java'])
        self.assertEqual(first, second)
        after = {p.relative_to(self.root): p.read_bytes()
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_invalid_encoding_is_an_analysis_error(self):
        (self.module.source_root / 'Broken.java').write_bytes(b'\xff')
        with self.assertRaises(AnalysisError):
            self.index()

    def test_unreadable_source_or_directory_is_an_analysis_error(self):
        path = self.put('src/main/java/nested/A.java', 'class A {}')
        for target in (path, path.parent):
            with self.subTest(target=target):
                mode = target.stat().st_mode
                try:
                    target.chmod(0)
                    with self.assertRaises(AnalysisError):
                        self.index()
                finally:
                    target.chmod(mode)


if __name__ == '__main__':
    unittest.main()
