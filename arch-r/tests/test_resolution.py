"""Contract tests for iteration 002's first pending task: method resolution.

Proposed seam (not implemented by these tests):
  archr.resolution.resolve_calls(Module) -> result with links and diagnostics.
Each link exposes caller_type (qualified name), caller_method (indexed Method),
receiver_field (indexed Field), target_type (qualified name), target_method
(indexed Method), and invocation (indexed Invocation). Diagnostics expose
caller_type, caller_method, invocation, code, message, and candidates (Methods).
Codes used here: ambiguous-overload, unresolved-type, unresolved-method,
unsupported-receiver, unsupported-syntax. Messages must be nonempty; their
prose is not prescribed.

A link is one supported source invocation, NOT a transitive class relationship.
Interface implementation selection, backward traversal and reports are later
plan tasks. Interface method declarations can be matched without runtime wiring.
All evidence is 1-based and module-relative. No production files are changed.
"""

import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from archr.module import load_module


class MethodResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='arch_r_resolution_')
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
            resolution = importlib.import_module('archr.resolution')
        except ModuleNotFoundError as exc:
            if exc.name != 'archr.resolution':
                raise
            self.fail('Method resolution is not implemented: missing archr.resolution.resolve_calls')
        return resolution.resolve_calls(self.module)

    @staticmethod
    def identity(link):
        return (link.caller_type, link.caller_method.name,
                link.caller_method.parameter_count, link.target_type,
                link.target_method.name, link.target_method.parameter_count)

    def client(self, methods='void lookup(String id);'):
        return self.put('src/main/java/remote/Client.java',
                        'package remote;\ninterface Client {\n    ' + methods + '\n}\n')

    def test_constructor_injected_field_forms_retain_call_and_declaration_evidence(self):
        client_path = self.client()
        caller_path = self.put('src/main/java/shop/Order.java', '''package shop;
import remote.Client;
class Order {
    private final Client client;
    Order(Client client) { this.client = client; }
    void place(String id) {
        client.lookup(id);
        this.client.lookup(id);
    }
}
''')
        result = self.resolve()
        self.assertEqual(list(result.diagnostics), [])
        self.assertEqual([self.identity(link) for link in result.links],
                         [('shop.Order', 'place', 1, 'remote.Client', 'lookup', 1)] * 2)
        self.assertEqual([(link.invocation.receiver, link.invocation.source_path,
                           link.invocation.line) for link in result.links],
                         [('client', caller_path, 7), ('this.client', caller_path, 8)])
        for link in result.links:
            self.assertEqual((link.receiver_field.name, link.receiver_field.type_name,
                              link.receiver_field.source_path, link.receiver_field.line),
                             ('client', 'remote.Client', caller_path, 4))
            self.assertEqual((link.caller_method.source_path, link.caller_method.line),
                             (caller_path, 6))
            self.assertEqual((link.target_method.source_path, link.target_method.line),
                             (client_path, 3))

    def test_package_import_and_fully_qualified_receivers_do_not_confuse_same_named_types(self):
        self.put('src/main/java/local/Client.java',
                 'package local; interface Client { void lookup(); }')
        self.put('src/main/java/remote/Client.java',
                 'package remote; interface Client { void lookup(); }')
        self.put('src/main/java/local/Same.java',
                 'package local; class Same { Client c; void run() { c.lookup(); } }')
        self.put('src/main/java/shop/Imported.java',
                 'package shop; import remote.Client; class Imported { Client c; void run() { c.lookup(); } }')
        self.put('src/main/java/shop/Qualified.java',
                 'package shop; class Qualified { local.Client a; remote.Client b; void run() { a.lookup(); b.lookup(); } }')
        result = self.resolve()
        self.assertEqual(list(result.diagnostics), [])
        self.assertEqual(sorted((link.caller_type, link.receiver_field.name, link.target_type)
                                for link in result.links),
                         [('local.Same', 'c', 'local.Client'),
                          ('shop.Imported', 'c', 'remote.Client'),
                          ('shop.Qualified', 'a', 'local.Client'),
                          ('shop.Qualified', 'b', 'remote.Client')])

    def test_name_and_argument_count_select_unique_overload(self):
        self.client('void lookup();\n    void lookup(String id);\n    void lookup(String id, int count);\n    void health(String id);')
        self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    remote.Client client;
    void run() {
        client.lookup();
        client.lookup("a,b");
        this.client.lookup("x", nested(1, 2));
    }
    int nested(int a, int b) { return 1; }
}
''')
        result = self.resolve()
        self.assertEqual(list(result.diagnostics), [])
        self.assertEqual([(link.target_method.name, link.target_method.parameter_count,
                           link.invocation.argument_count, link.invocation.line)
                          for link in result.links],
                         [('lookup', 0, 0, 5), ('lookup', 1, 1, 6), ('lookup', 2, 2, 7)])

    def test_same_arity_overloads_are_unresolved_even_with_literal_argument(self):
        client_path = self.client('void lookup(String id);\n    void lookup(int id);')
        path = self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    remote.Client client;
    void run() {
        client.lookup("known string");
    }
}
''')
        result = self.resolve()
        self.assertEqual(list(result.links), [])
        self.assertEqual(len(result.diagnostics), 1)
        diagnostic = result.diagnostics[0]
        self.assertEqual(diagnostic.code, 'ambiguous-overload')
        self.assertEqual((diagnostic.caller_type, diagnostic.caller_method.name,
                          diagnostic.invocation.source_path, diagnostic.invocation.line),
                         ('shop.Caller', 'run', path, 5))
        self.assertTrue(diagnostic.message.strip())
        self.assertEqual(sorted((m.name, m.parameter_count, m.source_path, m.line)
                                for m in diagnostic.candidates),
                         [('lookup', 1, client_path, 3), ('lookup', 1, client_path, 4)])

    def test_missing_method_and_wrong_arity_are_diagnosed_not_guessed(self):
        self.client()
        path = self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    remote.Client client;
    void run() {
        client.absent("x");
        this.client.lookup();
    }
}
''')
        result = self.resolve()
        self.assertEqual(list(result.links), [])
        self.assertEqual([(d.code, d.invocation.source_path, d.invocation.line)
                          for d in result.diagnostics],
                         [('unresolved-method', path, 5), ('unresolved-method', path, 6)])
        self.assertTrue(all(d.message.strip() for d in result.diagnostics))

    def test_missing_receiver_type_is_reported_with_actual_invocation(self):
        path = self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    missing.Client client;
    void run() {
        client.lookup("x");
    }
}
''')
        result = self.resolve()
        self.assertEqual(list(result.links), [])
        self.assertEqual(len(result.diagnostics), 1)
        diagnostic = result.diagnostics[0]
        self.assertEqual((diagnostic.code, diagnostic.invocation.source_path,
                          diagnostic.invocation.line), ('unresolved-type', path, 5))
        self.assertTrue(diagnostic.message.strip())

    def test_declarations_and_constructor_assignment_alone_create_no_links(self):
        self.client()
        self.put('src/main/java/shop/Holder.java', '''package shop;
import remote.Client;
@Deprecated
class Holder {
    final Client client;
    Holder(Client client) { this.client = client; }
    void idle() {}
}
''')
        result = self.resolve()
        self.assertEqual(list(result.links), [])
        self.assertEqual(list(result.diagnostics), [])

    def test_unrelated_intermediary_methods_remain_distinct_method_endpoints(self):
        self.client()
        self.put('src/main/java/shop/Gateway.java', '''package shop;
class Gateway {
    remote.Client client;
    void lookup(String id) { client.lookup(id); }
    void health() {}
}
''')
        self.put('src/main/java/shop/Order.java', '''package shop;
class Order {
    Gateway gateway;
    void place() { gateway.health(); }
}
''')
        result = self.resolve()
        self.assertEqual(list(result.diagnostics), [])
        self.assertEqual(sorted(self.identity(link) for link in result.links),
                         [('shop.Gateway', 'lookup', 1, 'remote.Client', 'lookup', 1),
                          ('shop.Order', 'place', 0, 'shop.Gateway', 'health', 0)])
        # Exact method endpoints prevent a subsequent traversal from treating
        # Order's call of health as a call of the Feign-calling lookup method.

    def test_same_class_helpers_are_not_expanded_into_calling_method(self):
        self.client()
        self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    remote.Client client;
    void run(String id) { helper(id); this.helper(id); }
    void helper(String id) { client.lookup(id); }
}
''')
        result = self.resolve()
        self.assertEqual([self.identity(link) for link in result.links],
                         [('shop.Caller', 'helper', 1, 'remote.Client', 'lookup', 1)])

    def test_parameter_and_local_receivers_do_not_become_field_connections(self):
        self.client()
        path = self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    remote.Client client;
    void parameter(remote.Client client) {
        client.lookup("parameter");
        this.client.lookup("field");
    }
    void local() {
        remote.Client client = null;
        client.lookup("local");
        this.client.lookup("field");
    }
}
''')
        result = self.resolve()
        self.assertEqual([(link.caller_method.name, link.invocation.receiver,
                           link.invocation.line) for link in result.links],
                         [('parameter', 'this.client', 6), ('local', 'this.client', 11)])
        self.assertEqual([(d.code, d.invocation.source_path, d.invocation.line)
                          for d in result.diagnostics],
                         [('unsupported-receiver', path, 5), ('unsupported-receiver', path, 10)])
        self.assertTrue(all(d.message.strip() for d in result.diagnostics))

    def assert_receiver_partition(self, path, supported, unsupported, syntax=()):
        """Every call must be a field link or an evidenced unsupported receiver."""
        result = self.resolve()
        self.assertEqual([(link.invocation.receiver, link.invocation.line)
                          for link in result.links], supported)
        for link in result.links:
            self.assertEqual(link.invocation.source_path, path)
            self.assertEqual(link.caller_type, 'shop.Caller')
            self.assertEqual(link.caller_method.name, 'run')
            self.assertEqual(link.receiver_field.name, 'client')
            self.assertEqual(link.receiver_field.type_name, 'remote.Client')
            self.assertEqual(link.receiver_field.source_path, path)
            self.assertEqual(link.receiver_field.line, 3)
            self.assertEqual(link.target_type, 'remote.Client')
            self.assertEqual(link.target_method.name, link.invocation.method_name)
            self.assertEqual(link.target_method.parameter_count,
                             link.invocation.argument_count)
        self.assertEqual([(d.code, d.invocation.receiver, d.invocation.source_path,
                           d.invocation.line) for d in result.diagnostics],
                         sorted(
                             [('unsupported-receiver', receiver, path, line)
                              for receiver, line in unsupported] +
                             [('unsupported-syntax', receiver, path, line)
                              for receiver, line in syntax],
                             key=lambda evidence: evidence[3]))
        self.assertTrue(all(d.message.strip() for d in result.diagnostics))

    def test_array_and_varargs_parameters_never_become_same_named_field_links(self):
        # clone() is valid on both an array and this explicitly typed field;
        # only the field invocation belongs in the supported call graph.
        self.client('Client clone();')
        parameters = (
            'remote.Client client[]',
            'remote.Client client[][]',
            'remote.Client[] client',
            'remote.Client[] client[]',
            '@Deprecated final remote.Client client[]',
            'remote.Client client @flags.Dimension []',
            'remote.Client client @flags.Dimension [] @flags.Dimension []',
            'remote.Client @flags.Dimension [] client @flags.Dimension []',
            'remote.Client... client',
        )
        for parameter in parameters:
            with self.subTest(parameter=parameter):
                path = self.put('src/main/java/shop/Caller.java', f'''package shop;
class Caller {{
    remote.Client client;
    void run({parameter}) {{
        client.clone();
        this.client.clone();
        {{ client.clone(); }}
        client.clone();
    }}
    void after() {{ client.clone(); }}
}}
''')
                result = self.resolve()
                self.assertEqual([(link.caller_method.name, link.invocation.receiver,
                                   link.invocation.source_path, link.invocation.line)
                                  for link in result.links],
                                 [('run', 'this.client', path, 6),
                                  ('after', 'client', path, 10)])
                for link in result.links:
                    self.assertEqual((link.receiver_field.name, link.receiver_field.type_name,
                                      link.receiver_field.source_path, link.receiver_field.line),
                                     ('client', 'remote.Client', path, 3))
                    self.assertEqual((link.target_type, link.target_method.name,
                                      link.target_method.parameter_count),
                                     ('remote.Client', 'clone', 0))
                self.assertEqual([(d.code, d.caller_method.name, d.invocation.receiver,
                                   d.invocation.source_path, d.invocation.line)
                                  for d in result.diagnostics],
                                 [('unsupported-receiver', 'run', 'client', path, line)
                                  for line in (5, 7, 8)])
                self.assertTrue(all(d.message.strip() for d in result.diagnostics))
                self.assertEqual(result.links[0].caller_method.parameter_count, 1)

    def test_enhanced_for_iterable_uses_field_before_loop_variable_shadowing(self):
        self.client('Client[] items(); Client[][] rows(); Client clone(); void lookup(String id);')
        declarations = (
            ('remote.Client client', 'items'),
            ('@Deprecated final remote.Client client', 'items'),
            ('@flags.Mark(value = "a,b") final remote.Client client', 'items'),
            ('remote.Client client[]', 'rows'),
        )
        for declaration, method in declarations:
            for body in ('{ client.clone(); this.client.lookup("field"); }',
                         'client.clone();'):
                with self.subTest(declaration=declaration, body=body):
                    path = self.put('src/main/java/shop/Caller.java', f'''package shop;
class Caller {{
    remote.Client client;
    void run() {{
        client.lookup("before");
        for ({declaration} : client.{method}())
            {body}
        client.lookup("after");
    }}
}}
''')
                    supported = [('client', 5), ('client', 6)]
                    if body.startswith('{'):
                        supported.append(('this.client', 7))
                    self.assert_receiver_partition(
                        path, supported + [('client', 8)], [('client', 7)])
                    result = self.resolve()
                    iterable = result.links[1]
                    self.assertEqual((iterable.target_method.name,
                                      iterable.target_method.parameter_count), (method, 0))
                    self.assertEqual(result, self.resolve())

    def test_nested_enhanced_for_iterable_restores_outer_loop_then_field(self):
        self.client('Client[] items(); void lookup(String id);')
        path = self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    remote.Client client;
    void run() {
        for (remote.Client client : client.items()) {
            for (remote.Client other : client.items()) {
                client.lookup("outer variable in inner body");
                this.client.lookup("field");
            }
            client.lookup("outer variable restored");
        }
        client.lookup("field restored");
    }
}
''')
        self.assert_receiver_partition(
            path, [('client', 5), ('this.client', 8), ('client', 12)],
            [('client', 6), ('client', 7), ('client', 10)])

    def test_enhanced_for_iterable_and_exit_preserve_enclosing_variable_shadowing(self):
        self.client('Client[] items(); void lookup(String id);')
        for parameter, declaration in (
                ('remote.Client client', ''),
                ('', 'remote.Client client = null;')):
            with self.subTest(parameter=parameter, declaration=declaration):
                path = self.put('src/main/java/shop/Caller.java', f'''package shop;
