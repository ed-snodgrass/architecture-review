import readline from 'node:readline';
import { Tetris } from './engine.js';
import { DISPLAY_ROWS, MIN_COLUMNS, renderFrame } from './display.js';

const input = process.stdin;
const output = process.stdout;

if (!input.isTTY || !output.isTTY) {
  console.error('Tetris needs an interactive terminal. Run npm start in a terminal.');
  process.exitCode = 1;
} else {
  start();
}

function start() {
  const game = new Tetris();
  const wasRaw = input.isRaw;
  let timer;
  let closed = false;
  let entered = false;
  const fits = () => output.columns >= MIN_COLUMNS && output.rows >= DISPLAY_ROWS;

  function draw() {
    const frame = fits()
      ? renderFrame(game)
      : `Resize to at least ${MIN_COLUMNS} columns x ${DISPLAY_ROWS} rows. Q quits.`;
    // Never write a trailing newline: at 24 rows it would scroll the screen.
    // Leave the last column unused, avoiding automatic line wrapping.
    const lines = frame.split('\n').slice(0, output.rows);
    output.write('\x1b[H' + lines.map(line =>
      line.slice(0, Math.max(0, output.columns - 1)) + '\x1b[K').join('\r\n') + '\x1b[J');
  }

  function schedule() {
    clearTimeout(timer);
    if (closed || game.gameOver || !fits()) return;
    timer = setTimeout(() => {
      game.tick();
      draw();
      schedule();
    }, game.gravityMs);
  }

  function cleanup() {
    if (closed) return;
    closed = true;
    clearTimeout(timer);
    input.removeListener('keypress', onKey);
    input.removeListener('end', quit);
    output.removeListener('resize', onResize);
    process.removeListener('SIGINT', quit);
    process.removeListener('SIGTERM', quit);
    process.removeListener('SIGHUP', quit);
    process.removeListener('uncaughtException', onError);
    process.removeListener('exit', cleanup);
    input.setRawMode(Boolean(wasRaw));
    input.pause();
    if (entered) output.write('\x1b[?25h\x1b[?1049l');
  }

  function quit() {
    cleanup();
  }

  function onError(error) {
    cleanup();
    console.error(error);
    process.exitCode = 1;
  }

  function onResize() {
    draw();
    schedule();
  }

  function onKey(text, key = {}) {
    const name = (key.name ?? text ?? '').toLowerCase();
    if (name === 'q' || (key.ctrl && name === 'c')) return quit();
    if (name === 'r') {
      game.reset();
      draw();
      schedule();
      return;
    }
    if (game.gameOver || !fits()) return;
    let resetGravity = false;
    switch (name) {
      case 'left': case 'a': game.move(-1); break;
      case 'right': case 'd': game.move(1); break;
      case 'down': case 's': game.softDrop(); resetGravity = true; break;
      case 'up': case 'w': case 'x': game.rotate(); break;
      case 'z': game.rotate(false); break;
      case 'space': case ' ': game.hardDrop(); resetGravity = true; break;
      default: return;
    }
    draw();
    if (resetGravity || game.gameOver) schedule();
  }

  process.on('exit', cleanup);
  process.on('uncaughtException', onError);
  process.on('SIGINT', quit);
  process.on('SIGTERM', quit);
  process.on('SIGHUP', quit);
  try {
    readline.emitKeypressEvents(input);
    input.setRawMode(true);
    input.on('keypress', onKey);
    input.on('end', quit);
    output.on('resize', onResize);
    input.resume();
    entered = true;
    output.write('\x1b[?1049h\x1b[?25l\x1b[2J');
    draw();
    schedule();
  } catch (error) {
    onError(error);
  }
}
