from pathlib import Path
import tempfile
import unittest

from archr.discovery import discover_clients, extract_clients
from archr.module import AnalysisError, load_module


IMPORT = 'import org.springframework.cloud.openfeign.FeignClient;\n'


class ExtractionTests(unittest.TestCase):
    def extract(self, source):
        return extract_clients(IMPORT + source, 'src/main/java/example/Clients.java')

    def test_multiline_attributes_aliases_and_evidence(self):
        clients = self.extract('''@FeignClient(
    name = "inventory", url = "https://inventory.example")
public interface InventoryClient {}
@FeignClient(value = "pricing", url = "${pricing.url}")
interface PricingClient {}
@FeignClient("shipping")
interface ShippingClient {}
''')
        self.assertEqual([c.interface_name for c in clients],
                         ['InventoryClient', 'PricingClient', 'ShippingClient'])
        self.assertEqual([c.name for c in clients], ['inventory', 'pricing', 'shipping'])
        self.assertEqual([c.url for c in clients],
                         ['https://inventory.example', '${pricing.url}', None])
        self.assertEqual([c.line for c in clients], [2, 5, 7])
        self.assertTrue(all(c.source_path == 'src/main/java/example/Clients.java' for c in clients))

    def test_comments_strings_classes_and_unrelated_annotations_ignored(self):
        clients = self.extract('''
// @FeignClient("fake") interface Fake {}
/* @FeignClient("fake") interface Fake {} */
class Holder {
 String s = "@FeignClient(\\"fake\\") interface Fake {}";
 String text = """
 @FeignClient("fake") interface Fake {}
 """;
}
@FeignClient("class") public class NotInterface {}
@Other.FeignClient("unrelated") interface OtherClient {}
@FeignClient("real") @Deprecated public interface Real {}
''')
        self.assertEqual([c.name for c in clients], ['real'])

    def test_type_resolution(self):
        declaration = '@FeignClient("test") interface Client {}'
        self.assertEqual(extract_clients(declaration, 'Client.java'), [])
        self.assertEqual(extract_clients('import unrelated.FeignClient;\n' + declaration, 'Client.java'), [])
        self.assertEqual(len(extract_clients('import org.springframework.cloud.openfeign.*;\n' + declaration, 'Client.java')), 1)
        self.assertEqual(len(extract_clients('@org.springframework.cloud.openfeign.FeignClient("test") interface Client {}', 'Client.java')), 1)

    def test_nonliteral_expressions_not_guessed(self):
        clients = self.extract('''@FeignClient(name = Names.INVENTORY, url = BASE + "/api")
interface Client {}
@FeignClient interface Empty {}
''')
        self.assertIsNone(clients[0].name)
        self.assertEqual(clients[0].name_expression, 'Names.INVENTORY')
        self.assertIsNone(clients[0].url)
        self.assertEqual(clients[0].url_expression, 'BASE + "/api"')
        self.assertIsNone(clients[1].url_expression)

    def test_commas_parentheses_escapes_and_annotation_order(self):
        clients = self.extract('''@Deprecated
@FeignClient(name = "a,b)", url = "https://example/\\\"quoted\\\"", configuration = {A.class, B.class})
@Other(values = {"a", "b"}) public interface Client<T> extends Base<T> {}
''')
        self.assertEqual(clients[0].name, 'a,b)')
        self.assertEqual(clients[0].url, 'https://example/"quoted"')

    def test_body_offsets_and_empty_name_alias(self):
        source = IMPORT + '@FeignClient(name = "", value = "alias") interface Client { void method(); }'
        client = extract_clients(source, 'Client.java')[0]
        self.assertEqual(client.name, 'alias')
        self.assertEqual(source[client.body_start:client.body_end], ' void method(); ')


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'src/main/java').mkdir(parents=True)
        self.module = load_module(str(self.root))

    def put(self, relative, name):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(IMPORT + f'@FeignClient("{name}") interface Client {{}}', encoding='utf-8')
        return path

    def test_recursive_sorted_java_only_and_source_boundaries(self):
        self.put('src/main/java/z/Z.java', 'z')
        self.put('src/main/java/a/A.java', 'a')
        self.put('src/main/java/Ignored.txt', 'text')
        self.put('src/test/java/Test.java', 'test')
        self.put('target/generated-sources/Generated.java', 'generated')
        self.put('other/Other.java', 'other')
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        clients = discover_clients(self.module)
        self.assertEqual([c.name for c in clients], ['a', 'z'])
        self.assertEqual([c.source_path for c in clients],
                         ['src/main/java/a/A.java', 'src/main/java/z/Z.java'])
        self.assertEqual(clients, discover_clients(self.module))
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_symlinks_do_not_expand_boundary(self):
        outside = self.put('outside/Outside.java', 'outside')
        (self.module.source_root / 'Link.java').symlink_to(outside)
        (self.module.source_root / 'linked').symlink_to(outside.parent, target_is_directory=True)
        self.assertEqual(discover_clients(self.module), [])

    def test_no_clients(self):
        self.assertEqual(discover_clients(self.module), [])

    def test_unreadable_source_and_directory_fail(self):
        path = self.put('src/main/java/nested/Client.java', 'client')
        for target in (path, path.parent):
            with self.subTest(target=target):
                mode = target.stat().st_mode
                try:
                    target.chmod(0)
                    with self.assertRaises(AnalysisError):
                        discover_clients(self.module)
                finally:
                    target.chmod(mode)

    def test_invalid_encoding_fails(self):
        (self.module.source_root / 'Broken.java').write_bytes(b'\xff')
        with self.assertRaises(AnalysisError):
            discover_clients(self.module)


if __name__ == '__main__':
    unittest.main()
