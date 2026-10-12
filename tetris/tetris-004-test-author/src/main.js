import { emitKeypressEvents } from 'node:readline';
import { createGame, move, rotate, tick } from './game.js';
import { render, terminalFits } from './render.js';

if (!process.stdin.isTTY || !process.stdout.isTTY) {
  console.error('Tetris requires an interactive terminal. Run npm start in a terminal.');
  process.exitCode = 1;
} else {
  const input = process.stdin;
  const wasRaw = Boolean(input.isRaw);
  const game = createGame();
  let timer;
  let stopped = false;
  let paused = !terminalFits(process.stdout);
  let lastTick = Date.now();

  function syncPause() {
    const undersized = !terminalFits(process.stdout);
    if (undersized !== paused) {
      paused = undersized;
      // Never catch up hidden time; resume with a full gravity interval.
      lastTick = Date.now();
      game.elapsedMs = 0;
    }
    return paused;
  }

  // All shutdown paths share idempotent cleanup, including unexpected exits.
  function cleanup() {
    if (stopped) return;
    stopped = true;
    clearInterval(timer);
    input.removeListener('keypress', onKey);
    input.removeListener('end', exit);
    input.removeListener('error', onError);
    process.stdout.removeListener('resize', draw);
    process.removeListener('SIGINT', exit);
    process.removeListener('SIGTERM', exit);
    process.removeListener('exit', cleanup);
    input.setRawMode(wasRaw);
    input.pause();
    process.stdout.write('\x1b[?25h\x1b[?1049l');
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

  function draw() {
    syncPause();
    // Home and erase rather than append; no trailing newline at row 24.
    process.stdout.write('\x1b[H\x1b[2J' + render(game, {
      columns: process.stdout.columns,
      rows: process.stdout.rows,
    }));
  }

  function onKey(text, key = {}) {
    if (stopped) return;
    if ((key.ctrl && key.name === 'c') || key.name === 'q') {
      exit();
      return;
    }
    if (syncPause()) return;
    switch (key.name) {
      case 'left': move(game, -1, 0); break;
      case 'right': move(game, 1, 0); break;
      case 'down': move(game, 0, 1); break;
      case 'up': rotate(game); break;
      default: return;
    }
    draw();
  }

  process.once('SIGINT', exit);
  process.once('SIGTERM', exit);
  process.once('exit', cleanup);
  input.once('end', exit);
  input.once('error', onError);
  process.stdout.on('resize', draw);

  try {
    emitKeypressEvents(input);
    input.on('keypress', onKey);
    input.setRawMode(true);
    input.resume();
    process.stdout.write('\x1b[?1049h\x1b[?25l');
    draw();

    timer = setInterval(() => {
      if (stopped) return;
      const isPaused = syncPause();
      const now = Date.now();
      if (!isPaused) tick(game, Math.max(0, now - lastTick));
      lastTick = now;
      draw();
    }, 50);
  } catch (error) {
    onError(error);
  }
}
