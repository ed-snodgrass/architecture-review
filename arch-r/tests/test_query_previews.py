"""Shared JDBC/JPA preview bounds apply before Markdown and coverage rendering."""
import tempfile
from pathlib import Path
import unittest

from archr.discovery import discover_clients, tokenize
from archr.findings import discover_findings
from archr.module import load_module
from archr.queries import normalize_query_preview, query_preview
from archr.report import _query_lines, render_report
from archr.traversal import trace_usage


class QueryPreviewTests(unittest.TestCase):
    def test_normalization_precedes_unicode_truncation(self):
        for character in ('界', '😀', '&'):
            with self.subTest(character=character):
                self.assertEqual(normalize_query_preview(' \n' + character * 100 + '\t'),
                                 character * 100)
                self.assertEqual(normalize_query_preview(character * 101),
                                 character * 99 + '…')
        self.assertEqual(normalize_query_preview('  select\t*\n from   items  '),
                         'select * from items')
        self.assertEqual(normalize_query_preview(' \n\t'), '')

    def test_surrogate_escapes_and_expressions(self):
        self.assertEqual(query_preview(tokenize('"' + r'\uD83D\uDE00' * 101 + '"')),
                         '😀' * 99 + '…')
        for expression in ('SQL', '"select " + SQL', '"one" + "two"', 'sql("hidden")'):
            with self.subTest(expression=expression):
                self.assertIsNone(query_preview(tokenize(expression)))

    def test_shared_evidence_and_rendering_do_not_retain_full_queries(self):
        query = '&' * 101 + 'SECRET_QUERY_TAIL'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'src/main/java'
            root.mkdir(parents=True)
            (root / 'Repo.java').write_text(
                'import org.springframework.data.jpa.repository.JpaRepository;\n'
                'import org.springframework.data.jpa.repository.Query;\n'
                'interface Repo extends JpaRepository<Item, Long> {\n'
                '@Query("' + query + '") Object find();\n'
                '@Query("select " + SQL) Object unresolved();\n}', encoding='utf-8')
            (root / 'Gateway.java').write_text(
                'import org.springframework.jdbc.core.JdbcTemplate;\n'
                'class Gateway { JdbcTemplate jdbc;\n'
                'void call() { jdbc.query("""\n  ' + query + '\n  """, mapper);\n'
                'jdbc.query("select " + SQL, mapper);\n'
                'unknown.send("' + query + '"); }\n}', encoding='utf-8')
            module = load_module(directory)
            evidence = [op.query for finding in discover_findings(module)
                        for op in finding.operations if op.query is not None]
            self.assertEqual(len(evidence), 4)
            self.assertEqual([q.preview for q in evidence].count('&' * 99 + '…'), 2)
            self.assertEqual(sum(q.preview is None for q in evidence), 2)
            for item in evidence:
                rendered = '\n'.join(_query_lines(item))
                self.assertIn(f'{item.source_path}:{item.line}', rendered)
                if item.preview is None:
                    self.assertIn('Unresolved query expression (not evaluated)', rendered)
                else:
                    self.assertIn('&#38;' * 99 + '…', rendered)
                self.assertNotIn('SECRET_QUERY_TAIL', rendered)
            usage = trace_usage(module)
            self.assertTrue(usage.untraced_sites)
            for detailed in (False, True):
                report = render_report(module, discover_clients(module), usage,
                                       show_analysis_limitations=detailed)
                self.assertNotIn('SECRET_QUERY_TAIL', report)
                self.assertNotIn(query, report)


if __name__ == '__main__':
    unittest.main()
