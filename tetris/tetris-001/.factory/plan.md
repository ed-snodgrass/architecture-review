# Terminal Tetris implementation plan

Seed: `/workspaces/architecture-review/tetris/spec.md`

Build a playable terminal Tetris game launched with `npm start`. The entire display (board, borders, score, controls, and game-over status) must fit within 24 rows.

## Tasks

- [x] Set up a dependency-free Node.js project with an `npm start` entry point and a test command. Verified `npm test` (1 passing startup test) and `npm start`; entry point is a placeholder until the UI task.
- [x] Implement and test the game engine: seven tetrominoes, movement, rotation, collision, gravity, locking, line clearing, scoring, spawning, and game over. Added `src/engine.js` and `test/engine.test.js`; verified `npm test` (14 passing tests).
- [x] Implement the interactive terminal UI: raw keyboard input, timed gravity, board rendering within 24 rows, score and controls, restart/quit, and terminal cleanup. Added `src/terminal.js`, connected `src/index.js`, and added UI tests. Display uses 22 rows, pauses on undersized terminals, and restores raw mode/cursor on quit or signals. Verified `npm test` (18 passing tests).
- [x] Verify engine tests and terminal gameplay, including the 24-row display limit; document startup and controls. Verified `npm test` (18 passing tests) and `npm start` in a 48x24 pseudo-terminal: movement/rotation/drop, pause, restart, game over, quit, and terminal restoration. Frames remain 22 rows and at most 48 columns. Added `README.md` with requirements, startup, controls, and verification instructions.
