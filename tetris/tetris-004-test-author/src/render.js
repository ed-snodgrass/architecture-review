import { getActiveCells } from './game.js';

export function terminalFits({ columns = 80, rows = 24 } = {}) {
  return columns >= 40 && rows >= 24;
}

// One header, two borders, twenty board rows, and one controls row: 24 rows.
export function render(game, { columns = 80, rows = 24 } = {}) {
  if (!terminalFits({ columns, rows })) {
    return ['Tetris needs 40 columns x 24 rows.', 'Resize terminal; Q or Ctrl+C: exit.']
      .slice(0, Math.max(0, rows))
      .map(line => line.slice(0, Math.max(0, columns)))
      .join('\n');
  }
  const cells = game.board.map(row => [...row]);
  // A blocked spawn is not a falling piece; retain the settled board at game over.
  if (!game.gameOver) {
    for (const { x, y } of getActiveCells(game)) {
      if (cells[y] && x >= 0 && x < cells[y].length) cells[y][x] = game.active.type;
    }
  }
  const border = '+--------------------+';
  let header = `Tetris | Score: ${game.score}${game.gameOver ? ' | GAME OVER' : ''}`;
  if (header.length > columns) {
    // Keep the end state visible even for unusually large scores.
    header = `${game.gameOver ? 'GAME OVER | ' : ''}Score: ${game.score}`.slice(0, columns);
  }
  return [
    header,
    border,
    ...cells.map(row => `|${row.map(cell => cell === null ? '  ' : '[]').join('')}|`),
    border,
    'Arrows: move; Up: rotate; Q/Ctrl+C: exit',
  ].join('\n');
}
