import readline from 'node:readline';
import { Game } from './engine.js';

export const MIN_COLUMNS = 48;
export const MIN_ROWS = 24;

// Twenty board rows plus two borders; all status text lives beside the board.
export function render(game, { paused = false } = {}) {
  const info = [
    'Terminal Tetris',
    `Score: ${game.score}`,
    `Lines: ${game.lines}`,
    `Level: ${game.level}`,
    '',
    game.gameOver ? 'GAME OVER' : paused ? 'PAUSED' : 'Playing',
    '',
    'Left/Right: move',
    'Up: rotate',
    'Down: soft drop',
    'Space: hard drop',
    'P: pause',
    'R: restart',
    'Q / Ctrl-C: quit',
  ];
  const board = game.frame().map(row => `|${row.map(cell => cell ? '[]' : '  ').join('')}|`);
  const border = `+${'-'.repeat(20)}+`;
  return [border, ...board, border]
    .map((row, i) => `${row}  ${info[i] ?? ''}`.trimEnd()).join('\n');
}

export function startTerminal({ input = process.stdin, output = process.stdout,
  game = new Game(), signals = process } = {}) {
  if (!input.isTTY || !output.isTTY) {
    output.write('Terminal Tetris requires an interactive terminal. Run npm start in a terminal.\n');
    return () => {};
  }

  let timer;
  let paused = false;
  let stopped = false;
  const wasRaw = Boolean(input.isRaw);
  const fits = () => (output.columns ?? MIN_COLUMNS) >= MIN_COLUMNS &&
    (output.rows ?? MIN_ROWS) >= MIN_ROWS;
  const draw = () => {
    if (stopped) return;
    const frame = fits() ? render(game, { paused }) :
      `Resize terminal to at least ${MIN_COLUMNS}x${MIN_ROWS}.`;
    // CRLF avoids depending on the terminal's raw-mode newline translation.
    output.write(`\x1b[H\x1b[2J${frame.replaceAll('\n', '\r\n')}`);
  };
  const schedule = () => {
    clearTimeout(timer);
    if (stopped || paused || game.gameOver || !fits()) return;
    timer = setTimeout(() => {
      game.tick();
      draw();
      schedule();
    }, game.gravityMs);
  };
  const cleanup = () => {
    if (stopped) return;
    stopped = true;
    clearTimeout(timer);
    input.removeListener('keypress', onKey);
    output.removeListener('resize', onResize);
    signals.removeListener('SIGINT', cleanup);
    signals.removeListener('SIGTERM', cleanup);
    signals.removeListener('exit', cleanup);
    input.setRawMode(wasRaw);
    input.pause();
    output.write('\x1b[?25h\x1b[?1049l');
  };
  const onKey = (text, key = {}) => {
    const name = key.name ?? text;
    if (name === 'q' || (key.ctrl && name === 'c')) return cleanup();
    if (name === 'r') {
      game.reset();
      paused = false;
      schedule();
    } else if (name === 'p') {
      paused = !paused;
      schedule();
    } else if (!paused && !game.gameOver && fits()) {
      if (name === 'left') game.move(-1);
      else if (name === 'right') game.move(1);
      else if (name === 'up') game.rotate();
      else if (name === 'down') game.tick({ softDrop: true });
      else if (name === 'space' || text === ' ') game.hardDrop();
      if (game.gameOver) clearTimeout(timer);
    }
    draw();
  };
  const onResize = () => { draw(); schedule(); };

  readline.emitKeypressEvents(input);
  input.on('keypress', onKey);
  output.on('resize', onResize);
  signals.on('SIGINT', cleanup);
  signals.on('SIGTERM', cleanup);
  signals.on('exit', cleanup);
  input.setRawMode(true);
  input.resume();
  output.write('\x1b[?1049h\x1b[?25l');
  draw();
  schedule();
  return cleanup;
}
