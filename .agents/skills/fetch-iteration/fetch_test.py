"""Run with python3 .agents/skills/fetch-iteration/fetch_test.py (no network)."""

import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest


class FetchTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "student factory"
        self.script = self.root / ".agents/skills/fetch-iteration/fetch.sh"
        self.script.parent.mkdir(parents=True)
        shutil.copy2(Path(__file__).with_name("fetch.sh"), self.script)
        self.iterations = self.base / "course/docs/iterations"
        self.iterations.mkdir(parents=True)
        ledger = []
        for number in range(1, 5):
            name = f"{number:03d}-homework"
            ledger.append(f"| {number:03d} | [Homework]({name}/README.md) |")
            folder = self.iterations / name
            (folder / "features").mkdir(parents=True)
            (folder / "README.md").write_text(f"Homework {number}\n")
            (folder / "FACTORY.md").write_text(f"Factory {number}\n")
            (folder / "features" / f"{number}.feature").write_text("Feature: Example\n")
            (folder / "spec.md").write_text(f"Seed {number}\n")
        (self.iterations / "README.md").write_text("\n".join(ledger))
        archive = self.base / "course.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(self.base / "course", arcname="tutorial-main")
        fake_bin = self.base / "bin"
        fake_bin.mkdir()
        curl = fake_bin / "curl"
        curl.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$CURL_ARGS"\ncat "$COURSE_ARCHIVE"\n')
        curl.chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "COURSE_ARCHIVE": str(archive),
            "CURL_ARGS": str(self.base / "curl-args"),
            "COURSE_REF": "test-root-layout",
        }

    def fetch(self, cwd=None, success=True):
        result = subprocess.run(
            ["bash", str(self.script)], cwd=cwd or self.root,
            env=self.env, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_first_fetch_at_root(self):
        self.fetch()
        self.assertEqual((self.root / "factory/ITERATION").read_text(), "001 WIP\n")
        self.assertEqual((self.root / "tetris/spec.md").read_text(), "Seed 1\n")
        self.assertTrue((self.root / "factory/spec/features/1.feature").is_file())
        self.assertFalse((self.root / "spec").exists())
        self.assertFalse((self.root / "ITERATION").exists())
        self.assertIn("/test-root-layout", (self.base / "curl-args").read_text())

    def test_fetch_from_generated_target_uses_factory_root(self):
        target = self.root / "tetris/tetris1"
        target.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(target)], check=True)
        self.fetch(cwd=target)
        self.assertTrue((self.root / "factory/spec/README.md").is_file())
        self.assertFalse((target / "spec").exists())
        self.assertFalse((target / "ITERATION").exists())

    def test_fetch_from_outside_repository(self):
        self.fetch(cwd=self.base)
        self.assertTrue((self.root / "factory/ITERATION").is_file())
        self.assertFalse((self.base / "ITERATION").exists())

    def test_next_fetch_preserves_seed_and_outputs(self):
        self.fetch()
        seed = self.root / "tetris/spec.md"
        seed.write_text("Student's seed\n")
        notes = self.root / "factory/spec/notes.md"
        notes.write_text("Student's notes\n")
        plan = self.root / "tetris/tetris1/.factory/plan.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("All done\n")
        self.fetch()
        self.assertEqual((self.root / "factory/ITERATION").read_text(), "002 WIP\n")
        self.assertEqual(seed.read_text(), "Student's seed\n")
        self.assertEqual(notes.read_text(), "Student's notes\n")
        self.assertEqual(plan.read_text(), "All done\n")
        self.assertFalse((self.root / "factory/spec/features/1.feature").exists())
        self.assertTrue((self.root / "factory/spec/features/2.feature").is_file())

    def test_fourth_iteration_keeps_factory_in_place_and_end_is_reported(self):
        for number in range(1, 5):
            self.fetch()
            self.assertEqual((self.root / "factory/ITERATION").read_text(), f"{number:03d} WIP\n")
            self.assertTrue(self.script.is_file())
            self.assertTrue((self.root / "factory").is_dir())
            self.assertFalse((self.root / "tetris/.factory").exists())
        result = self.fetch(success=False)
        self.assertIn("nothing left to fetch after 004", result.stdout)
        self.assertEqual((self.root / "factory/ITERATION").read_text(), "004 WIP\n")


if __name__ == "__main__":
    unittest.main()
