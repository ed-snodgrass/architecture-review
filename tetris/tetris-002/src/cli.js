import { emitKeypressEvents } from 'node:readline';
import { Tetris } from './engine.js';
import { renderScreen, SCREEN_COLUMNS, SCREEN_ROWS } from './display.js';

const input = process.stdin;
const output = process.stdout;

if (!input.isTTY || !output.isTTY || typeof input.setRawMode !== 'function') {
  console.error('Tetris needs an interactive terminal. Run npm start in a terminal.');
  process.exitCode = 1;
} else {
  const game = new Tetris();
  const originalRawMode = input.isRaw;
  let timer;
  let stopped = false;
  let terminalEntered = false;

  function fits() {
    return (output.columns ?? 80) >= SCREEN_COLUMNS && (output.rows ?? 24) >= SCREEN_ROWS;
  }

  function draw() {
    const lines = fits() ? renderScreen(game) : [
      `Resize terminal to ${SCREEN_COLUMNS}x${SCREEN_ROWS}. Q to quit.`
        .slice(0, Math.max(0, (output.columns ?? 80) - 1)),
    ];
    // No trailing newline: a 24-row terminal must never scroll the game.
    output.write(`\x1b[H\x1b[2J${lines.join('\r\n')}`);
  }

  function scheduleGravity() {
    clearTimeout(timer);
    if (stopped || game.gameOver || !fits()) return;
    timer = setTimeout(() => {
      game.tick();
      draw();
      scheduleGravity();
    }, game.gravityMs);
  }

  function cleanup() {
    if (stopped) return;
    stopped = true;
    clearTimeout(timer);
    input.removeListener('keypress', onKey);
    output.removeListener('resize', onResize);
    process.removeListener('SIGINT', quit);
    process.removeListener('SIGTERM', terminate);
    process.removeListener('SIGHUP', hangup);
    process.removeListener('uncaughtException', fail);
    try {
      input.setRawMode(Boolean(originalRawMode));
    } finally {
      input.pause();
      if (terminalEntered) output.write('\x1b[?25h\x1b[?1049l');
    }
  }

  function quit() { cleanup(); }
  function terminate() { process.exitCode = 143; cleanup(); }
  function hangup() { process.exitCode = 129; cleanup(); }
  function fail(error) {
    cleanup();
    console.error(error);
    process.exitCode = 1;
  }

  function onResize() {
    draw();
    scheduleGravity();
  }

  function onKey(character, key = {}) {
    const name = key.name ?? character;
    if (name === 'q' || name === 'escape' || (key.ctrl && name === 'c')) {
      quit();
      return;
    }
    if (name === 'r') {
      game.reset();
      draw();
      scheduleGravity();
      return;
    }
    if (game.gameOver || !fits()) return;
    const previousMatrix = game.active?.matrix;
    switch (name) {
      case 'left': case 'a': game.move(-1); break;
      case 'right': case 'd': game.move(1); break;
      case 'up': case 'w': game.rotate(); break;
      case 'z': game.rotate(-1); break;
      case 'down': case 's': game.softDrop(); break;
      case 'space': game.hardDrop(); break;
      default: return;
    }
    draw();
    // Movement must not postpone gravity indefinitely. Restart the timer only
    // when a piece locks or the game ends (and may change the level/speed).
    if (game.gameOver || name === 'space' ||
        ((name === 'down' || name === 's') && game.active?.matrix !== previousMatrix)) {
      scheduleGravity();
    }
  }

  process.once('exit', cleanup);
  process.on('SIGINT', quit);
  process.on('SIGTERM', terminate);
  process.on('SIGHUP', hangup);
  process.on('uncaughtException', fail);
  try {
    emitKeypressEvents(input);
    input.setRawMode(true);
    input.on('keypress', onKey);
    output.on('resize', onResize);
    input.resume();
    terminalEntered = true;
    output.write('\x1b[?1049h\x1b[?25l');
    draw();
    scheduleGravity();
  } catch (error) {
    fail(error);
  }
}
