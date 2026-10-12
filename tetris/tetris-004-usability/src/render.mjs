import { cells } from './game.mjs';

export const DISPLAY_ROWS = 24;
export const DISPLAY_COLUMNS = 52;

// Bound counter widths so even long games cannot wrap the status row.
const counter = (value, maximum) => value > maximum ? `${maximum}+` : String(value);

export function render(game) {
  const board = game.board.map(row => [...row]);
  if (game.active) {
    for (const { x, y, type } of cells(game.active)) board[y][x] = type;
  }
  return [
    `${game.gameOver ? 'GAME OVER' : 'TETRIS'} | Score ${counter(game.score, 999999)} | Lines ${counter(game.lines, 9999)} | Level ${counter(game.level, 999)}`,
    '+--------------------+',
    ...board.map(row => `|${row.map(cell => cell ? '[]' : '  ').join('')}|`),
    '+--------------------+',
    '←→ move | ↑ rotate | ↓ soft | Space hard | Q/^C quit',
  ].join('\n');
}
