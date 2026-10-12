"""Regression contracts for generic commas in ordinary field-call arguments.

Java fixtures are source-only: the tests neither compile nor execute them.
Generic expressions must not invent additional arguments or resolve an
otherwise ambiguous/missing overload. Generic receiver resolution is not
required by these tests.
"""

from pathlib import Path
import tempfile
import unittest

from archr.module import load_module
from archr.resolution import resolve_calls


class GenericArgumentArityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='arch_r_generic_arity_')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'src/main/java').mkdir(parents=True)
        self.module = load_module(str(self.root))
        self.put('src/main/java/shop/Values.java', '''package shop;
class Pair<A, B> {
    Pair() {}
    Pair(Object first, Object second) {}
}
class Box {
    <A, B> Box() {}
}
class Factory {
    static <A, B> Object create() { return null; }
}
''')

    def put(self, relative, source):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')
        return relative

    def fixture(self, declarations, arguments):
        client_path = self.put('src/main/java/remote/Client.java',
                               'package remote;\npublic interface Client {\n' +
                               declarations + '\n}\n')
        caller_path = self.put('src/main/java/shop/Caller.java', f'''package shop;
class Caller {{
    remote.Client client;
    void run() {{
        this.client.lookup({arguments});
    }}
}}
''')
        return client_path, caller_path

    def assert_call_evidence(self, invocation, path, arity):
        self.assertEqual((invocation.receiver, invocation.method_name,
                          invocation.argument_count, invocation.source_path,
                          invocation.line),
                         ('this.client', 'lookup', arity, path, 5))

    def test_generic_comma_cannot_create_a_link_to_only_two_argument_method(self):
        for expression in ('new Pair<String, Integer>()',
                           'new <String, Integer>Box()',
                           'new Pair<String, java.util.Map<Integer, Long>>()'):
            with self.subTest(expression=expression):
                _, caller = self.fixture('    void lookup(Object a, Object b);', expression)
                result = resolve_calls(self.module)
                self.assertEqual(result.links, ())
                self.assertEqual(len(result.diagnostics), 1)
                diagnostic = result.diagnostics[0]
                self.assertEqual(diagnostic.code, 'unresolved-method')
                self.assert_call_evidence(diagnostic.invocation, caller, 1)
                self.assertTrue(diagnostic.message.strip())

    def test_generic_argument_preserves_same_arity_ambiguity_not_wrong_overload(self):
        client, caller = self.fixture('''    void lookup(Object value);
    void lookup(java.io.Serializable value);
    void lookup(Object first, Object second);''',
                                      'new Pair<String, Integer>()')
        result = resolve_calls(self.module)
        self.assertEqual(result.links, ())
        self.assertEqual(len(result.diagnostics), 1)
        diagnostic = result.diagnostics[0]
        self.assertEqual(diagnostic.code, 'ambiguous-overload')
        self.assert_call_evidence(diagnostic.invocation, caller, 1)
        self.assertEqual([(m.parameter_count, m.source_path, m.line)
                          for m in diagnostic.candidates],
                         [(1, client, 3), (1, client, 4)])
        self.assertTrue(diagnostic.message.strip())

    def test_multiple_generic_arguments_select_exact_three_argument_endpoint(self):
        expressions = (
            'new Pair<String, Integer>(), new <String, Integer>Box(), "a,b"',
            'new Pair<String, java.util.Map<Integer, Long>>(), "a,b", '
            'new Pair<Integer, Long>(1, 2)',
            '1 < 2, new Pair<String, Integer>(), 3 > 2',
        )
        for arguments in expressions:
            with self.subTest(arguments=arguments):
                client, caller = self.fixture('''    void lookup(Object value);
    void lookup(Object first, Object second);
    void lookup(Object first, Object second, Object third);''', arguments)
                before = {p: p.read_bytes() for p in self.root.rglob('*.java')}
                result = resolve_calls(self.module)
                self.assertEqual(result.diagnostics, ())
                self.assertEqual(len(result.links), 1)
                link = result.links[0]
                self.assert_call_evidence(link.invocation, caller, 3)
                self.assertEqual((link.target_type, link.target_method.name,
                                  link.target_method.parameter_count,
                                  link.target_method.source_path, link.target_method.line),
                                 ('remote.Client', 'lookup', 3, client, 5))
                self.assertEqual(result, resolve_calls(self.module))
                self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*.java')})

    def test_generic_method_argument_does_not_invent_matching_outer_overload(self):
        _, caller = self.fixture('    void lookup(Object first, Object second);',
                                 'Factory.<String, java.util.Map<Integer, Long>>create()')
        result = resolve_calls(self.module)
        self.assertEqual(result.links, ())
        # Diagnostic policy for the nested generic call is a later pending task.
        # Here only the enclosing ordinary field invocation is under test.
        outer = [d for d in result.diagnostics
                 if d.invocation.receiver == 'this.client']
        self.assertEqual(len(outer), 1)
        self.assertEqual(outer[0].code, 'unresolved-method')
        self.assert_call_evidence(outer[0].invocation, caller, 1)


if __name__ == '__main__':
    unittest.main()
