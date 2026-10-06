// Twenty board rows plus two borders; all status and help live beside the board.
export const SCREEN_ROWS = 22;
export const SCREEN_COLUMNS = 56;

export function renderScreen(game) {
  const sidebar = [
    'TETRIS',
    `Score: ${game.score}`,
    `Lines: ${game.lines}`,
    `Level: ${game.level}`,
    `Next: ${game.next}`,
    '',
    'Left/Right or A/D: move',
    'Up or W: rotate',
    'Z: rotate counterclockwise',
    'Down or S: soft drop',
    'Space: hard drop',
    'R: restart',
    'Q / Esc / Ctrl-C: quit',
    '',
    game.gameOver ? 'GAME OVER' : 'Playing',
    game.gameOver ? 'Press R to play again' : '',
  ];
  const border = `+${'-'.repeat(game.width * 2)}+`;
  const board = [border, ...game.visibleBoard().map(row =>
    `|${row.map(cell => cell ? '[]' : '  ').join('')}|`), border];
  return board.map((row, index) => `${row}  ${(sidebar[index] ?? '').slice(0, 32)}`.trimEnd());
}
