"""Iteration 004 declaration inventory, independent of operation/report tasks."""

from pathlib import Path
import tempfile
import unittest

from archr.indexing import SourceIndex, index_source
from archr.integrations import (CLIENT_FIELDS, JPA_REPOSITORY,
                                declarations_from_index, discover_declarations,
                                extract_declarations)
from archr.module import load_module


class IntegrationDeclarationTests(unittest.TestCase):
    path = 'src/main/java/shop/Declarations.java'

    def extract(self, source):
        return extract_declarations(source, self.path)

    def test_direct_generic_repository_and_constructor_injected_fields(self):
        source = '''package shop;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.reactive.function.client.WebClient;
interface Orders extends JpaRepository<Order, Long> {}
class Gateway {
    private final JdbcTemplate jdbc;
    private final RestTemplate rest;
    private final WebClient web;
    Gateway(JdbcTemplate jdbc, RestTemplate rest, WebClient web) {
        this.jdbc = jdbc; this.rest = rest; this.web = web;
    }
}
'''
        declarations = self.extract(source)
        self.assertEqual([(d.mechanism, d.category, d.declaring_type,
                           d.field_name, d.line) for d in declarations], [
            ('Spring Data JPA', 'database', 'shop.Orders', None, 6),
            ('Spring JDBC', 'database', 'shop.Gateway', 'jdbc', 8),
            ('Spring HTTP', 'HTTP', 'shop.Gateway', 'rest', 9),
            ('Spring reactive HTTP', 'HTTP', 'shop.Gateway', 'web', 10),
        ])
        self.assertTrue(all(d.source_path == self.path for d in declarations))
        self.assertEqual([d.type_name for d in declarations],
                         ['shop.Orders', *CLIENT_FIELDS])

    def test_fully_qualified_and_same_package_types(self):
        for library, (mechanism, _) in CLIENT_FIELDS.items():
            package, _, simple = library.rpartition('.')
            with self.subTest(library=library):
                qualified = self.extract(f'class Gateway {{ {library} client; }}')
                packaged = self.extract(
                    f'package {package}; class Gateway {{ {simple} client; }}')
                self.assertEqual(qualified[0].mechanism, mechanism)
                self.assertEqual(packaged[0].type_name, library)
        for source in (
            f'interface Orders extends {JPA_REPOSITORY}<Order, Long> {{}}',
            'package org.springframework.data.jpa.repository; '
            'interface Orders extends JpaRepository<Order, Long> {}',
        ):
            self.assertEqual(self.extract(source)[0].mechanism, 'Spring Data JPA')

    def test_imports_parameters_locals_and_bean_factories_are_not_fields(self):
        for library in CLIENT_FIELDS:
            simple = library.rsplit('.', 1)[-1]
            with self.subTest(library=library):
                source = f'''import {library};
class Configuration {{
    Configuration({simple} client) {{}}
    void use({simple} client) {{ {simple} local = client; }}
    @Bean {simple} client() {{ return new {simple}(); }}
}}
'''
                self.assertEqual(self.extract(source), ())

    def test_unrelated_simple_names_wildcards_and_custom_subclasses_are_excluded(self):
        for library in CLIENT_FIELDS:
            package, _, simple = library.rpartition('.')
            with self.subTest(library=library):
                sources = (
                    f'class Gateway {{ {simple} client; }}',
                    f'import other.{simple}; class Gateway {{ {simple} client; }}',
                    f'import {package}.*; class Gateway {{ {simple} client; }}',
                    f'import {library}; class Custom extends {simple} {{}} '
                    'class Gateway { Custom client; }',
                    f'import {library}; class {simple} {{}} '
                    f'class Gateway {{ {simple} client; }}',
                    f'import {library}; class Gateway<{simple}> {{ {simple} client; }}',
                    f'import {library}; class Gateway {{ '
                    f'class {simple} {{}} {simple} client; }}',
                    f'import {library}; import other.{simple}; '
                    f'class Gateway {{ {simple} client; }}',
                    f'import {library}; class Gateway {{ '
                    f'{simple}[] clients; {simple} other[]; }}',
                )
                for source in sources:
                    self.assertEqual(self.extract(source), (), source)

    def test_repository_is_direct_only_and_not_repeated_for_typed_fields(self):
        declarations = self.extract('''package shop;
import org.springframework.data.jpa.repository.JpaRepository;
interface Parent<T> {}
interface Orders extends Parent<Order>, JpaRepository<Order, Long> {}
interface Specialized extends Orders {}
class Gateway { Orders first; Orders second; Specialized third; }
class NotARepository extends JpaRepository<Order, Long> {}
interface Wrong extends other.JpaRepository<Order, Long> {}
''')
        self.assertEqual([(d.declaring_type, d.field_name) for d in declarations],
                         [('shop.Orders', None)])

    def test_multiple_fields_have_separate_identity_and_name_citations(self):
        declarations = self.extract('''package shop;
import org.springframework.jdbc.core.JdbcTemplate;
class Gateway {
    JdbcTemplate first = new JdbcTemplate(),
        second = new JdbcTemplate();
}
''')
        self.assertEqual([(d.field_name, d.line) for d in declarations],
                         [('first', 4), ('second', 5)])
        self.assertEqual(len({d.identity for d in declarations}), 2)

    def test_feign_is_retained_with_annotation_evidence(self):
        declarations = self.extract('''package shop;
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient(name = "products")
public interface Products {}
''')
        self.assertEqual(len(declarations), 1)
        self.assertEqual((declarations[0].mechanism, declarations[0].declaring_type,
                          declarations[0].line), ('OpenFeign', 'shop.Products', 3))

    def test_repeated_index_entries_do_not_duplicate_findings(self):
        index = index_source('class Gateway { '
                             'org.springframework.jdbc.core.JdbcTemplate client; }',
                             self.path)
        repeated = SourceIndex(index.types * 2, index.declared_type_names)
        self.assertEqual(declarations_from_index(repeated),
                         declarations_from_index(index))

    def test_module_scope_and_source_defined_library_exclusion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            java = root / 'src/main/java'
            java.mkdir(parents=True)
            files = {
                'src/main/java/shop/Gateway.java': '''package shop;
import org.springframework.jdbc.core.JdbcTemplate;
class Gateway { JdbcTemplate jdbc; org.springframework.web.client.RestTemplate rest; }
''',
                # Even an unindexed record with a canonical Spring name is local source.
                'src/main/java/spring/JdbcTemplate.java':
                    'package org.springframework.jdbc.core; record JdbcTemplate() {}',
                'src/test/java/Test.java':
                    'class Test { org.springframework.web.client.RestTemplate ignored; }',
                'Other.java':
                    f'interface Ignored extends {JPA_REPOSITORY}<Order, Long> {{}}',
            }
            for relative, source in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding='utf-8')
            before = {relative: (root / relative).read_bytes() for relative in files}
            module = load_module(str(root))
            declarations = discover_declarations(module)
            self.assertEqual([(d.declaring_type, d.field_name) for d in declarations],
                             [('shop.Gateway', 'rest')])
            self.assertEqual(declarations, discover_declarations(module))
            self.assertEqual(before, {relative: (root / relative).read_bytes()
                                      for relative in files})


if __name__ == '__main__':
    unittest.main()