class Caller {{
    remote.Client client;
    void run({parameter}) {{
        {declaration}
        for (remote.Client other : client.items()) {{
            client.lookup("enclosing variable in loop");
            this.client.lookup("field");
        }}
        client.lookup("enclosing variable restored");
        for (remote.Client other : this.client.items())
            client.lookup("enclosing variable");
        this.client.lookup("field after loops");
    }}
}}
''')
                self.assert_receiver_partition(
                    path, [('this.client', 8), ('this.client', 11), ('this.client', 13)],
                    [('client', 6), ('client', 7), ('client', 10), ('client', 12)])

    def test_annotated_local_shadowing_preserves_explicit_this_and_block_exit(self):
        self.client()
        for declaration in (
                '@Deprecated remote.Client client = null;',
                '@Deprecated final remote.Client client = null;',
                '@flags.Mark(value = "a,b", tags = {"x", "y"}) '
                '@Deprecated final remote.Client client = null;'):
            with self.subTest(declaration=declaration):
                path = self.put('src/main/java/shop/Caller.java', f'''package shop;
class Caller {{
    remote.Client client;
    void run() {{
        client.lookup("before");
        {{
            {declaration}
            client.lookup("local");
            this.client.lookup("field");
        }}
        client.lookup("after");
    }}
}}
''')
                self.assert_receiver_partition(
                    path, [('client', 5), ('this.client', 9), ('client', 11)],
                    [('client', 8)])

    def test_comma_declarators_shadow_only_from_their_own_declaration(self):
        self.client('Client copy(String a, String b); void lookup(String id);')
        for prefix in ('', 'final ', '@Deprecated final ',
                       '@flags.Mark(value = "a,b", tags = {"x", "y"}) final '):
            with self.subTest(prefix=prefix):
                path = self.put('src/main/java/shop/Caller.java', f'''package shop;
