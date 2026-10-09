# Target project inspection

Target: `/workspaces/architecture-review/tetris/tetris-004`

## Existing structure

- `.assembly-lines/careful.dot` and `.assembly-lines/quick.dot` define orchestration workflows.
- `.assembly-lines/.machines/` contains planner, doer, and validator configuration.
- No game source, README, tests, `package.json`, dependency lockfile, or installed dependencies exist in this target.
- Sibling Tetris targets are separate projects and are not dependencies of this target.

## Runtime and dependencies

- Available Node.js: `v24.21.0`.
- Available npm: `11.19.0`.
- No project dependencies are declared; there is no existing start or test script.
- Node.js built-ins are sufficient for an initial implementation: terminal output via `process.stdout`, keyboard input via `process.stdin` and `node:readline`, timers for gravity, and `node:test` for logic tests. External packages are optional, not currently required.

## Constraints for subsequent tasks

- Create a Node.js project whose `npm start` launches terminal Tetris.
- Keep the entire display at or below 24 terminal rows, including borders, score, controls, and game-over messages.
- Separate gameplay logic from terminal input/rendering so rules can be tested independently.
- Restore terminal input settings and clean up timers/listeners when quitting or ending the game.

This inspection does not configure the project or implement gameplay. The plan's checkboxes remain unchanged.
