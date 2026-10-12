import { emitKeypressEvents } from 'node:readline';
import { createGame, move, rotate, tick } from './game.js';

if (!process.stdin.isTTY || !process.stdout.isTTY) {
  console.error('Tetris requires an interactive terminal. Run npm start in a terminal.');
  process.exitCode = 1;
} else {
  const input = process.stdin;
  const wasRaw = Boolean(input.isRaw);
  const game = createGame();
  let timer;
  let stopped = false;

  // All shutdown paths share idempotent cleanup, including unexpected exits.
  function cleanup() {
    if (stopped) return;
    stopped = true;
    clearInterval(timer);
    input.removeListener('keypress', onKey);
    input.removeListener('end', exit);
    input.removeListener('error', onError);
    process.removeListener('SIGINT', exit);
    process.removeListener('SIGTERM', exit);
    process.removeListener('exit', cleanup);
    input.setRawMode(wasRaw);
    input.pause();
  }

  function exit() {
    cleanup();
    process.exit(0);
  }

  function onError(error) {
    cleanup();
    console.error(error);
    process.exit(1);
  }

  function onKey(text, key = {}) {
    if (stopped) return;
    if ((key.ctrl && key.name === 'c') || key.name === 'q') {
      exit();
      return;
    }
    switch (key.name) {
      case 'left': move(game, -1, 0); break;
      case 'right': move(game, 1, 0); break;
      case 'down': move(game, 0, 1); break;
      case 'up': rotate(game); break;
    }
  }

  process.once('SIGINT', exit);
  process.once('SIGTERM', exit);
  process.once('exit', cleanup);
  input.once('end', exit);
  input.once('error', onError);

  try {
    emitKeypressEvents(input);
    input.on('keypress', onKey);
    input.setRawMode(true);
    input.resume();
    process.stdout.write('Tetris\nArrows: move; Up: rotate; Q or Ctrl+C: exit.\n');

    let lastTick = Date.now();
    timer = setInterval(() => {
      if (stopped) return;
      const now = Date.now();
      tick(game, Math.max(0, now - lastTick));
      lastTick = now;
    }, 50);
  } catch (error) {
    onError(error);
  }
}
