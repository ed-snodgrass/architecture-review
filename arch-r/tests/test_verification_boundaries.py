"""Final verification contracts; disposable source only, no Java execution."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from archr.cli import main


ENTRY_POINT = Path(__file__).resolve().parents[1] / 'arch-r'


class VerificationBoundaryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='arch_r_verification_')
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.module = self.work / 'orders'
        self.put('orders/pom.xml', '<project><artifactId>orders</artifactId></project>')
        self.put('orders/src/main/java/sample/Client.java', '''package sample;
import org.springframework.cloud.openfeign.FeignClient;
@FeignClient(name="products", url="${products.url}")
public interface Client { String get(String id); }
''')
        self.put('orders/src/main/java/sample/Order.java', '''package sample;
class Order {
    final Client client;
    Order(Client client) { this.client = client; }
    String place(String id) { return this.client.get(id); }
}
''')
        self.output = self.work / 'arch-r-report-orders.md'

    def put(self, relative, content):
        path = self.work / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def snapshot(self):
        # Include directories and permission bits, not only Java file contents.
        return {str(p.relative_to(self.work)):
                (p.stat().st_mode, p.read_bytes() if p.is_file() else None)
                for p in self.work.rglob('*')}

    def test_analysis_does_not_launch_processes_or_change_input_tree(self):
        before = self.snapshot()
        stdout, stderr = io.StringIO(), io.StringIO()
        old_cwd = Path.cwd()
        try:
            os.chdir(self.work)
            with ExitStack() as stack:
                # Fail at common process-launch boundaries, rather than merely
                # trusting report claims that Java was not compiled or run.
                for target in ('subprocess.Popen', 'os.system', 'os.execv',
                               'os.execve', 'os.posix_spawn', 'os.posix_spawnp'):
                    stack.enter_context(patch(target, side_effect=AssertionError(
                        'Source-only analysis must not launch a process: ' + target)))
                stack.enter_context(redirect_stdout(stdout))
                stack.enter_context(redirect_stderr(stderr))
                self.assertEqual(main(['analyze', str(self.module)]), 0)
        finally:
            os.chdir(old_cwd)
        self.assertEqual(stderr.getvalue(), '')
        after = self.snapshot()
        self.assertEqual(set(after) - set(before), {'arch-r-report-orders.md'})
        self.assertEqual(before, {key: after[key] for key in before})
        report = self.output.read_text(encoding='utf-8')
        self.assertIn('sample.Order', report)
        self.assertIn('sample.Client', report)
        self.assertIn('src/main/java/sample/Order.java:5', report)

    def test_excluded_sources_and_configuration_are_not_read_or_reported(self):
        excluded = set()
        for relative in ('orders/src/test/java/TestCaller.java',
                         'orders/target/generated-sources/GeneratedCaller.java',
                         'orders/src/main/resources/ResourceCaller.java',
                         'other/src/main/java/OtherCaller.java',
                         'orders/src/main/java/not-java.txt',
                         'orders/src/main/resources/application.properties',
                         'orders/src/main/resources/application.yml'):
            excluded.add(self.put(relative, 'OUTSIDE_BOUNDARY_SENTINEL').resolve())
        # Invalid UTF-8 would also expose accidental Java scanning outside scope.
        for path in excluded:
            if path.suffix == '.java':
                path.write_bytes(b'\xff OUTSIDE_BOUNDARY_SENTINEL')
        before = self.snapshot()
        original_open, original_io_open = open, io.open

        def guarded(opener):
            def checked(file, *args, **kwargs):
                if isinstance(file, (str, bytes, os.PathLike)):
                    self.assertNotIn(Path(os.fsdecode(file)).resolve(), excluded,
                                     'Analysis opened an excluded input')
                return opener(file, *args, **kwargs)
            return checked

        old_cwd = Path.cwd()
        try:
            os.chdir(self.work)
            with patch('builtins.open', guarded(original_open)), \
                    patch('io.open', guarded(original_io_open)), \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main(['analyze', str(self.module)]), 0)
        finally:
            os.chdir(old_cwd)
        report = self.output.read_text(encoding='utf-8')
        self.assertNotIn('OUTSIDE_BOUNDARY_SENTINEL', report)
        self.assertIn('${products.url}', report)
        self.assertIn('destination unresolved', report)
        self.assertIn('sample.Order', report)
        after = self.snapshot()
        self.assertEqual(set(after) - set(before), {'arch-r-report-orders.md'})
        self.assertEqual(before, {key: after[key] for key in before})

    def test_cli_has_no_depth_configuration_or_alternative_output_flags(self):
        before = self.snapshot()
        for extra in (['--depth', '3'], ['--max-depth', '3'],
                      ['--config', 'settings.yml'], ['--format', 'json'],
                      ['--output', 'other.md']):
            with self.subTest(arguments=extra):
                result = subprocess.run(
                    [str(ENTRY_POINT), 'analyze', str(self.module), *extra],
                    cwd=self.work, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('unrecognized arguments', result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertEqual(before, self.snapshot())
        result = subprocess.run([str(ENTRY_POINT), 'analyze', '--help'],
                                cwd=self.work, capture_output=True, text=True,
                                timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('spring_module_path', result.stdout)
        for flag in ('--depth', '--max-depth', '--config', '--format', '--output'):
            self.assertNotIn(flag, result.stdout)
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
