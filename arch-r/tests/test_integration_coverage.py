"""Expanded integrations preserve brief coverage and opt-in CLI details."""
import unittest

from tests import test_coverage_mode_preservation as modes
from tests import test_untraced_call_coverage as fixtures


class IntegrationCoverageTests(unittest.TestCase):
    setUp = fixtures.UntracedCallCoverageTests.setUp
    put = fixtures.UntracedCallCoverageTests.put
    snapshot = fixtures.UntracedCallCoverageTests.snapshot
    run_cli = fixtures.UntracedCallCoverageTests.run_cli
    report = fixtures.UntracedCallCoverageTests.report
    assert_coverage = fixtures.UntracedCallCoverageTests.assert_coverage
    split_coverage = modes.CoverageModePreservationTests.split_coverage

    def clients(self, body):
        self.put('Gateway', '''package sample;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.reactive.function.client.WebClient;
class Gateway {
    JdbcTemplate jdbc;
    RestTemplate rest;
    WebClient client;
    Repo repo;
    void run(String sql, String url, Object verb, Request request) {
''' + body + '''
    }
}
''')
        self.put('Repo', '''package sample;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
interface Repo extends JpaRepository<Order, Long> {
    @Query(value = Queries.TEXT, nativeQuery = Flags.NATIVE)
    Order lookup();
}
''')

    def test_integration_uncertainty_does_not_create_coverage_gaps(self):
        self.clients('''
jdbc.query(sql);
rest.getForObject(url, String.class);
repo.lookup();
client.method(verb).uri(url).retrieve().bodyToMono(String.class);
''')
        default = self.report()
        self.assert_coverage(default, 0)
        self.assertIn('Found 4 integration declarations: 2 HTTP and 2 database.', default)
        self.assertIn('unresolved', default.lower())
        for before in (False, True):
            self.assertEqual(default, self.report(details=True, before=before))

    def test_details_change_only_coverage_with_new_libraries(self):
        self.clients('''
jdbc.query(sql);
rest.getForObject(url, String.class);
repo.lookup();
client.get().uri("/items").retrieve().bodyToMono(String.class);
request.coverageOnlyGap();
''')
        default = self.report()
        brief, architecture = self.split_coverage(default)
        self.assert_coverage(default, 1)
        self.assertNotIn('coverageOnlyGap', default)
        for before in (False, True):
            detailed = self.report(details=True, before=before)
            coverage, unchanged = self.split_coverage(detailed)
            self.assertEqual(architecture, unchanged)
            self.assertIn(brief.strip(), coverage)
            self.assertIn('request.coverageOnlyGap', coverage)
            self.assertNotIn('unsupported-receiver', coverage)
            self.assert_coverage(detailed, 1)
            self.assertEqual(detailed, self.report(details=True, before=before))

    def test_fluent_segments_do_not_hide_nested_argument_gap(self):
        self.clients('''
client.get().uri(request.path()).retrieve().bodyToMono(String.class);
client.post().uri("/builder").header("x", "y");
''')
        detailed = self.report(details=True)
        self.assert_coverage(detailed, 1)
        coverage, _ = self.split_coverage(detailed)
        self.assertIn('request.path', coverage)
        self.assertNotIn('<chained expression>', coverage)
        self.assertIn('Request-builder configuration only', detailed)

    def test_split_chain_remains_outside_supported_receiver_scope(self):
        self.clients('''
var builder = client.get().uri("/items");
builder.retrieve().bodyToMono(String.class);
''')
        default = self.report()
        self.assert_coverage(default, 2)
        self.assertIn('**Status:** No caller found', default)
        coverage, architecture = self.split_coverage(self.report(details=True))
        self.assertIn('builder.retrieve', coverage)
        self.assertIn('bodyToMono', coverage)
        self.assertNotIn('Observed source operation call', architecture)


if __name__ == '__main__':
    unittest.main()
