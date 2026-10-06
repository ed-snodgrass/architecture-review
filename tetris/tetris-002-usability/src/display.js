export const MIN_COLUMNS = 48;
export const DISPLAY_ROWS = 24;

// Twenty board rows plus borders, title, and status: exactly 24 rows.
// Controls live beside the board, including when the game is over.
export function renderFrame(game) {
  const help = [
    `Score: ${game.score}`,
    `Lines: ${game.lines}`,
    `Level: ${game.level}`,
    `Next: ${game.next}`,
    '<> falling; [] settled',
    'Left / A: left',
    'Right / D: right',
    'Down / S: soft drop',
    'Up / W / X: rotate',
    'Z: rotate back',
    'Space: hard drop',
    '',
    'R: restart',
    'Q / Ctrl-C: quit',
  ];
  const board = game.getDisplayBoard();
  return [
    'TETRIS',
    `+${'-'.repeat(20)}+`,
    ...board.map((row, y) =>
      `|${row.map((cell, x) => {
        if (!cell) return '  ';
        const active = game.active;
        const isActive = active?.matrix[y - active.y]?.[x - active.x];
        return isActive ? '<>' : '[]';
      }).join('')}|  ${help[y] ?? ''}`),
    `+${'-'.repeat(20)}+`,
    game.gameOver ? 'GAME OVER - R to restart, Q to quit' : 'Stack blocks; complete rows to score.',
  ].join('\n');
}
