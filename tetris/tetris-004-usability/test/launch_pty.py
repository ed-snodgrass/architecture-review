"""Real launch verification (POSIX + Python stdlib): python3 test/launch_pty.py."""
import fcntl
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
FRAME = b"\x1b[H\x1b[2J"
CONTROLS_END = b"Q/^C quit"
RESTORE = b"\x1b[?25h\x1b[?1049l"


class Terminal:
    def __init__(self, columns):
        self.master, self.slave = pty.openpty()
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ,
                    struct.pack("HHHH", 24, columns, 0, 0))
        self.original_mode = termios.tcgetattr(self.slave)
        self.columns = columns
        self.pending = b""
        self.transcript = b""
        self.process = subprocess.Popen(
            ["npm", "start"], cwd=ROOT, stdin=self.slave,
            stdout=self.slave, stderr=self.slave, start_new_session=True,
        )

    def read_until(self, marker, timeout=5):
        deadline = time.monotonic() + timeout
        while marker not in self.pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.master], [], [], remaining)[0]:
                raise AssertionError(f"Timed out waiting for {marker!r}: {self.transcript!r}")
            data = os.read(self.master, 65536)
            if not data:
                raise AssertionError("Terminal closed unexpectedly")
            self.pending += data
            self.transcript += data
        end = self.pending.index(marker) + len(marker)
        result, self.pending = self.pending[:end], self.pending[end:]
        return result

    def frame(self):
        data = self.read_until(CONTROLS_END)
        assert FRAME in data, data
        text = data.split(FRAME)[-1].decode().replace("\r\n", "\n")
        rows = text.split("\n")
        # All glyphs used by the renderer are single terminal columns.
        assert len(rows) == 24, rows
        assert all(len(row) <= self.columns for row in rows), rows
        assert "\x1b" not in text, "Unexpected cursor movement inside a frame"
        assert rows[1] == rows[22] == "+--------------------+"
        assert all(row.startswith("|") and row.endswith("|") and len(row) == 22
                   for row in rows[2:22])
        assert rows[23] == "←→ move | ↑ rotate | ↓ soft | Space hard | Q/^C quit"
        return rows

    def key(self, data):
        os.write(self.master, data)
        return self.frame()

    def quit(self, key):
        os.write(self.master, key)
        self.read_until(RESTORE)
        assert self.process.wait(timeout=5) == 0
        assert termios.tcgetattr(self.slave) == self.original_mode
        assert self.transcript.count(RESTORE) == 1
        assert self.transcript.count(b"\x1b[?1049h\x1b[?25l") == 1

    def close(self):
        # Kill the whole npm/node group on assertion failures, not only npm.
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.process.wait(timeout=5)
        os.close(self.master)
        os.close(self.slave)


class LaunchTests(unittest.TestCase):
    def test_interactive_launch_gameplay_and_game_over(self):
        for columns, quit_key in [(80, b"q"), (52, b"\x03")]:
            with self.subTest(columns=columns):
                terminal = Terminal(columns)
                try:
                    initial = terminal.frame()
                    self.assertTrue(initial[0].startswith("TETRIS | Score 0"))
                    self.assertFalse(termios.tcgetattr(terminal.slave)[3] & termios.ICANON)
                    self.assertFalse(termios.tcgetattr(terminal.slave)[3] & termios.ECHO)
                    left = terminal.key(b"\x1b[D")
                    self.assertNotEqual(left[2:22], initial[2:22])
                    right = terminal.key(b"\x1b[C")
                    self.assertEqual(right[2:22], initial[2:22])
                    terminal.key(b"\x1b[A")  # Rotation (O may remain unchanged).
                    soft = terminal.key(b"\x1b[B")
                    self.assertIn("Score 1 |", soft[0])
                    gravity = terminal.frame()  # Real timer, without input.
                    self.assertNotEqual(gravity[2:22], soft[2:22])
                    self.assertEqual(gravity[0], soft[0])
                    # Repeated center drops cannot clear a full-width line;
                    # they inevitably block the spawn, regardless of the bag.
                    for _ in range(40):
                        dropped = terminal.key(b" ")
                        if dropped[0].startswith("GAME OVER"):
                            break
                    else:
                        self.fail("Center stack did not reach game over")
                    self.assertIn("Lines 0", dropped[0])
                    self.assertGreater(sum(row.count("[]") for row in dropped[2:22]), 4)
                    os.write(terminal.master, b"\x1b[D\x1b[A ")
                    self.assertFalse(select.select([terminal.master], [], [], 0.2)[0],
                                     "Game over should stop input rendering and gravity")
                    terminal.quit(quit_key)
                finally:
                    terminal.close()

    def test_non_tty_npm_start_exits_cleanly(self):
        result = subprocess.run(["npm", "start"], cwd=ROOT, input="",
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertIn("requires an interactive terminal", result.stderr)
        self.assertNotIn("\x1b", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
