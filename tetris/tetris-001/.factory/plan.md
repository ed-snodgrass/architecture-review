# Terminal Tetris implementation plan

Seed: `/workspaces/architecture-review/tetris/spec.md`

Build a playable terminal Tetris game launched with `npm start`. The entire display (board, borders, score, controls, and game-over status) must fit within 24 rows.

## Tasks

- [x] Set up a dependency-free Node.js project with an `npm start` entry point and a test command. Verified `npm test` (1 passing startup test) and `npm start`; entry point is a placeholder until the UI task.
- [ ] Implement and test the game engine: seven tetrominoes, movement, rotation, collision, gravity, locking, line clearing, scoring, spawning, and game over.
- [ ] Implement the interactive terminal UI: raw keyboard input, timed gravity, board rendering within 24 rows, score and controls, restart/quit, and terminal cleanup.
- [ ] Verify engine tests and terminal gameplay, including the 24-row display limit; document startup and controls.
