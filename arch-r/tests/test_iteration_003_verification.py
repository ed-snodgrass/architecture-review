"""Final iteration 003 verification through the CLI and filesystem boundaries."""
from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from archr.cli import main
from tests import test_untraced_call_coverage as fixtures


class Iteration003VerificationTests(unittest.TestCase):
    setUp = fixtures.UntracedCallCoverageTests.setUp
    put = fixtures.UntracedCallCoverageTests.put
    client = fixtures.UntracedCallCoverageTests.client
    seven_sites = fixtures.UntracedCallCoverageTests.seven_sites
    run_cli = fixtures.UntracedCallCoverageTests.run_cli

    def tree_snapshot(self):
        # Ignore access times (reads may update them); check contents, permissions,
        # directory membership and modification times of everything but output.
        return {str(p.relative_to(self.work)):
                (p.stat().st_mode, p.stat().st_mtime_ns,
                 p.read_bytes() if p.is_file() else None)
                for p in self.work.rglob('*') if p != self.output}

    def successful_report(self, details):
        result = self.run_cli(details=details)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        data = self.output.read_bytes()
        self.assertIn(b'7 call sites were not traced', data)
        self.assertEqual(b'request.getId' in data, details)
        return data

    def test_repeat_and_switch_modes_are_stable_across_process_hash_seeds(self):
        self.seven_sites()
        (self.work / 'notes.txt').write_bytes(b'Caller-owned file\n')
        (self.work / 'arch-r-report-other.md').write_bytes(b'Other report\n')
        before = self.tree_snapshot()
        expected = {}
        # Separate processes, varied hash iteration order, consecutive repeats,
        # both switch directions, and both flag positions.
        for details, flag_before, seed in (
                (False, False, '1'), (False, False, '17'),
                (True, False, '1'), (True, True, '17'),
                (False, False, '93'), (True, False, '93'),
                (False, False, '1')):
            with self.subTest(details=details, flag_before=flag_before, seed=seed):
                args = ['analyze', str(self.module)]
                if details:
                    args.insert(1 if flag_before else len(args), fixtures.FLAG)
                result = subprocess.run(
                    [str(fixtures.ENTRY_POINT), *args], cwd=self.work,
                    env={**os.environ, 'PYTHONHASHSEED': seed},
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, '')
                data = self.output.read_bytes()
                self.assertIn(b'7 call sites were not traced', data)
                self.assertEqual(b'request.getId' in data, details)
                if details in expected:
                    self.assertEqual(expected[details], data)
                expected[details] = data
                self.assertEqual(before, self.tree_snapshot(),
                                 'Only the established report may change')
        self.assertNotEqual(expected[False], expected[True])
        self.assertEqual(self.output.read_bytes(), expected[False])

    def test_invalid_inputs_preserve_actual_successful_reports_in_either_mode(self):
        self.seven_sites()
        not_directory = self.work / 'not-a-directory'
        not_directory.write_text('Not a module', encoding='utf-8')
        no_sources = self.work / 'no-sources'
        no_sources.mkdir()
        for prior_details in (False, True):
            previous = self.successful_report(prior_details)
            for details in (False, True):
                for invalid, message in (
                        (self.work / 'missing', 'Directory does not exist'),
                        (not_directory, 'Not a directory'),
                        (no_sources, 'Directory does not exist')):
                    with self.subTest(prior=prior_details, details=details,
                                      invalid=invalid.name):
                        before = self.tree_snapshot()
                        result = self.run_cli(details=details, path=invalid)
                        self.assertEqual(result.returncode, 1)
                        self.assertEqual(result.stdout, '')
                        self.assertIn('arch-r:', result.stderr)
                        self.assertIn(message, result.stderr)
                        self.assertNotIn('Traceback', result.stderr)
                        self.assertEqual(previous, self.output.read_bytes())
                        self.assertEqual(before, self.tree_snapshot())
                # An analysis failure inside an otherwise valid module must
                # preserve the report too, not just invalid module paths.
                broken = self.module / 'src/main/java/sample/Broken.java'
                broken.write_bytes(b'\xff')
                try:
                    before = self.tree_snapshot()
                    result = self.run_cli(details=details)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, '')
                    self.assertIn('Cannot read Java sources', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
                    self.assertEqual(previous, self.output.read_bytes())
                    self.assertEqual(before, self.tree_snapshot())
                finally:
                    broken.unlink()

    def test_create_write_and_replace_failures_preserve_both_prior_modes(self):
        self.seven_sites()
        real_temporary_file = tempfile.NamedTemporaryFile

        def failing_write(*args, **kwargs):
            output = real_temporary_file(*args, **kwargs)
            output.write = Mock(side_effect=OSError('injected write failure'))
            return output

        failures = (
            ('create', 'archr.cli.tempfile.NamedTemporaryFile',
             PermissionError('injected creation failure')),
            ('write', 'archr.cli.tempfile.NamedTemporaryFile', failing_write),
            ('replace', 'archr.cli.os.replace', OSError('injected replace failure')),
        )
        for prior_details in (False, True):
            previous = self.successful_report(prior_details)
            for details in (False, True):
                for stage, target, effect in failures:
                    with self.subTest(prior=prior_details, details=details, stage=stage):
                        before = self.tree_snapshot()
                        stdout, stderr = io.StringIO(), io.StringIO()
                        old_cwd = Path.cwd()
                        try:
                            os.chdir(self.work)
                            args = ['analyze', str(self.module)]
                            if details:
                                args.append(fixtures.FLAG)
                            with patch(target, side_effect=effect), \
                                    redirect_stdout(stdout), redirect_stderr(stderr):
                                status = main(args)
                        finally:
                            os.chdir(old_cwd)
                        self.assertEqual(status, 1)
                        self.assertEqual(stdout.getvalue(), '')
                        self.assertIn('Cannot write report ' + self.output.name,
                                      stderr.getvalue())
                        self.assertNotIn('Traceback', stderr.getvalue())
                        self.assertEqual(previous, self.output.read_bytes())
                        self.assertEqual(before, self.tree_snapshot(),
                                         'Failures must clean temporary artifacts')


if __name__ == '__main__':
    unittest.main()
