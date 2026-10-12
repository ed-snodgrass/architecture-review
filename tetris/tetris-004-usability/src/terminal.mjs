import readline from 'node:readline';
import { Game } from './game.mjs';
import { render, DISPLAY_COLUMNS, DISPLAY_ROWS } from './render.mjs';

// Dependencies are injectable so input and terminal restoration can be tested.
export function startTerminal({
  input = process.stdin,
  output = process.stdout,
  lifecycle = process,
  game = new Game(),
  setTimer = setTimeout,
  clearTimer = clearTimeout,
  reportError = error => console.error(error),
} = {}) {
  if (!input.isTTY || !output.isTTY) {
    throw new Error('Tetris requires an interactive terminal. Run: npm start');
  }
  let timer;
  let closed = false;
  let screenEntered = false;
  const originalRaw = Boolean(input.isRaw);
  const largeEnough = () => output.columns >= DISPLAY_COLUMNS && output.rows >= DISPLAY_ROWS;
  const draw = () => {
    if (closed) return;
    output.write('\x1b[H\x1b[2J' + (largeEnough()
      ? render(game)
      : `Paused: resize to ${DISPLAY_COLUMNS} columns by ${DISPLAY_ROWS} rows. Q/^C: quit`
        .slice(0, Math.max(0, output.columns || 0))));
  };
  const cleanup = () => {
    if (closed) return;
    closed = true;
    clearTimer(timer);
    input.off('keypress', onKey);
    input.off('end', cleanup);
    input.off('close', cleanup);
    input.off('error', fail);
    output.off('resize', redraw);
    output.off('error', fail);
    lifecycle.off('exit', cleanup);
    lifecycle.off('SIGINT', cleanup);
    lifecycle.off('SIGTERM', cleanup);
    lifecycle.off('SIGHUP', cleanup);
    lifecycle.off('uncaughtException', fail);
    // Always attempt screen restoration, even if restoring raw mode fails.
    try {
      input.setRawMode(originalRaw);
    } finally {
      input.pause();
      if (screenEntered) output.write('\x1b[?25h\x1b[?1049l');
    }
  };
  const fail = error => {
    try { cleanup(); } finally {
      lifecycle.exitCode = 1;
      reportError(error);
    }
  };
  const guard = action => (...args) => {
    try { action(...args); } catch (error) { fail(error); }
  };
  const redraw = guard(draw);
  const schedule = () => {
    clearTimer(timer);
    if (closed || game.gameOver) return;
    timer = setTimer(guard(() => {
      if (largeEnough()) game.step();
      draw();
      schedule();
    }), game.fallInterval);
  };
  const onKey = guard((str, key = {}) => {
    if (key.name === 'q' || (key.ctrl && key.name === 'c')) {
      cleanup();
      return;
    }
    // Modified arrows must not accidentally trigger gameplay.
    if (key.ctrl || key.meta || !largeEnough() || game.gameOver) return;
    switch (key.name) {
      case 'left': game.move(-1); break;
      case 'right': game.move(1); break;
      case 'up': game.rotate(); break;
      case 'down': game.step(true); break;
      case 'space': game.hardDrop(); break;
      default: return;
    }
    draw();
    if (game.gameOver) clearTimer(timer);
  });
  try {
    lifecycle.once('exit', cleanup);
    lifecycle.once('SIGINT', cleanup);
    lifecycle.once('SIGTERM', cleanup);
    lifecycle.once('SIGHUP', cleanup);
    lifecycle.once('uncaughtException', fail);
    input.once('end', cleanup);
    input.once('close', cleanup);
    input.on('error', fail);
    output.on('error', fail);
    readline.emitKeypressEvents(input);
    input.on('keypress', onKey);
    input.setRawMode(true);
    input.resume();
    output.on('resize', redraw);
    screenEntered = true;
    output.write('\x1b[?1049h\x1b[?25l');
    draw();
    schedule();
  } catch (error) {
    cleanup();
    throw error;
  }
  return { cleanup };
}
