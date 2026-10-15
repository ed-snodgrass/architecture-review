"""JPA query metadata is declaration evidence, not execution evidence."""
import tempfile
from pathlib import Path
import unittest

from archr.findings import discover_findings
from archr.module import load_module


class RepositoryQueryTests(unittest.TestCase):
    def finding(self, methods, imports='import org.springframework.data.jpa.repository.Query;'):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'src/main/java/Repo.java'
            source.parent.mkdir(parents=True)
            source.write_text('import org.springframework.data.jpa.repository.JpaRepository;\n'
                              + imports + '\ninterface Repo extends JpaRepository<Item, Long> {\n'
                              + methods + '\n}', encoding='utf-8')
            finding, = discover_findings(load_module(directory))
            return finding

    def test_languages_and_declaration_only_evidence(self):
        finding = self.finding('''@Query("select x from Item x") Object first();
@Query(value="select * from items", nativeQuery=true) Object second();
@Query(nativeQuery=false, value="select y from Item y") Object third();
@Query(value="select 1", nativeQuery=Settings.NATIVE) Object fourth();''')
        self.assertEqual([op.query.language for op in finding.operations],
                         ['JPQL', 'SQL', 'JPQL', 'Query (language unresolved)'])
        self.assertFalse(finding.has_supported_caller)
        self.assertEqual(finding.status_label, 'Declared integration — No supported caller found')
        self.assertEqual(finding.destination.label, 'Destination unknown')
        self.assertEqual([op.query.line for op in finding.operations], [4, 5, 6, 7])
        self.assertTrue(all(op.query.source_path.endswith('Repo.java') for op in finding.operations))

    def test_text_blocks_and_literals_share_bounded_normalization(self):
        finding = self.finding('@Query("""\n select   x\n from Item x\n """) Object first();'
                               + '@Query("' + '界' * 100 + '") Object second();'
                               + '@Query("' + '界' * 101 + '") Object third();')
        self.assertEqual([op.query.preview for op in finding.operations],
                         ['select x from Item x', '界' * 100, '界' * 99 + '…'])

    def test_expressions_are_unresolved_and_named_queries_not_extracted(self):
        finding = self.finding('''@Query(SQL) Object first();
@Query("select " + SQL) Object second();
@Query(name="named.query") Object third();
@Query(value=makeSql("hidden"), nativeQuery=true) Object fourth();''')
        self.assertEqual([op.method_name for op in finding.operations],
                         ['first', 'second', 'fourth'])
        self.assertTrue(all(op.query.preview is None for op in finding.operations))

    def test_exact_annotation_type_and_member_boundaries(self):
        finding = self.finding('''@Query("not Spring") Object first();
@org.springframework.data.jpa.repository.Query("select x from Item x") Object second();
Object third(@org.springframework.data.jpa.repository.Query("not method metadata") String x);''',
                               'import other.Query;')
        self.assertEqual([op.method_name for op in finding.operations], ['second'])
        self.assertFalse(self.finding('@Query("not imported") Object first();', '').operations)

    def test_same_line_overloads_keep_their_own_annotation(self):
        finding = self.finding('@Query("first") Object get(); @Query("second") Object get(int x);')
        self.assertEqual([op.query.preview for op in finding.operations], ['first', 'second'])


if __name__ == '__main__':
    unittest.main()
