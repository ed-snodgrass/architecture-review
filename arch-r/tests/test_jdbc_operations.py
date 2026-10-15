"""JdbcTemplate endpoints preserve calls independently of SQL availability."""
import tempfile
from pathlib import Path
import unittest

from archr.findings import discover_findings
from archr.indexing import index_source
from archr.interfaces import resolve_interface_index
from archr.module import load_module
from archr.resolution import JDBC_OPERATIONS, resolve_index


class JdbcOperationTests(unittest.TestCase):
    def findings(self, body):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'src/main/java/Gateway.java'
            source.parent.mkdir(parents=True)
            source.write_text('''import org.springframework.jdbc.core.JdbcTemplate;
class Gateway {
 JdbcTemplate jdbc, other;
 void run(String sql) { ''' + body + ''' }
}
class Service { Gateway gateway; void act() { gateway.run(null); } }
''', encoding='utf-8')
            return discover_findings(load_module(directory))

    def test_all_operations_and_two_step_chains(self):
        findings = self.findings(''.join(
            f'this.jdbc.{name}("select 1");' for name in sorted(JDBC_OPERATIONS)))
        jdbc, other = findings
        self.assertEqual({op.method_name for op in jdbc.operations}, JDBC_OPERATIONS)
        self.assertTrue(all(op.query.preview == 'select 1' for op in jdbc.operations))
        self.assertTrue(all(len(chain.steps) == 2 for chain in jdbc.chains))
        self.assertTrue(jdbc.has_supported_caller)
        self.assertFalse(other.has_supported_caller)
        self.assertEqual(jdbc.destination.label, 'Destination unknown')

    def test_literal_sql_without_upstream_caller_keeps_direct_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'src/main/java/Gateway.java'
            source.parent.mkdir(parents=True)
            source.write_text('''class Gateway {
 org.springframework.jdbc.core.JdbcTemplate jdbc;
 void run() {
  this.jdbc.queryForObject("select 1", Integer.class);
 }
}''', encoding='utf-8')
            finding, = discover_findings(load_module(directory))
        operation, = finding.operations
        chain, = finding.chains
        self.assertTrue(finding.has_supported_caller)
        self.assertEqual(operation.method_name, 'queryForObject')
        self.assertEqual(operation.query.preview, 'select 1')
        self.assertEqual(operation.evidence[0].line, 4)
        self.assertEqual(operation.query.line, 4)
        self.assertEqual(len(chain.steps), 1)
        self.assertEqual(chain.steps[0].link.receiver_field.line, 2)
        self.assertEqual(finding.destination.label, 'Destination unknown')

    def test_unknown_sql_overloads_remain_calls(self):
        jdbc, _ = self.findings('''jdbc.query(sql, mapper);
 jdbc.execute(callback); jdbc.batchUpdate(new String[]{"select 1"});
 jdbc.update("select " + sql); jdbc.queryForObject(makeSql(), String.class);
 jdbc.toString(); jdbc.unknown();''')
        self.assertEqual(len(jdbc.operations), 5)
        self.assertTrue(all(op.query.preview is None for op in jdbc.operations))
        self.assertTrue(jdbc.has_supported_caller)

    def test_each_operation_keeps_nonliteral_sql_call_evidence(self):
        jdbc, _ = self.findings(''.join(
            f'this.jdbc.{name}(sql);' for name in sorted(JDBC_OPERATIONS)))
        self.assertEqual({op.method_name for op in jdbc.operations}, JDBC_OPERATIONS)
        self.assertTrue(all(op.has_supported_caller for op in jdbc.operations))
        self.assertTrue(all(op.query.preview is None for op in jdbc.operations))
        self.assertEqual(len(jdbc.chains), len(JDBC_OPERATIONS))
        self.assertTrue(all(len(chain.steps) == 2 for chain in jdbc.chains))

    def test_unresolved_query_cites_first_argument_independently_of_call(self):
        jdbc, _ = self.findings('''this.jdbc.query(
 /* Do not evaluate this expression or extract its nested literal. */
 makeSql("not a query", sql), mapper);''')
        operation, = jdbc.operations
        self.assertIsNone(operation.query.preview)
        self.assertEqual(operation.query.line, operation.invocation.line + 2)
        self.assertEqual(operation.query.source_path, operation.invocation.source_path)
        self.assertTrue(operation.has_supported_caller)

    def test_text_block_normalization_and_unicode_bounds(self):
        jdbc, _ = self.findings('jdbc.query("""\n select   *\n from orders\n """, mapper);'
                               + 'jdbc.execute("' + '界' * 100 + '");'
                               + 'jdbc.update("' + '界' * 101 + '");')
        self.assertEqual([op.query.preview for op in jdbc.operations],
                         ['select * from orders', '界' * 100, '界' * 99 + '…'])
        self.assertTrue(all(op.query.source_path.endswith('Gateway.java')
                            and op.query.line > 0 for op in jdbc.operations))

    def test_unicode_escape_pairs_count_as_single_preview_characters(self):
        escaped = r'\uD83D\uDE00'
        jdbc, _ = self.findings('jdbc.execute("' + escaped * 100 + '");'
                               + 'jdbc.update("' + escaped * 101 + '");'
                               + 'jdbc.query("' + '😀' * 101 + '", mapper);')
        self.assertEqual([op.query.preview for op in jdbc.operations],
                         ['😀' * 100, '😀' * 99 + '…', '😀' * 99 + '…'])
        self.assertTrue(all(len(op.query.preview) == 100 for op in jdbc.operations))

    def test_text_block_line_continuations_respect_escaped_backslashes(self):
        jdbc, _ = self.findings('jdbc.query("""\nselect' + '\\' + '\n 1\n""", mapper);'
                               + 'jdbc.execute("""\nselect' + '\\\\' + '\n 2\n""");')
        self.assertEqual([op.query.preview for op in jdbc.operations],
                         ['select 1', 'select\\ 2'])

    def test_text_block_normalizes_cr_line_endings_before_continuations(self):
        jdbc, _ = self.findings('jdbc.query("""\rselect' + '\\' + '\r 1\r""", mapper);'
                               + 'jdbc.execute("""\r\nselect' + '\\' + '\r\n 2\r\n""");')
        self.assertEqual([op.query.preview for op in jdbc.operations],
                         ['select 1', 'select 2'])

    def test_text_block_indentation_is_removed_before_joining_sql_tokens(self):
        jdbc, _ = self.findings('jdbc.query("""\n'
                               '    sel' + '\\' + '\n'
                               '    ect 1\n'
                               '    """, mapper);')
        self.assertEqual(jdbc.operations[0].query.preview, 'select 1')

    def test_text_block_trailing_whitespace_is_removed_before_continuation(self):
        jdbc, _ = self.findings('jdbc.execute("""\n'
                               '    sel' + '\\' + '   \n'
                               '    ect 1\n'
                               '    """);')
        self.assertEqual(jdbc.operations[0].query.preview, 'select 1')

    def test_constructor_injected_field_keeps_nonliteral_call_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'src/main/java/Gateway.java'
            source.parent.mkdir(parents=True)
            source.write_text('''class Gateway {
 private final org.springframework.jdbc.core.JdbcTemplate jdbc;
 Gateway(org.springframework.jdbc.core.JdbcTemplate jdbc) { this.jdbc = jdbc; }
 void run(String sql) {
  this.jdbc.queryForList(sql);
 }
}''', encoding='utf-8')
            finding, = discover_findings(load_module(directory))
        operation, = finding.operations
        self.assertTrue(finding.has_supported_caller)
        self.assertEqual(operation.method_name, 'queryForList')
        self.assertIsNone(operation.query.preview)
        self.assertEqual(operation.evidence[0].line, 5)
        self.assertEqual(operation.query.line, 5)
        self.assertEqual(operation.query.source_path, operation.evidence[0].source_path)
        step, = finding.chains[0].steps
        self.assertEqual(step.link.receiver_field.name, 'jdbc')
        self.assertEqual(step.link.invocation.receiver, 'this.jdbc')

    def test_fields_do_not_share_calls(self):
        jdbc, other = self.findings('jdbc.execute("one"); other.execute("two");')
        self.assertEqual(jdbc.operations[0].query.preview, 'one')
        self.assertEqual(other.operations[0].query.preview, 'two')

    def test_shadowed_local_and_generic_receivers_not_followed(self):
        index = index_source('''import org.springframework.jdbc.core.JdbcTemplate;
class Gateway { JdbcTemplate jdbc;
 void run(JdbcTemplate jdbc) {
 jdbc.query("shadow"); this.jdbc.<String>query("generic");
 this.jdbc.query("ok");
 }
}''', 'Gateway.java')
        result = resolve_index(index)
        self.assertEqual(len(result.links), 1)
        self.assertEqual(len(result.diagnostics), 2)

    def test_unknown_operations_keep_declaration_without_caller(self):
        jdbc, _ = self.findings('jdbc.toString(); this.jdbc.unknown("not SQL");')
        self.assertEqual(jdbc.operations, ())
        self.assertEqual(jdbc.chains, ())
        self.assertEqual(jdbc.status_label,
                         'Declared integration — No supported caller found')
        self.assertEqual(jdbc.destination.label, 'Destination unknown')

    def test_same_line_calls_keep_independent_query_evidence(self):
        jdbc, _ = self.findings('jdbc.query("first", mapper); jdbc.query(sql, mapper);'
                               'this.jdbc.query("third", mapper);')
        self.assertEqual([op.query.preview for op in jdbc.operations],
                         ['first', None, 'third'])
        self.assertEqual(len(jdbc.chains), 3)

    def test_only_first_argument_supplies_sql_and_calls_keep_source_order(self):
        body = ('jdbc.query(sql, "not the query");'
                'jdbc.update("select\\n\\t1", value);'
                'jdbc.execute(callback);'
                'jdbc.batchUpdate("delete from orders", batches);')
        first, _ = self.findings(body)
        second, _ = self.findings(body)
        self.assertEqual(first, second)
        self.assertEqual([op.method_name for op in first.operations],
                         ['query', 'update', 'execute', 'batchUpdate'])
        self.assertEqual([op.query.preview for op in first.operations],
                         [None, 'select 1', None, 'delete from orders'])
        self.assertTrue(all(op.has_supported_caller for op in first.operations))
        self.assertTrue(all(op.destination.label == 'Destination unknown'
                            for op in first.operations))

    def test_nested_nonliteral_first_argument_does_not_become_sql(self):
        jdbc, _ = self.findings('jdbc.query(makeSql("not SQL", 1), mapper);'
                               'jdbc.execute();')
        self.assertEqual(len(jdbc.operations), 2)
        self.assertTrue(all(op.query.preview is None for op in jdbc.operations))
        self.assertTrue(jdbc.has_supported_caller)

    def test_upstream_branches_share_one_operation_not_unrelated_methods(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'src/main/java/Gateway.java'
            source.parent.mkdir(parents=True)
            source.write_text('''import org.springframework.jdbc.core.JdbcTemplate;
class Gateway {
 JdbcTemplate jdbc;
 void run(String sql) { jdbc.query(sql, mapper); }
 void unrelated() { jdbc.toString(); }
}
class Service {
 Gateway gateway;
 void first() { gateway.run(null); }
 void second() { gateway.run(null); }
 void unrelated() { gateway.unrelated(); }
}
''', encoding='utf-8')
            finding, = discover_findings(load_module(directory))
        self.assertEqual(len(finding.operations), 1)
        self.assertIsNone(finding.operations[0].query.preview)
        self.assertEqual(len(finding.chains), 2)
        self.assertEqual({chain.steps[1].link.caller_method.name
                          for chain in finding.chains}, {'first', 'second'})
        self.assertEqual(len(finding.supported_call_evidence), 1)
        self.assertEqual(finding.supported_call_evidence[0].line, 4)

    def test_library_operations_need_no_source_or_interface_route(self):
        index = index_source('''import org.springframework.jdbc.core.JdbcTemplate;
class Gateway {
 JdbcTemplate jdbc;
 void run(String sql) {
  jdbc.query(sql, mapper); this.jdbc.update("delete from orders");
 }
}''', 'Gateway.java')
        resolution = resolve_index(index)
        self.assertEqual(len(resolution.links), 2)
        self.assertEqual(resolution.diagnostics, ())
        routes = resolve_interface_index(index)
        self.assertEqual(routes.connections, ())
        self.assertEqual(routes.diagnostics, ())
        for link in resolution.links:
            self.assertEqual(link.target_method.parameter_count,
                             link.invocation.argument_count)
            self.assertEqual(link.target_type,
                             'org.springframework.jdbc.core.JdbcTemplate')

    def test_repository_and_jdbc_operations_keep_separate_findings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'src/main/java/Gateway.java'
            source.parent.mkdir(parents=True)
            source.write_text('''import org.springframework.jdbc.core.JdbcTemplate;
interface Orders extends org.springframework.data.jpa.repository.JpaRepository<Order, Long> {}
class Gateway {
 Orders orders; JdbcTemplate jdbc, other;
 void store() { orders.save(null); jdbc.update("insert into orders values (1)"); }
 void unrelated() { other.toString(); }
}
class Service { Gateway gateway; void run() { gateway.store(); } }
''', encoding='utf-8')
            findings = discover_findings(load_module(directory))
        repository, jdbc, other = findings
        self.assertEqual([op.method_name for op in repository.operations], ['save'])
        self.assertEqual([op.method_name for op in jdbc.operations], ['update'])
        self.assertEqual(jdbc.operations[0].query.preview,
                         'insert into orders values (1)')
        self.assertTrue(all(len(finding.chains[0].steps) == 2
                            for finding in (repository, jdbc)))
        self.assertFalse(other.has_supported_caller)
        self.assertEqual(other.operations, ())

    def test_same_named_fields_in_different_classes_keep_separate_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / 'src/main/java'
            sources.mkdir(parents=True)
            for name, sql in [('First', 'select 1'), ('Second', 'select 2')]:
                (sources / f'{name}.java').write_text(
                    f'''class {name} {{
 org.springframework.jdbc.core.JdbcTemplate jdbc;
 void run() {{ this.jdbc.query("{sql}", mapper); }}
}}''', encoding='utf-8')
            findings = discover_findings(load_module(directory))
        self.assertEqual([f.declaration.declaring_type for f in findings],
                         ['First', 'Second'])
        self.assertEqual([f.operations[0].query.preview for f in findings],
                         ['select 1', 'select 2'])
        for finding in findings:
            self.assertEqual(len(finding.chains), 1)
            self.assertEqual(finding.chains[0].steps[0].link.caller_type,
                             finding.declaration.declaring_type)

    def test_multiline_argument_cites_literal_not_invocation_line(self):
        jdbc, _ = self.findings('''jdbc.query(
 /* SQL preview comes only from the first argument. */
 "select 'comma, parentheses()' from orders",
 mapper);''')
        operation, = jdbc.operations
        self.assertEqual(operation.query.preview,
                         "select 'comma, parentheses()' from orders")
        self.assertEqual(operation.query.line, operation.invocation.line + 2)
        self.assertEqual(operation.evidence[0].line, operation.invocation.line)

    def test_possible_interface_upstream_preserves_jdbc_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'src/main/java/Gateway.java'
            source.parent.mkdir(parents=True)
            source.write_text('''import org.springframework.jdbc.core.JdbcTemplate;
interface Port { void store(); }
class Gateway implements Port {
 JdbcTemplate jdbc;
 public void store() { jdbc.update("delete from orders"); }
}
class Service { Port port; void run() { port.store(); } }
''', encoding='utf-8')
            finding, = discover_findings(load_module(directory))
        operation, = finding.operations
        chain, = finding.chains
        self.assertEqual(operation.query.preview, 'delete from orders')
        self.assertEqual(len(chain.steps), 2)
        self.assertEqual(chain.certainty, 'possible')
        self.assertEqual(chain.steps[0].certainty, 'observed')
        self.assertEqual(chain.steps[1].certainty, 'possible')
        self.assertEqual(chain.steps[0].link.receiver_field.name, 'jdbc')
        self.assertEqual(finding.destination.label, 'Destination unknown')

    def test_source_defined_spring_type_is_not_library_endpoint(self):
        index = index_source('''package org.springframework.jdbc.core;
class JdbcTemplate { void execute(String sql) {} }
class Gateway { JdbcTemplate jdbc; void run() { jdbc.query("no"); } }
''', 'Gateway.java')
        self.assertEqual(resolve_index(index).links, ())


if __name__ == '__main__':
    unittest.main()
