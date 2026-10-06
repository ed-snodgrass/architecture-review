# Terminal Tetris implementation plan

Seed: `/workspaces/architecture-review/tetris/spec.md`

Build a playable terminal Tetris game launched with `npm start`. The complete display, including the board, score, controls, borders, and game-over messages, must fit within 24 terminal rows.

## Tasks

- [x] Set up the Node.js project and implement a testable Tetris engine: seven tetrominoes, spawning, movement, rotation, collision detection, gravity, locking, line clearing, scoring, and game over. Added `package.json` and `src/engine.js`; Node assertion smoke checks passed.
- [x] Implement the terminal interface and `npm start`: keyboard controls, timed gravity, rendering within 24 rows, restart/quit controls, and safe terminal cleanup.
- [x] Add and run automated engine and display tests, smoke-test startup and exit, and document installation and controls. Added `test/engine.test.js`, `test/display.test.js`, and `README.md`; all 10 tests pass with `npm test`. A 24×80 pseudo-terminal smoke test of `npm start` passed rendering, movement/rotation/drop, restart, quit, cursor restoration, and input-mode restoration.

## Acceptance checks

- `npm start` launches a playable terminal game.
- Pieces move, rotate, fall, lock, and clear completed lines; score updates and blocked spawning ends the game.
- Every screen state fits within 24 rows, including game over and control instructions.
- Quitting restores terminal input and cursor state.
- Automated tests pass.