class Caller {{
    remote.Client client;
    void run() {{
        {{
            {prefix}remote.Client first = client.copy("a,b", "x"),
                second = client.copy("c", "d"),
                client = this.client.copy("e", "f"),
                last = client.copy("g", "h");
            client.lookup("local");
            this.client.lookup("field");
        }}
        client.lookup("after");
    }}
}}
''')
                # Calls in earlier declarators still use the field. The last
                # initializer and subsequent bare calls use the local instead.
                self.assert_receiver_partition(
                    path, [('client', 6), ('client', 7), ('this.client', 8),
                           ('this.client', 11), ('client', 13)],
                    [('client', 9), ('client', 10)])

    def test_loop_local_lifetime_ends_after_the_whole_body(self):
        self.client()
        headers = (
            'for (remote.Client client : clients)',
            'for (@Deprecated final remote.Client client : clients)',
            'for (remote.Client client = null; client != null; client = null)',
            'for (final remote.Client first = null, client = null; client != null; )',
        )
        # Each statement is a complete loop body, including nested loops and
        # both arms of an unbraced conditional. Ending at the first semicolon
        # or retaining the variable until the method ends is incorrect.
        bodies = (
            ('{\n            client.lookup("local");\n'
             '            this.client.lookup("field");\n        }',
             [('this.client', 8)], [('client', 7)], 10),
            ('client.lookup("local");', [], [('client', 6)], 7),
            ('if (true)\n            client.lookup("then");\n'
             '        else\n            client.lookup("else");',
             [], [('client', 7), ('client', 9)], 10),
            ('for (int i = 0; i < 1; i++)\n'
             '            client.lookup("nested");',
             [], [('client', 7)], 8),
            ('{\n            for (int i = 0; i < 1; i++) {\n'
             '                client.lookup("nested");\n            }\n'
             '            client.lookup("still local");\n        }',
             [], [('client', 8), ('client', 10)], 12),
        )
        for header in headers:
            for body, supported, unsupported, after_line in bodies:
                with self.subTest(header=header, body=body):
                    path = self.put('src/main/java/shop/Caller.java', f'''package shop;
