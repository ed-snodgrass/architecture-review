# Gameplay and terminal verification

Run from `tetris/tetris-004-usability/`:

```sh
npm test
python3 test/launch_pty.py
```

Results: all 37 Node tests and both Python launch tests passed. The Python
smoke tests require POSIX pseudo-terminals and Python 3; the game itself has
no Python dependency.

Coverage:

- Deterministic mechanics: all seven pieces, rotations and kicks, collisions,
  gravity, soft/hard drops, locking, one-to-four simultaneous line clears,
  scoring, level acceleration, and frozen gameplay after blocked spawn.
- Renderer: normal/game-over states and maximum counters fit exactly 24 rows
  and at most 52 columns, with borders, score, and controls inside that budget.
- Input/lifecycle: split escape sequences, modified arrows, resize pause/resume,
  quit, signals, stream errors, and idempotent cleanup.
- Actual `npm start` processes attached to 80x24 and 52x24 pseudo-terminals:
  immediate arrow input, rotation, soft drop, timed gravity, repeated hard drops
  through game over, and Q/Ctrl-C exit. Each observed frame has 24 rows, fits
  the terminal width, and ends without a newline or embedded cursor controls.
  Game-over rendering retains controls and does not append rows. Further
  gameplay input produces no output after game over.
- Exit restores the complete original terminal attributes and emits cursor
  and alternate-screen restoration exactly once.
- Non-TTY `npm start` exits with status 1 and a clear diagnostic, without ANSI
  output or hanging.

These are automated unit/integration and real-process PTY checks, not a manual
visual play session in a terminal emulator. The external plan was not changed.
