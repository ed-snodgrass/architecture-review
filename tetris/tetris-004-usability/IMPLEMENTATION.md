# Implementation and test approach

## Inspection

The working project (`tetris/tetris-004-usability/`) contains only
`.assembly-lines/` orchestration definitions and machine configuration. There
is no game source, package manifest, launch script, or test suite to extend.
Neighboring Tetris projects are separate runs, not this project's source.
Node.js v24.21.0 and npm 11.19.0 are available.

The seed requires a terminal Tetris game launched with `npm start`, with its
entire display fitting within 24 terminal rows. The run plan additionally
calls for playable mechanics, visible controls, reliable input, and terminal
restoration. This document records the approach for the first task only; the
plan's checkboxes and completion flag remain unchanged.

## Implementation approach

Use dependency-free JavaScript ES modules and Node's built-in APIs:

- `package.json`: `start` runs `node src/main.js`; `test` runs `node --test`.
- `src/game.js`: terminal-independent game state and transitions. Represent a
  10-column, 20-row board and seven tetrominoes; inject piece selection for
  deterministic tests. Implement movement, clockwise rotation (with a small,
  documented wall-kick policy), gravity, hard drop, collision, locking,
  simultaneous line removal, scoring, and spawn-collision game over. Invalid
  moves must leave the state unchanged, and pieces must not lock outside the
  board. Freeze gameplay after game over.
- `src/render.js`: pure rendering to an array of lines, overlaying the active
  piece without modifying the board. Reserve exactly 24 rows: one status row,
  one top border, twenty board rows, one bottom border, and one controls row.
  Show game-over text in the status row rather than appending output. Use
  compact cell glyphs and keep visible width within 80 columns.
- `src/main.js`: interactive terminal adapter using `node:readline` keypress
  events, raw input, and a gravity timer. Provide arrows for movement/rotation,
  down for soft drop, space for hard drop, and Q/Ctrl-C to quit. Draw using
  cursor positioning rather than accumulating frames. Avoid a trailing newline
  on the last display row so a 24-row terminal does not scroll. Require a TTY
  and sufficient terminal dimensions; report unsupported environments clearly.
  Restore cursor visibility, raw mode, timers, and the original screen on quit,
  signals, and errors through a shared idempotent cleanup path. Handle resize
  without drawing a clipped game (pause while the terminal is too small).

## Verification approach

Use Node's built-in test runner; no package installation is necessary.

1. Unit-test deterministic game transitions: every piece's spawn and rotation,
   movement at both walls, floor and settled-block collisions, unsuccessful
   rotations, gravity and drop locking, clearing one or multiple lines,
   corresponding score changes, and spawn-blocked game over.
2. Unit-test rendering for initial, active, line-cleared, and game-over states.
   Assert at most 24 lines and at most 80 visible columns after stripping ANSI
   escapes. Confirm score, controls, borders, and game-over text are present
   within that budget and rendering does not mutate game state.
3. Test input-to-action mapping and lifecycle cleanup with injected streams and
   timers, including repeated cleanup, Ctrl-C, quit, signals, errors, and resize.
4. Run `npm test`, then smoke-test `npm start` in a pseudo-terminal sized to
   80x24. Exercise movement, rotation, soft/hard drop, and quit; verify input is
   processed immediately and cursor/raw mode are restored. Inspect frames for
   scrolling and appended lines, including a deterministic game-over fixture.
5. Manually play in a real terminal to check responsiveness and readability;
   separately verify that non-TTY launch fails cleanly rather than hanging.

These checks are planned, not yet executed: no implementation exists in this
project at the time of inspection.