class Caller {{
    remote.Client client;
    void run() {{
        client.lookup("before");
        {header} {body}
        client.lookup("after");
    }}
}}
''')
                    self.assert_receiver_partition(
                        path, [('client', 5)] + supported + [('client', after_line)],
                        unsupported)

    def test_classic_loop_shadowing_applies_in_condition_update_and_body_only(self):
        self.client('Client copy(String a, String b); void lookup(String id);')
        path = self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    remote.Client client;
    void run() {
        for (remote.Client first = client.copy("a,b", "x"),
                client = this.client.copy("c", "d");
                client.copy("condition", "x") != null;
                client.lookup("update")) {
            client.lookup("body");
            this.client.lookup("field");
        }
        client.lookup("after");
    }
}
''')
        self.assert_receiver_partition(
            path, [('client', 5), ('this.client', 6), ('this.client', 10),
                   ('client', 12)],
            [('client', 7), ('client', 8), ('client', 9)])

    def test_catch_parameter_shadows_only_its_body(self):
        self.client()
        for parameter in ('remote.Failure client',
                          'final remote.Failure client',
                          '@Deprecated final remote.Failure client',
                          'remote.FirstFailure | remote.SecondFailure client'):
            with self.subTest(parameter=parameter):
                path = self.put('src/main/java/shop/Caller.java', f'''package shop;
class Caller {{
    remote.Client client;
    void run() {{
        client.lookup("before");
        try {{ client.lookup("try"); }}
        catch ({parameter}) {{
            client.lookup("catch parameter");
            this.client.lookup("field");
            {{ client.lookup("nested catch body"); }}
        }}
        finally {{ client.lookup("finally field"); }}
        client.lookup("after");
    }}
}}
''')
                self.assert_receiver_partition(
                    path, [('client', 5), ('client', 6), ('this.client', 9),
                           ('client', 12), ('client', 13)],
                    [('client', 8), ('client', 10)])

    def test_successive_catches_do_not_share_parameter_scope(self):
        self.client()
        path = self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    remote.Client client;
    void run() {
        try {} catch (remote.FirstFailure client) {
            client.lookup("parameter");
            this.client.lookup("field");
        } catch (remote.SecondFailure other) {
            client.lookup("field in second catch");
        }
        client.lookup("after");
    }
}
''')
        self.assert_receiver_partition(
            path, [('this.client', 7), ('client', 9), ('client', 11)],
            [('client', 6)])

    def test_catch_exit_restores_enclosing_local_not_field(self):
        self.client()
        path = self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    remote.Client client;
    void run() {
        {
            remote.Client client = null;
            try {} catch (remote.Failure other) {
                client.lookup("enclosing local in catch");
                this.client.lookup("field");
            }
            client.lookup("enclosing local");
            this.client.lookup("field");
        }
        client.lookup("after block");
    }
}
''')
        self.assert_receiver_partition(
            path, [('this.client', 9), ('this.client', 12), ('client', 14)],
            [('client', 8), ('client', 11)])

    def test_generic_initializer_commas_do_not_hide_later_local_declarators(self):
        self.client('Client copy(String a, String b); void lookup(String id);')
        initializers = (
            'new Pair<String, Integer>()',
            'new Pair<String, java.util.List<Integer>>()',
            'new Pair<java.util.Map<String, Integer>, java.util.List<Long>>()',
            'Factory.<String, Integer>create()',
            'this.<String, java.util.List<Integer>>create()',
            'new <String, Integer>Box()',
        )
        for initializer in initializers:
            with self.subTest(initializer=initializer):
                path = self.put('src/main/java/shop/Caller.java', f'''package shop;
class Caller {{
    remote.Client client;
    void run() {{
        {{
            Object first = client.copy("before", "declaration"),
                generic = {initializer},
                client = this.client.copy("field", "initializer"),
                last = client.copy("local", "initializer");
            client.lookup("local");
            this.client.lookup("field");
        }}
        client.lookup("after");
    }}
}}
''')
                self.assert_receiver_partition(
                    path, [('client', 6), ('this.client', 8),
                           ('this.client', 11), ('client', 13)],
                    [('client', 9), ('client', 10)],
                    syntax=[('Factory', 7)] if initializer.startswith('Factory.') else ())

    def test_generic_initializer_in_loop_restores_field_after_body(self):
        self.client()
        path = self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    remote.Client client;
    void run() {
        for (Object first = new Pair<String, java.util.List<Integer>>(),
                client = null; client != null; ) {
            client.lookup("local");
            this.client.lookup("field");
        }
        client.lookup("after");
    }
}
''')
        self.assert_receiver_partition(
            path, [('this.client', 8), ('client', 10)], [('client', 7)])

    def test_comparisons_do_not_swallow_local_declarator_commas(self):
        self.client()
        # A '<' comparison is not an opening generic type argument list.
        for initializer in ('a < b', 'a < b && c > d',
                            'a < b ? left : right', 'a > b'):
            with self.subTest(initializer=initializer):
                path = self.put('src/main/java/shop/Caller.java', f'''package shop;
