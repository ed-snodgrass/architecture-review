"""Evidence contracts for explicit generic calls, not generic dispatch support.

Fixtures are analyzed as source only; no Java compilation or execution occurs.
"""

from pathlib import Path
import tempfile
import unittest

from archr.indexing import index_module
from archr.module import load_module
from archr.resolution import resolve_calls


class ExplicitGenericInvocationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='arch_r_explicit_generic_')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'src/main/java/shop').mkdir(parents=True)
        self.module = load_module(str(self.root))
        self.put('Client.java', '''package shop;
interface Client {
    <A, B> Object fetch(Object value);
    <A, B> Object fetch(Object first, Object second);
    Object key();
    void accept(Object value);
}
''')

    def put(self, name, source):
        relative = 'src/main/java/shop/' + name
        (self.root / relative).write_text(source, encoding='utf-8')
        return relative

    def test_multiline_generic_call_inventory_retains_receiver_arity_and_citations(self):
        path = self.put('Caller.java', '''package shop;
class Caller {
    Client client;
    void run() {
        this.client
            .<String, java.util.Map<Integer, Long>>fetch(
                client.key(), "a,b");
        client.<String, Integer>fetch(client.key());
    }
}
''')
        index = index_module(self.module)
        caller = next(t for t in index.types if t.qualified_name == 'shop.Caller')
        method = next(m for m in caller.methods if m.name == 'run')
        self.assertEqual(
            [(i.receiver, i.method_name, i.argument_count, i.source_path,
              i.line, i.explicit_type_arguments) for i in method.invocations],
            [('this.client', 'fetch', 2, path, 5, True),
             ('client', 'key', 0, path, 7, False),
             ('client', 'fetch', 1, path, 8, True),
             ('client', 'key', 0, path, 8, False)])
        self.assertEqual(index, index_module(self.module))

    def test_nested_generic_calls_each_have_diagnostic_while_ordinary_calls_resolve(self):
        path = self.put('Caller.java', '''package shop;
class Caller {
    Client client;
    void run() {
        client.accept(client.<String, Integer>fetch(
            this.client.<String, Integer>fetch(client.key())));
    }
}
''')
        result = resolve_calls(self.module)
        self.assertEqual(
            [(link.invocation.method_name, link.invocation.argument_count,
              link.invocation.source_path, link.invocation.line)
             for link in result.links],
            [('accept', 1, path, 5), ('key', 0, path, 6)])
        self.assertEqual(
            [(d.code, d.caller_type, d.caller_method.name,
              d.invocation.receiver, d.invocation.method_name,
              d.invocation.argument_count, d.invocation.source_path,
              d.invocation.line) for d in result.diagnostics],
            [('unsupported-syntax', 'shop.Caller', 'run', 'client', 'fetch', 1, path, 5),
             ('unsupported-syntax', 'shop.Caller', 'run', 'this.client', 'fetch', 1, path, 6)])
        for diagnostic in result.diagnostics:
            self.assertTrue(diagnostic.invocation.explicit_type_arguments)
            self.assertIn('generic', diagnostic.message.lower())
            self.assertIn('not supported', diagnostic.message.lower())
            self.assertEqual(diagnostic.candidates, ())
        self.assertEqual(result, resolve_calls(self.module))

    def test_explicit_generic_same_class_helpers_do_not_become_field_connections(self):
        self.put('Caller.java', '''package shop;
class Caller {
    Client client;
    <A, B> Object helper(Object value) { return value; }
    void run() {
        this.<String, Integer>helper(client.key());
        helper(client.key());
    }
}
''')
        result = resolve_calls(self.module)
        self.assertEqual(result.diagnostics, ())
        self.assertEqual(
            [(link.target_type, link.target_method.name, link.invocation.line)
             for link in result.links],
            [('shop.Client', 'key', 6), ('shop.Client', 'key', 7)])


if __name__ == '__main__':
    unittest.main()
