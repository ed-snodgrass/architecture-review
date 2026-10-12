# Target project inspection

## Current state

- The target directory contains only `.assembly-lines/` workflow configuration. There is no existing game implementation.
- No `package.json`, lockfile, application entry point, dependencies, or test files are present. There are therefore no applicable tests or start commands to run yet.
- The environment provides Node.js v24.21.0 and npm 11.19.0.
- The seed requires a terminal Tetris game launched with `npm start`, with the entire display constrained to 24 rows.

## Implementation and test setup for subsequent tasks

Use plain JavaScript with Node.js ES modules; no compilation or external dependencies are needed. In the next configuration task, create `package.json` with `"type": "module"` and a start script targeting `src/main.js`.

Keep game mechanics independent of terminal I/O, with separate modules for game state, rendering, and the terminal entry point. Node's built-in `readline` keypress handling, stdin raw mode, and ANSI escape sequences can provide controls and rendering. The entry point should restore terminal state on exit.

When the plan reaches testing, use the built-in `node:test` runner and `node:assert/strict`, exposed through an `npm test` script running `node --test`. Pure mechanics and a renderer returning display text will support deterministic checks without an interactive terminal. Reserve rendering space for the 20-row board plus borders and status/control lines, including game-over text, within the 24-row limit.

This inspection does not configure the project, implement the game, create or modify tests, or change task completion markers.
