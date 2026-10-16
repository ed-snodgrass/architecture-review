# Terminal Tetris

A terminal Tetris game with a 10-column, 20-row board. Requires Node.js 20 or newer and an interactive terminal at least **64 columns × 24 rows**.

## Run

From this directory:

```sh
npm install
npm start
```

There are no external dependencies. The game uses an alternate screen; quitting restores the cursor and terminal input mode. Noninteractive execution exits with an explanatory error. If the terminal is too small, play pauses until it is resized to at least 64×24.

## Controls

| Key | Action |
| --- | --- |
| Left / Right | Move |
| Up | Rotate clockwise |
| Down | Soft drop |
| Space | Hard drop and lock |
| R | Restart after game over |
| Q / Ctrl+C | Quit |

Completed rows award points; soft and hard drops also score points. Gravity accelerates every ten cleared lines. Rotation has no wall kicks.

The complete playing and game-over displays occupy 24 rows: 20 board rows, two borders, one status row, and one controls row. Game-over and restart instructions share the status row rather than adding output.

## Tests

```sh
npm test
```

The suite includes:
- 15 engine tests covering piece supply, boundaries, collisions, movement, gravity, locking, line clearing, scoring, rotation, and game over/restart.
- Rendering checks for playing and game-over states at 64, 80, and 120 columns: exactly 24 rows, no wrapping, visible board/status/controls, and no state mutation.
- Noninteractive `npm start` rejection with a bounded diagnostic and no terminal escape sequences.
- A real `npm start` pseudo-terminal smoke test covering startup, left/right movement, rotation input, timed gravity, soft/hard drops, game over/restart, resize and recovery, normal quit, and SIGTERM. It checks terminal attributes, cursor, and alternate-screen restoration.

The PTY test requires **Python 3** (`python3` on PATH) and a POSIX system; it is skipped on Windows. The game itself only needs Node.js. To run checks separately:

```sh
node --test test/engine.test.js
node --test test/terminal.test.js
python3 test/terminal-pty.py
```

For a manual terminal smoke check, start with `npm start`, try movement and both drops, repeatedly hard-drop to reach game over, press R to restart, then Q to quit. Verify that the entire display fits at 64×24 and that normal typing and the cursor are restored after quitting. Resize below the minimum and back to verify paused play and recovery.
