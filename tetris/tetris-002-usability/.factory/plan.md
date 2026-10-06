# Terminal Tetris implementation plan

Seed: `/workspaces/architecture-review/tetris/spec.md`

Build a playable terminal Tetris game launched with `npm start`. All display states, including controls and game over, must fit within 24 terminal rows.

- [x] Set up the Node.js project and implement the testable Tetris game engine: board, seven tetrominoes, movement, rotation, collision, gravity, locking, line clearing, scoring, and game over. Implemented in `package.json` and `src/engine.js`; inline Node assertion smoke checks passed.
- [x] Implement the terminal interface and `npm start`: keyboard controls, timed gravity, board and score rendering within 24 rows, game-over display, restart, and clean terminal restoration on exit.
  - [x] Validator finding (`src/display.js`): falling and settled blocks both render as `[]`, making the controllable piece difficult to distinguish when it touches the stack. Render active blocks as `<>`, retain `[]` for settled blocks, and add a side-panel legend. Added regression tests in `test/display.test.js` for touching same-type blocks, locking, game over, non-mutating rendering, and 24-row/48-column bounds; `npm test` passed (2 tests).
- [x] Add automated engine and display tests, run them, and document startup, controls, terminal requirements, and display-height compliance. Added `test/engine.test.js`, expanded `test/display.test.js`, and wrote `README.md`; `npm test` passed all 17 tests.
