"""Bounded source detection; independent of traversal and report rendering."""
from dataclasses import replace
import unittest

from archr.failure_handling import detect_failure_handling
from archr.indexing import SourceIndex, index_source
from archr.resolution import resolve_index


CLIENT = '''package shop;
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient(name="products") interface Products { String get(); }
'''


class FailureHandlingDetectionTests(unittest.TestCase):
    def detect(self, body, imports='import feign.FeignException;', header='', extra=''):
        source = ('package shop;\n' + imports + '\nclass Orders ' + header + ''' {
    Products products;
    void place() {
''' + body + '\n    }\n}\n' + extra)
        units = (index_source(CLIENT, 'Products.java'), index_source(source, 'Orders.java'))
        index = SourceIndex(tuple(t for u in units for t in u.types),
                            tuple(n for u in units for n in u.declared_type_names),
                            tuple(s for u in units for s in u.sources))
        resolution = resolve_index(index)
        return source, index, resolution, detect_failure_handling(index, resolution)

    def test_imported_and_qualified_catches_have_exact_evidence(self):
        for exception, imports in [('FeignException', 'import feign.FeignException;'),
                                   ('feign.FeignException', '')]:
            with self.subTest(exception=exception):
                source, _, _, observations = self.detect(
                    'try {\n products.get();\n} catch (' + exception + ' failure) {}', imports)
                self.assertEqual(len(observations), 1)
                observation = observations[0]
                self.assertEqual(observation.call.caller_type, 'shop.Orders')
                self.assertEqual(observation.call.target_type, 'shop.Products')
                self.assertEqual(observation.call.target_method.name, 'get')
                self.assertEqual(observation.call.invocation.source_offset, source.index('products.get'))
                self.assertEqual(observation.catch_source_offset, source.index('catch'))
                self.assertEqual(observation.catch_line, source[:source.index('catch')].count('\n') + 1)
                self.assertEqual(observation.catch_source_path, 'Orders.java')

    def test_deduplicates_links_but_keeps_distinct_calls_and_catches(self):
        _, index, resolution, observations = self.detect('''
try { products.get(); products.get(); } catch (FeignException e) {}
try { products.get(); } catch (FeignException e) {}
''')
        self.assertEqual(len(observations), 3)
        duplicate = replace(resolution, links=resolution.links * 2)
        self.assertEqual(detect_failure_handling(index, duplicate), observations)
        self.assertEqual(len({o.identity for o in observations}), 3)

    def test_unsupported_associations_are_silent(self):
        bodies = [
            'products.get(); try { other.work(); } catch (FeignException e) {}',
            'try { other.work(); } catch (FeignException e) { products.get(); }',
            'try { other.work(); } finally { products.get(); }',
            'try { products.get(); } catch (Exception e) {}',
            'try { products.get(); } catch (ChildException e) {}',
            'try { products.get(); } catch (FeignException | OtherException e) {}',
            'try (Resource r = open()) { products.get(); } catch (FeignException e) {}',
            'try { try { products.get(); } catch (FeignException e) {} } catch (FeignException e) {}',
            'try { products.get(); try { other.work(); } finally {} } catch (FeignException e) {}',
            'try (Resource r = open()) { try { products.get(); } catch (FeignException e) {} }',
            'try { Runnable r = () -> { products.get(); }; } catch (FeignException e) {}',
            'try { Runnable r = () -> products.get(); } catch (FeignException e) {}',
            'Runnable r = () -> { try { products.get(); } catch (FeignException e) {} };',
            'try { class Local { void run() { products.get(); } } } catch (FeignException e) {}',
            'try { Object o = new Object() { void run() { products.get(); } }; } catch (FeignException e) {}',
            'try { helper(); } catch (FeignException e) {}',
            '// try { products.get(); } catch (FeignException e) {}',
            'String s = "try { products.get(); } catch (FeignException e) {}";',
        ]
        for body in bodies:
            with self.subTest(body=body):
                self.assertEqual(self.detect(body)[3], ())

    def test_uncertain_or_shadowed_types_are_silent(self):
        body = 'try { products.get(); } catch (FeignException e) {}'
        for imports, header, extra in [
            ('', '', ''), ('import feign.*;', '', ''),
            ('import app.FeignException;', '', ''),
            ('import feign.FeignException; import app.FeignException;', '', ''),
            ('import feign.FeignException;', '<FeignException>', ''),
            ('import feign.FeignException;', '', 'class FeignException {}'),
            ('import feign.FeignException;', 'extends Base', ''),
        ]:
            with self.subTest(imports=imports, header=header, extra=extra):
                self.assertEqual(self.detect(body, imports, header, extra)[3], ())
        self.assertEqual(self.detect('class FeignException {} ' + body)[3], ())
        self.assertEqual(self.detect(body.replace('FeignException', 'feign.FeignException'),
                                     '', '<feign>')[3], ())

    def test_plain_control_blocks_and_final_parameter_are_supported(self):
        self.assertEqual(len(self.detect('''
try { if (ready) { products.get(); } } catch (final FeignException e) {}
''')[3]), 1)

    def test_missing_source_or_legacy_offsets_do_not_guess(self):
        _, index, resolution, observations = self.detect(
            'try { products.get(); } catch (FeignException e) {}')
        self.assertTrue(observations)
        self.assertEqual(detect_failure_handling(replace(index, sources=()), resolution), ())
        call = resolution.links[0]
        legacy = replace(call, invocation=replace(call.invocation, source_offset=None))
        self.assertEqual(detect_failure_handling(index, replace(resolution, links=(legacy,))), ())


if __name__ == '__main__':
    unittest.main()
