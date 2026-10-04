# Terminal Tetris

Requires Node.js 18 or newer. No dependencies or installation step needed.

```sh
npm start
```

Run in an interactive terminal at least 48 columns wide and 24 rows tall.
The complete game display uses 22 rows, including the board, score, controls,
and game-over message. Play pauses automatically when the terminal is too small.

## Controls

| Key | Action |
| --- | --- |
| Left / Right | Move |
| Up | Rotate clockwise |
| Down | Soft drop |
| Space | Hard drop |
| P | Pause / resume |
| R | Restart (also after game over) |
| Q / Ctrl-C | Quit |

Completed rows disappear and award points. Gravity speeds up every ten lines.
The game ends when a new piece cannot spawn. Quitting restores the cursor,
normal keyboard mode, and the previous terminal screen.

## Verification

```sh
npm test
```

Tests cover the engine, controls, gravity, cleanup, and the display size in
playing, paused, and game-over states. Startup and keyboard gameplay were also
verified through a pseudo-terminal sized to 48 by 24.
