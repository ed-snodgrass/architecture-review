"""Verify expanded reports remain deterministic, bounded and read-only."""
import os
import subprocess
import unittest

from tests import test_iteration_004_acceptance as fixtures


class Iteration004VerificationTests(unittest.TestCase):
    setUp = fixtures.Iteration004AcceptanceTests.setUp
    source = fixtures.Iteration004AcceptanceTests.source

    def snapshot(self):
        return {str(path.relative_to(self.caller)):
                (path.stat().st_mode, path.stat().st_mtime_ns,
                 path.read_bytes() if path.is_file() else None)
                for path in self.caller.rglob('*') if path != self.output}

    def invoke(self, details, seed, path=None, flag_first=False):
        args = ['analyze', str(path or self.module)]
        if details:
            args.insert(1 if flag_first else len(args), '--show-analysis-limitations')
        return subprocess.run(
            [str(fixtures.ENTRY_POINT), *args], cwd=self.caller,
            env={**os.environ, 'PYTHONHASHSEED': seed},
            capture_output=True, text=True, timeout=30)

    def test_expanded_reports_repeat_and_fail_without_mutating_inputs(self):
        self.source('Integrations.java', '''
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.reactive.function.client.WebClient;
@FeignClient(name="products")
interface Products { @GetMapping("/items") String items(); }
interface Orders extends JpaRepository<Order, Long> {
 @Query("''' + '界' * 101 + '''PRIVATE_QUERY_TAIL") Order lookup();
}
class Gateway {
 Orders orders; JdbcTemplate jdbc; RestTemplate rest; WebClient web; Products products;
 void call() {
  orders.save(null);
  jdbc.query("''' + '界' * 101 + '''PRIVATE_QUERY_TAIL", mapper);
  rest.getForObject("/items", String.class);
  web.get().uri("/items").retrieve().bodyToMono(String.class);
  products.items();
 }
}
class Service { Gateway gateway; void run() { gateway.call(); } }
''')
        (self.caller / 'notes.txt').write_bytes(b'Caller-owned file\n')
        before = self.snapshot()
        expected = {}
        for details, seed, flag_first in (
                (False, '1', False), (True, '1', False),
                (True, '17', True), (False, '17', False),
                (True, '93', False), (False, '93', False)):
            with self.subTest(details=details, seed=seed, flag_first=flag_first):
                result = self.invoke(details, seed, flag_first=flag_first)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, '')
                report = self.output.read_bytes()
                text = report.decode('utf-8')
                self.assertIn('Found 5 integration declarations: 3 HTTP and 2 database.', text)
                self.assertIn('Service → Gateway', text)
                self.assertIn('界' * 99 + '…', text)
                self.assertNotIn('界' * 100, text)
                self.assertNotIn('PRIVATE_QUERY_TAIL', text)
                if details in expected:
                    self.assertEqual(expected[details], report)
                expected[details] = report
                self.assertEqual(before, self.snapshot())

                # Preserve the actual successful expanded report in either mode.
                failed = self.invoke(not details, seed, self.caller / 'missing')
                self.assertEqual(failed.returncode, 1)
                self.assertEqual(failed.stdout, '')
                self.assertIn('arch-r:', failed.stderr)
                self.assertNotIn('Traceback', failed.stderr)
                self.assertEqual(report, self.output.read_bytes())
                self.assertEqual(before, self.snapshot())

        broken = self.java / 'Broken.java'
        broken.write_bytes(b'\xff')
        before = self.snapshot()
        for details in (False, True):
            failed = self.invoke(details, '1')
            self.assertEqual(failed.returncode, 1)
            self.assertIn('Cannot read Java sources', failed.stderr)
            self.assertEqual(expected[False], self.output.read_bytes())
            self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
