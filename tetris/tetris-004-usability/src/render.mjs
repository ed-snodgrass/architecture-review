import { cells } from './game.mjs';

export function render(game) {
  const board = game.board.map(row => [...row]);
  if (game.active) {
    for (const { x, y, type } of cells(game.active)) board[y][x] = type;
  }
  return [
    `${game.gameOver ? 'GAME OVER' : 'TETRIS'} | Score ${game.score} | Lines ${game.lines} | Level ${game.level}`,
    '+--------------------+',
    ...board.map(row => `|${row.map(cell => cell ? '[]' : '  ').join('')}|`),
    '+--------------------+',
    'Arrows: move/rotate/drop | Space: hard drop | Q: quit',
  ].join('\n');
}
