"""Smoke-test the real npm entry point using only Python's standard library."""
import errno
import fcntl
import os
import pty
import select
import signal
import struct
import subprocess
import termios
import time


class Terminal:
    def __init__(self):
        self.master, self.slave = pty.openpty()
        self.resize(64, 24)
        self.original = termios.tcgetattr(self.slave)
        self.output = b''
        self.process = subprocess.Popen(
            ['npm', 'start'], stdin=self.slave, stdout=self.slave,
            stderr=self.slave, start_new_session=True)

    def resize(self, columns, rows):
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ,
                    struct.pack('HHHH', rows, columns, 0, 0))
        if hasattr(self, 'process'):
            os.killpg(self.process.pid, signal.SIGWINCH)

    def read(self, timeout):
        if select.select([self.master], [], [], timeout)[0]:
            try:
                self.output += os.read(self.master, 65536)
            except OSError as error:
                if error.errno != errno.EIO:
                    raise

    def wait(self, predicate, description, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            self.read(0.05)
        raise AssertionError(f'Timed out: {description}; output={self.output[-2000:]!r}')

    def frames(self):
        frames = []
        for part in self.output.split(b'\x1b[H\x1b[2J')[1:]:
            text = part.decode().replace('\r', '').split('\x1b')[0]
            rows = text.split('\n')
            if len(rows) == 24 and rows[-1].endswith('Q: quit'):
                assert all(len(row) < 64 for row in rows)
                frames.append(rows)
        return frames

    def key(self, key):
        count = len(self.frames())
        os.write(self.master, key)
        self.wait(lambda: len(self.frames()) > count, f'frame after {key!r}')
        return self.frames()[-1]

    def restored(self):
        self.wait(lambda: self.process.poll() is not None, 'process exit')
        self.read(0.1)
        assert termios.tcgetattr(self.slave) == self.original, 'terminal attributes not restored'
        assert b'\x1b[?25h' in self.output, 'cursor not restored'
        assert b'\x1b[?1049l' in self.output, 'alternate screen not restored'

    def close(self):
        # Kill any remaining npm/node process even after a failed assertion.
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.process.wait(timeout=5)
        os.close(self.master)
        os.close(self.slave)


terminal = Terminal()
try:
    terminal.wait(lambda: bool(terminal.frames()), 'startup')
    assert b'\x1b[?1049h\x1b[?25l' in terminal.output
    assert termios.tcgetattr(terminal.slave) != terminal.original
    initial = terminal.frames()[-1]
    left = terminal.key(b'\x1b[D')
    assert left[1:21] != initial[1:21], 'left movement not visible'
    right = terminal.key(b'\x1b[C')
    assert right[1:21] == initial[1:21], 'right movement did not undo left'
    terminal.key(b'\x1b[A')  # O pieces may rotate without a visible change.
    before = terminal.frames()[-1]
    terminal.wait(lambda: terminal.frames()[-1][1:21] != before[1:21], 'timed gravity')
    dropped = terminal.key(b'\x1b[B')
    assert 'Score: 1 ' in dropped[22], 'soft drop did not score'
    hard = terminal.key(b' ')
    assert any('[]' in row for row in hard[18:21]), 'hard drop did not lock at floor'
    for _ in range(40):
        if 'GAME OVER!' in terminal.frames()[-1][22]:
            break
        terminal.key(b' ')
    assert 'GAME OVER!' in terminal.frames()[-1][22]
    restarted = terminal.key(b'r')
    assert 'GAME OVER!' not in restarted[22]
    assert 'Score: 0  Lines: 0' in restarted[22]
    assert all('[]' not in row for row in restarted[5:21])
    terminal.resize(30, 10)
    terminal.wait(lambda: b'Resize to at least' in terminal.output, 'small terminal warning')
    count = len(terminal.frames())
    terminal.resize(64, 24)
    terminal.wait(lambda: len(terminal.frames()) > count, 'resize recovery')
    os.write(terminal.master, b'q')
    terminal.restored()
    assert terminal.process.returncode == 0
finally:
    terminal.close()

terminal = Terminal()
try:
    terminal.wait(lambda: bool(terminal.frames()), 'signal test startup')
    os.killpg(terminal.process.pid, signal.SIGTERM)
    terminal.restored()
finally:
    terminal.close()

print('PTY startup, movement, gravity, drops, game over/restart, resize, quit and SIGTERM passed')
