import { BOARD_HEIGHT, BOARD_WIDTH } from './game.js';

// A frame is exactly 24 rows: two borders, 20 board rows, and two status rows.
// No trailing newline: printing one at the bottom of a 24-row terminal scrolls.
export function renderGame(game) {
  const cells = game.board.map(row => [...row]);
  if (game.active && !game.gameOver) {
    const { matrix, x, y, type } = game.active;
    for (let row = 0; row < matrix.length; row++) {
      for (let col = 0; col < matrix[row].length; col++) {
        const boardX = x + col;
        const boardY = y + row;
        if (matrix[row][col] && boardX >= 0 && boardX < BOARD_WIDTH &&
            boardY >= 0 && boardY < BOARD_HEIGHT) {
          cells[boardY][boardX] = type;
        }
      }
    }
  }

  const border = `+${'-'.repeat(BOARD_WIDTH * 2)}+`;
  return [
    border,
    ...cells.map(row => `|${row.map(cell => cell === null ? '  ' : '[]').join('')}|`),
    border,
    `${game.gameOver ? 'GAME OVER | ' : ''}Score: ${game.score} | Lines: ${game.lines}`,
    'Arrows: move/rotate | Space: drop | Q: quit',
  ].join('\n');
}