class Caller {{
    remote.Client client;
    void run() {{
        {{
            Object first = {initializer}, client = null;
            client.lookup("unsupported local");
            this.client.lookup("field");
        }}
        client.lookup("after");
    }}
}}
''')
                self.assert_receiver_partition(
                    path, [('this.client', 8), ('client', 10)], [('client', 7)])

    def test_generic_constructor_commas_do_not_select_wrong_overload(self):
        client_path = self.client('void lookup(Object value);\n    void lookup(Object a, Object b);')
        expressions = (
            'new Pair<String, Integer>()',
            'new Pair<String, java.util.List<Integer>>()',
            'new Pair<java.util.Map<String, Integer>, java.util.List<Long>>()',
            'new <String, Integer>Box()',
            'new Pair<String, Integer>(nested(1, 2), "a,b")',
        )
        for expression in expressions:
            for second_argument in ('', ', "second"'):
                with self.subTest(expression=expression, second_argument=second_argument):
                    path = self.put('src/main/java/shop/Caller.java', f'''package shop;
class Caller {{
    remote.Client client;
    void run() {{
        client.lookup({expression}{second_argument});
    }}
}}
''')
                    result = self.resolve()
                    self.assertEqual(list(result.diagnostics), [])
                    self.assertEqual(len(result.links), 1)
                    link = result.links[0]
                    arity = 2 if second_argument else 1
                    self.assertEqual((link.invocation.argument_count,
                                      link.target_method.parameter_count), (arity, arity))
                    self.assertEqual((link.invocation.source_path, link.invocation.line),
                                     (path, 5))
                    self.assertEqual((link.target_method.source_path, link.target_method.line),
                                     (client_path, 3 if arity == 1 else 4))
                    self.assertEqual(result, self.resolve())

    def test_comparison_arguments_still_select_two_argument_overload(self):
        self.client('void lookup(Object value); void lookup(Object a, Object b);')
        for arguments in ('a < b, c > d', 'a < b, c',
                          'a < b ? left : right, "a,b"',
                          'a > b, new Pair<String, Integer>()'):
            with self.subTest(arguments=arguments):
                self.put('src/main/java/shop/Caller.java', f'''package shop;
