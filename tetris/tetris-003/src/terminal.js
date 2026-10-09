import { emitKeypressEvents } from 'node:readline';
import { Game } from './game.js';
import { renderGame } from './render.js';

const ENTER_SCREEN = '\x1b[?1049h\x1b[?25l\x1b[?7l\x1b[2J';
const LEAVE_SCREEN = '\x1b[?7h\x1b[?25h\x1b[?1049l';

export function runGame({ game = new Game(), input = process.stdin,
  output = process.stdout, gravityMs = 700 } = {}) {
  if (!input.isTTY || !output.isTTY || typeof input.setRawMode !== 'function') {
    throw new Error('Tetris requires an interactive terminal. Run npm start in a terminal.');
  }

  const wasRaw = Boolean(input.isRaw);
  let timer;
  let stopped = false;
  let screenEntered = false;

  function draw() {
    // Clear each row so shorter status text leaves no stale characters. Clip
    // narrow terminals instead of wrapping the two status rows onto extra rows.
    const width = output.columns || 80;
    const frame = renderGame(game).split('\n')
      .map(line => line.slice(0, width) + '\x1b[K').join('\n');
    output.write('\x1b[H' + frame);
    if (game.gameOver) clearInterval(timer);
  }

  function stop() {
    if (stopped) return;
    stopped = true;
    clearInterval(timer);
    input.removeListener('keypress', onKey);
    input.removeListener('end', stop);
    output.removeListener('resize', draw);
    process.removeListener('exit', stop);
    process.removeListener('SIGINT', onInterrupt);
    process.removeListener('SIGTERM', onTerminate);
    process.removeListener('SIGHUP', onHangup);
    try {
      input.setRawMode(wasRaw);
      input.pause();
    } finally {
      if (screenEntered) output.write(LEAVE_SCREEN);
    }
  }

  function interrupt(code) {
    process.exitCode = code;
    stop();
  }
  function onInterrupt() { interrupt(130); }
  function onTerminate() { interrupt(143); }
  function onHangup() { interrupt(129); }

  function onKey(text, key = {}) {
    if (key.ctrl && key.name === 'c') return onInterrupt();
    if (key.name === 'q' || text?.toLowerCase() === 'q') return stop();
    if (stopped || game.gameOver) return;
    switch (key.name) {
      case 'left': game.move(-1); break;
      case 'right': game.move(1); break;
      case 'up': game.rotate(); break;
      case 'down': game.tick(); break;
      case 'space': game.hardDrop(); break;
      default: return;
    }
    draw();
  }

  try {
    emitKeypressEvents(input);
    input.on('keypress', onKey);
    input.on('end', stop);
    output.on('resize', draw);
    process.on('exit', stop);
    process.on('SIGINT', onInterrupt);
    process.on('SIGTERM', onTerminate);
    process.on('SIGHUP', onHangup);
    input.setRawMode(true);
    input.resume();
    screenEntered = true;
    output.write(ENTER_SCREEN);
    if (!game.gameOver) {
      timer = setInterval(() => {
        game.tick();
        draw();
      }, gravityMs);
    }
    draw();
    return stop;
  } catch (error) {
    stop();
    throw error;
  }
}
