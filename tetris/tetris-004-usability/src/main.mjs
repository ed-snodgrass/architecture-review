import readline from 'node:readline';
import { Game } from './game.mjs';
import { render } from './render.mjs';

const input = process.stdin;
const output = process.stdout;
if (!input.isTTY || !output.isTTY) {
  console.error('Tetris requires an interactive terminal. Run: npm start');
  process.exitCode = 1;
} else {
  const game = new Game();
  let timer;
  let closed = false;
  const originalRaw = Boolean(input.isRaw);
  const largeEnough = () => output.columns >= 52 && output.rows >= 24;
  const draw = () => {
    if (closed) return;
    output.write('\x1b[H\x1b[2J' + (largeEnough()
      ? render(game)
      : 'Paused: resize terminal to at least 52 columns by 24 rows. Q: quit'));
  };
  const schedule = () => {
    clearTimeout(timer);
    if (closed || game.gameOver) return;
    timer = setTimeout(() => {
      if (largeEnough()) game.step();
      draw();
      schedule();
    }, game.fallInterval);
  };
  const cleanup = () => {
    if (closed) return;
    closed = true;
    clearTimeout(timer);
    input.off('keypress', onKey);
    output.off('resize', draw);
    input.setRawMode(originalRaw);
    input.pause();
    output.write('\x1b[?25h\x1b[?1049l');
  };
  const onKey = (str, key = {}) => {
    if (key.name === 'q' || (key.ctrl && key.name === 'c')) {
      cleanup();
      return;
    }
    if (!largeEnough() || game.gameOver) return;
    switch (key.name) {
      case 'left': game.move(-1); break;
      case 'right': game.move(1); break;
      case 'up': game.rotate(); break;
      case 'down': game.step(true); break;
      case 'space': game.hardDrop(); break;
      default: return;
    }
    draw();
    if (game.gameOver) clearTimeout(timer);
  };
  process.once('exit', cleanup);
  process.once('SIGINT', cleanup);
  process.once('SIGTERM', cleanup);
  process.once('uncaughtException', error => {
    cleanup();
    console.error(error);
    process.exitCode = 1;
  });
  readline.emitKeypressEvents(input);
  input.setRawMode(true);
  input.resume();
  input.on('keypress', onKey);
  output.on('resize', draw);
  output.write('\x1b[?1049h\x1b[?25l');
  draw();
  schedule();
}
