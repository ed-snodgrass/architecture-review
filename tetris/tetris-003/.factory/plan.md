# Terminal Tetris plan

Seed: `/workspaces/architecture-review/tetris/spec.md`

## Tasks

- [x] Create a Node.js project with an `npm start` entry point.
- [x] Implement the Tetris board, seven tetrominoes, spawning, movement, rotation, collision detection, gravity, and piece locking.
- [x] Implement completed-line clearing, scoring, and game-over detection.
- [x] Render the complete display within 24 terminal rows: use a 20-row board, two border rows, and two status/control rows; show game-over text in the status area.
- [x] Add terminal keyboard input for movement, rotation, dropping, and quitting, with safe terminal cleanup on exit.
  - [x] Address validator finding in `src/terminal.js:65-67`: move the drop-and-lock game rule into `Game.hardDrop()` and have the space-key handler only call that action.
- [x] Add automated tests for core game rules and the 24-row display limit.
- [ ] Run tests and manually verify `npm start`, gameplay, controls, and game-over display.

## Acceptance criteria

- The game runs in the terminal via `npm start`.
- The board, score, controls, borders, and game-over messages together occupy no more than 24 terminal rows.
- Gameplay supports falling pieces, legal movement and rotation, locking, line clearing, and game over.
