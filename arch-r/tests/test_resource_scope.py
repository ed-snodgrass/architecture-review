"""Resource lifetimes must not turn local calls into observed field links.

Fixtures use AutoCloseable resources and are inspected as source only; Java is
never compiled or executed. Tests target the first unfinished plan subtask.
"""

from pathlib import Path
import tempfile
import unittest

from archr.module import load_module
from archr.resolution import resolve_calls


class ResourceScopeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='arch_r_resources_')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.put('remote/Client.java', '''package remote;
public interface Client extends AutoCloseable {
    Client copy();
    void lookup(String id);
    void close();
}
''')
        self.module = load_module(str(self.root))

    def put(self, name, source):
        path = self.root / 'src/main/java' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')
        return path.relative_to(self.root).as_posix()

    def check_partition(self, source, observed, unsupported):
        path = self.put('shop/Caller.java', source)
        result = resolve_calls(self.module)
        self.assertEqual(
            [(link.invocation.receiver, link.invocation.line) for link in result.links],
            observed)
        self.assertEqual(
            [(d.invocation.receiver, d.invocation.line) for d in result.diagnostics],
            unsupported)
        for link in result.links:
            self.assertEqual(link.caller_type, 'shop.Caller')
            self.assertEqual(link.caller_method.name, 'run')
            self.assertEqual(link.invocation.source_path, path)
            self.assertEqual(link.target_type, 'remote.Client')
            self.assertEqual(link.receiver_field.source_path, path)
            self.assertEqual(link.receiver_field.line, 3)
        for diagnostic in result.diagnostics:
            self.assertEqual(diagnostic.code, 'unsupported-receiver')
            self.assertEqual(diagnostic.invocation.source_path, path)
            self.assertTrue(diagnostic.message.strip())
        self.assertEqual(result, resolve_calls(self.module))

    def test_multiple_resources_restore_field_after_body_for_all_modifiers(self):
        for modifier in ('', 'final ', '@Deprecated final '):
            with self.subTest(modifier=modifier):
                self.check_partition(f'''package shop;
class Caller {{
    remote.Client client;
    void run() {{
        try ({modifier}remote.Client first = client.copy();
             {modifier}remote.Client client = this.client.copy();
             remote.Client last = client.copy()) {{
            client.lookup("resource");
            this.client.lookup("field");
        }} catch (Exception failure) {{
            client.lookup("catch field");
        }} finally {{
            client.lookup("finally field");
        }}
        client.lookup("after");
    }}
}}
''', [('client', 5), ('this.client', 6), ('this.client', 9),
      ('client', 11), ('client', 13), ('client', 15)],
                     [('client', 7), ('client', 8)])

    def test_catch_can_reuse_resource_name_without_leaking_either_scope(self):
        self.check_partition('''package shop;
class Caller {
    remote.Client client;
    void run() {
        try (remote.Client client = this.client.copy()) {
            client.lookup("resource");
        } catch (Exception client) {
            client.getMessage();
            this.client.lookup("explicit field");
        } finally {
            client.lookup("finally field");
        }
        client.lookup("after");
    }
}
''', [('this.client', 5), ('this.client', 9), ('client', 11), ('client', 13)],
             [('client', 6), ('client', 8)])

    def test_resource_exit_does_not_remove_enclosing_parameter_shadow(self):
        self.check_partition('''package shop;
class Caller {
    remote.Client client;
    void run(remote.Client client) {
        try (remote.Client resource = client.copy()) {
            client.lookup("parameter in body");
        } catch (Exception failure) {
            client.lookup("parameter in catch");
        } finally {
            client.lookup("parameter in finally");
        }
        client.lookup("parameter afterward");
        this.client.lookup("field");
    }
}
''', [('this.client', 13)],
             [('client', 5), ('client', 6), ('client', 8), ('client', 10), ('client', 12)])

    def test_existing_field_resource_is_not_a_new_local_declaration(self):
        self.check_partition('''package shop;
class Caller {
    final remote.Client client = null;
    void run() {
        try (client) {
            client.lookup("field in body");
        } finally {
            client.lookup("field in finally");
        }
        client.lookup("field afterward");
    }
}
''', [('client', 6), ('client', 8), ('client', 10)], [])


if __name__ == '__main__':
    unittest.main()
