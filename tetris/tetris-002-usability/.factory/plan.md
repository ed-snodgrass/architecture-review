# Terminal Tetris implementation plan

Seed: `/workspaces/architecture-review/tetris/spec.md`

Build a playable terminal Tetris game launched with `npm start`. All display states, including controls and game over, must fit within 24 terminal rows.

- [ ] Set up the Node.js project and implement the testable Tetris game engine: board, seven tetrominoes, movement, rotation, collision, gravity, locking, line clearing, scoring, and game over.
- [ ] Implement the terminal interface and `npm start`: keyboard controls, timed gravity, board and score rendering within 24 rows, game-over display, restart, and clean terminal restoration on exit.
- [ ] Add automated engine and display tests, run them, and document startup, controls, terminal requirements, and display-height compliance.
