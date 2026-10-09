# Gameplay verification

Verified the final pending plan task without changing its checkbox.

- `npm test`: all 18 tests passed.
- Launched the actual `npm start` command in an 80-column, 24-row pseudo-terminal.
- Observed gravity advance the falling piece.
- Sent left, right, up (rotation), down, and space (hard drop) keyboard sequences; each produced a refreshed display.
- Repeated hard drops until the game-over status appeared; verified gravity stopped afterward.
- All 19 captured display frames contained exactly 24 rows, including borders, score, controls, and game-over text.
- Pressed Q after game over: process exited successfully and restored terminal settings, cursor visibility, wrapping, and the original screen.

The terminal interaction was exercised through a PTY, not a human-operated terminal window. No gameplay source changes were necessary.