class Caller {{
    remote.Client client;
    void run() {{ client.lookup({arguments}); }}
}}
''')
                result = self.resolve()
                self.assertEqual(list(result.diagnostics), [])
                self.assertEqual(len(result.links), 1)
                self.assertEqual((result.links[0].invocation.argument_count,
                                  result.links[0].target_method.parameter_count), (2, 2))

    def test_generic_method_argument_retains_diagnostic_and_outer_arity(self):
        self.client('void lookup(Object value); void lookup(Object a, Object b);')
        for expression in ('Factory.<String, Integer>create()',
                           'Factory.<String, java.util.List<Integer>>create("a,b")'):
            for suffix in ('', ', "second"'):
                with self.subTest(expression=expression, suffix=suffix):
                    path = self.put('src/main/java/shop/Caller.java', f'''package shop;
class Caller {{
    remote.Client client;
    void run() {{
        client.lookup({expression}{suffix});
    }}
}}
''')
                    result = self.resolve()
                    self.assertEqual(len(result.links), 1)
                    self.assertEqual((result.links[0].invocation.argument_count,
                                      result.links[0].target_method.parameter_count),
                                     (2, 2) if suffix else (1, 1))
                    self.assertEqual([(d.code, d.invocation.receiver,
                                       d.invocation.method_name, d.invocation.source_path,
                                       d.invocation.line) for d in result.diagnostics],
                                     [('unsupported-syntax', 'Factory', 'create', path, 5)])
                    self.assertTrue(result.diagnostics[0].message.strip())

    def test_resource_variable_shadows_header_and_body_not_catch_finally_or_after(self):
        self.client('Client copy(String a, String b); void lookup(String id);')
        for modifier in ('', 'final ', '@Deprecated final '):
            with self.subTest(modifier=modifier):
                path = self.put('src/main/java/shop/Caller.java', f'''package shop;
