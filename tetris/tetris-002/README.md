# Terminal Tetris

Requires Node.js 18 or newer and an interactive terminal at least 56 columns
wide and 22 rows tall. There are no dependencies to install.

```sh
npm start
```

The 10×20 board, score, next-piece name, controls and game-over message share
one 22-row screen, fitting inside a 24-row terminal. Smaller terminals show a
resize prompt and pause play until resized.

## Controls

| Key | Action |
| --- | --- |
| Left / Right or A / D | Move |
| Up or W | Rotate clockwise |
| Z | Rotate counterclockwise |
| Down or S | Soft drop |
| Space | Hard drop |
| R | Restart (including after game over) |
| Q / Esc / Ctrl-C | Quit |

Completed lines earn 100/300/500/800 points for clearing 1/2/3/4 lines,
multiplied by the current level. Soft drops earn one point per row; hard drops
earn two. Every ten cleared lines increases the level and gravity speed.
Blocked spawning ends the game. Quitting restores the cursor, previous screen
and terminal input mode.

## Tests

```sh
npm test
```

Tests cover the engine, scoring, game over/restart, display dimensions and
non-interactive startup. For a manual terminal smoke test, run `npm start`,
move/rotate/drop a piece, restart with R, then quit with Q. The original screen
and normal echoed input should return.
