# Terminal Tetris

## Run

Use Node.js 18 or newer in an interactive terminal:

```sh
npm start
```

No dependencies or installation step are required. Redirected input/output is not supported. The terminal must be at least **48 columns by 24 rows**. If resized smaller, play pauses and a resize prompt appears; enlarging it resumes play.

## Controls

| Key | Action |
| --- | --- |
| Left / A | Move left |
| Right / D | Move right |
| Down / S | Soft drop |
| Up / W / X | Rotate clockwise |
| Z | Rotate counterclockwise |
| Space | Hard drop |
| R | Restart (also after game over) |
| Q / Ctrl-C | Quit |

Falling blocks are `<>`; settled blocks are `[]`. Complete horizontal rows to clear them. Each seven-piece bag contains every tetromino once. Clearing one to four rows awards 100/300/500/800 points times the current level. Soft drops earn one point per cell, hard drops two. Every ten cleared rows increases the level and speeds gravity. A blocked spawn ends the game.

## Display size

The full frame is exactly **24 rows**: title, top border, 20 board rows, bottom border, and status/game-over message. Score, next-piece name, legend, and all controls sit beside the board rather than adding rows. The renderer reserves the final terminal column and writes no trailing newline to avoid wrapping or scrolling at the minimum size. The game uses the alternate screen and restores the cursor and input mode on exit.

## Tests

```sh
npm test
```

The built-in Node test runner checks piece bags, movement/collision, rotation and kicks, gravity/locking, drops, line clearing/scoring, levels, game over/reset, immutable display snapshots, block glyphs, controls, and the 24-row/48-column display bounds. No external test packages are needed.