class Caller {{
    remote.Client client;
    void run() {{
        client.lookup("before");
        try ({modifier}remote.Client first = client.copy("a", "b");
             {modifier}remote.Client client = this.client.copy("c", "d");
             remote.Client last = client.copy("local", "header")) {{
            client.lookup("resource");
            this.client.lookup("field");
            {{ client.lookup("nested block"); }}
        }} catch (Exception other) {{
            client.lookup("catch field");
        }} finally {{
            client.lookup("finally field");
        }}
        client.lookup("after");
    }}
}}
''')
                self.assert_receiver_partition(
                    path, [('client', 5), ('client', 6), ('this.client', 7),
                           ('this.client', 10), ('client', 13), ('client', 15),
                           ('client', 17)],
                    [('client', 8), ('client', 9), ('client', 11)])

    def test_nested_resource_exit_restores_outer_resource_then_field(self):
        self.client()
        path = self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    remote.Client client;
    void run() {
        try (remote.Client client = null) {
            try (remote.Client other = null) {
                client.lookup("outer resource");
                this.client.lookup("field");
            } finally { client.lookup("still outer resource"); }
            client.lookup("outer resource after inner");
        } finally { client.lookup("field"); }
        client.lookup("after");
    }
}
''')
        self.assert_receiver_partition(
            path, [('this.client', 8), ('client', 11), ('client', 12)],
            [('client', 7), ('client', 9), ('client', 10)])

    def test_resource_exit_restores_enclosing_local_not_field(self):
        self.client()
        path = self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    remote.Client client;
    void run() {
        {
            remote.Client client = null;
            try (remote.Client other = null) {
                client.lookup("enclosing local");
                this.client.lookup("field");
            } catch (Exception failure) { client.lookup("local in catch"); }
            finally { client.lookup("local in finally"); }
            client.lookup("local after try");
        }
        client.lookup("field after block");
    }
}
''')
        self.assert_receiver_partition(
            path, [('this.client', 9), ('client', 14)],
            [('client', 8), ('client', 10), ('client', 11), ('client', 12)])

    def test_explicit_generic_field_calls_are_evidenced_not_observed_links(self):
        self.client('void lookup(); void lookup(Object value); String key(String a, String b);')
        path = self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    remote.Client client;
    void run() {
        client.<String, Integer>lookup();
        this.client.<String, java.util.List<Integer>>lookup(
            client.key("a,b", "c"));
        client.lookup();
        this.<String, Integer>helper();
    }
    void helper() {}
}
''')
        result = self.resolve()
        self.assertEqual([(link.invocation.receiver, link.target_method.name,
                           link.invocation.argument_count, link.invocation.line)
                          for link in result.links],
                         [('client', 'key', 2, 7), ('client', 'lookup', 0, 8)])
        self.assertEqual([(d.code, d.caller_type, d.caller_method.name,
                           d.invocation.receiver, d.invocation.method_name,
                           d.invocation.argument_count, d.invocation.source_path,
                           d.invocation.line) for d in result.diagnostics],
                         [('unsupported-syntax', 'shop.Caller', 'run', 'client',
                           'lookup', 0, path, 5),
                          ('unsupported-syntax', 'shop.Caller', 'run', 'this.client',
                           'lookup', 1, path, 6)])
        for diagnostic in result.diagnostics:
            self.assertTrue(diagnostic.invocation.explicit_type_arguments)
            self.assertIn('generic', diagnostic.message.lower())
            self.assertIn('not supported', diagnostic.message.lower())
            self.assertEqual(diagnostic.candidates, ())
        self.assertEqual(result, self.resolve())

    def test_supported_links_and_unresolved_connections_coexist(self):
        self.client('void lookup(String id);\n    void lookup(int id);\n    void refresh();')
        self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    remote.Client client;
    void run() {
        client.lookup(1);
        client.refresh();
        this.client.refresh();
    }
}
''')
        result = self.resolve()
        self.assertEqual([(link.target_method.name, link.invocation.line)
                          for link in result.links], [('refresh', 6), ('refresh', 7)])
        self.assertEqual([(d.code, d.invocation.line) for d in result.diagnostics],
                         [('ambiguous-overload', 5)])

    def test_overloaded_caller_methods_keep_distinct_method_identity(self):
        self.client('void lookup();')
        path = self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    remote.Client client;
    void run(String id) { client.lookup(); }
    void run(int id) { this.client.lookup(); }
}
''')
        result = self.resolve()
        self.assertEqual(list(result.diagnostics), [])
        self.assertEqual([(link.caller_method.name, link.caller_method.parameter_count,
                           link.caller_method.source_path, link.caller_method.line,
                           link.invocation.line) for link in result.links],
                         [('run', 1, path, 4, 4), ('run', 1, path, 5, 5)])
        self.assertNotEqual(result.links[0].caller_method, result.links[1].caller_method,
                            'Same-name/same-arity caller declarations must not be merged')

    def test_nested_field_invocations_resolve_independently_with_exact_arity(self):
        self.client('void lookup(String id);\n    String key(String a, String b);')
        path = self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    remote.Client client;
    void run() {
        this.client.lookup(
            client.key("a,b", "c"));
    }
}
''')
        result = self.resolve()
        self.assertEqual(list(result.diagnostics), [])
        self.assertEqual([(link.target_method.name, link.target_method.parameter_count,
                           link.invocation.source_path, link.invocation.line)
                          for link in result.links],
                         [('lookup', 1, path, 5), ('key', 2, path, 6)])

    def test_inherited_method_is_unresolved_rather_than_guessed(self):
        self.put('src/main/java/shop/Base.java',
                 'package shop; class Base { void lookup(String id) {} }')
        self.put('src/main/java/shop/Gateway.java',
                 'package shop; class Gateway extends Base {}')
        path = self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    Gateway gateway;
    void run() {
        gateway.lookup("x");
    }
}
''')
        result = self.resolve()
        self.assertEqual(list(result.links), [])
        self.assertEqual([(d.code, d.invocation.source_path, d.invocation.line)
                          for d in result.diagnostics], [('unresolved-method', path, 5)])
        self.assertTrue(result.diagnostics[0].message.strip())

    def test_relevant_chained_receiver_has_uncertainty_evidence_not_a_guessed_link(self):
        self.client()
        self.put('src/main/java/shop/Factory.java', '''package shop;
class Factory {
    remote.Client create() { return null; }
}
''')
        path = self.put('src/main/java/shop/Caller.java', '''package shop;
class Caller {
    Factory factory;
    void run() {
        factory.create().lookup("x");
    }
}
''')
        result = self.resolve()
        # The typed field call to create is supported. Its result is not a
        # supported receiver: do not infer an invocation of Client.lookup.
        self.assertEqual([self.identity(link) for link in result.links],
                         [('shop.Caller', 'run', 0, 'shop.Factory', 'create', 0)])
        unsupported = [d for d in result.diagnostics if d.code == 'unsupported-receiver']
        self.assertTrue(unsupported,
                        'Relevant chained calls must not silently disappear from uncertainty evidence')
        self.assertTrue(any(d.invocation.method_name == 'lookup' and
                            d.invocation.source_path == path and d.invocation.line == 5 and
                            d.message.strip() for d in unsupported))

    def test_resolution_is_source_only_bounded_read_only_and_repeatable(self):
        self.client()
        self.put('src/main/java/shop/Caller.java',
                 'package shop; class Caller { remote.Client c; void run() { c.lookup("x"); } }')
        for relative in ('src/test/java/Test.java', 'target/generated-sources/Generated.java',
                         'other/Other.java', 'src/main/java/NotJava.txt'):
            self.put(relative,
                     'class Outside { remote.Client c; void run() { c.lookup("x"); } }')
        before = {p.relative_to(self.root): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file()}
        with patch('subprocess.Popen', side_effect=AssertionError('Do not execute Java or build tools')), \
             patch('os.system', side_effect=AssertionError('Do not execute tools')):
            first = self.resolve()
            second = self.resolve()
        self.assertEqual([self.identity(link) for link in first.links],
                         [('shop.Caller', 'run', 0, 'remote.Client', 'lookup', 1)])
        self.assertEqual(first, second)
        after = {p.relative_to(self.root): p.read_bytes()
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
