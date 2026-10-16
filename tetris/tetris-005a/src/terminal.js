import { emitKeypressEvents } from 'node:readline';
import { Game, WIDTH } from './engine.js';

export const MIN_COLUMNS = 64;
export const MIN_ROWS = 24;
const controls = 'Arrows: move/rotate/drop  Space: hard drop  R: restart  Q: quit';

/** Exactly 24 lines, with no trailing newline (avoids scrolling at row 24). */
export function render(game, columns = MIN_COLUMNS) {
  const board = game.board.map(row => [...row]);
  for (const { x, y } of game.cells()) board[y][x] = game.active.type;
  const border = `+${'-'.repeat(WIDTH * 2)}+`;
  const status = `${game.gameOver ? 'GAME OVER! R: restart | ' : ''}Score: ${game.score}  Lines: ${game.lines}  Level: ${game.level}  Next: ${game.nextType}`;
  return [
    border,
    ...board.map(row => `|${row.map(cell => cell ? '[]' : '  ').join('')}|`),
    border,
    status.slice(0, columns - 1),
    controls,
  ].join('\n');
}

/**
 * Injectable terminal controller. lifecycle is a process-like EventEmitter;
 * scheduler exposes setInterval/clearInterval and now returns milliseconds.
 * setupKeypress can be replaced when tests emit keypress events directly.
 * The returned stop() is idempotent and restores terminal state.
 */
export function runTerminal({
  game = new Game(),
  input = process.stdin,
  output = process.stdout,
  errorOutput = process.stderr,
  lifecycle = process,
  now = Date.now,
  scheduler = { setInterval, clearInterval },
  setupKeypress = emitKeypressEvents,
} = {}) {
  if (!input.isTTY || !output.isTTY || typeof input.setRawMode !== 'function') {
    errorOutput.write('Tetris requires an interactive terminal (at least 64 columns by 24 rows).\n');
    lifecycle.exitCode = 1;
    return { stop() {} };
  }

  const wasRaw = input.isRaw;
  const wasPaused = input.isPaused();
  let timer;
  let started = false;
  let stopped = false;
  let nextTick = now() + game.gravityIntervalMs;
  const fits = () => output.columns >= MIN_COLUMNS && output.rows >= MIN_ROWS;

  function draw() {
    const frame = fits()
      ? render(game, output.columns)
      : 'Resize to at least 64x24. Q: quit'.slice(0, Math.max(0, (output.columns || 1) - 1));
    // Clear in place rather than printing successive frames into scrollback.
    output.write(`\x1b[H\x1b[2J${frame}`);
  }

  function cleanup() {
    if (stopped) return;
    stopped = true;
    if (timer !== undefined) scheduler.clearInterval(timer);
    input.removeListener('keypress', onKey);
    output.removeListener('resize', onResize);
    output.removeListener('error', onError);
    for (const [signal, handler] of signals) lifecycle.removeListener(signal, handler);
    lifecycle.removeListener('uncaughtException', onError);
    lifecycle.removeListener('unhandledRejection', onError);
    lifecycle.removeListener('exit', cleanup);
    try { input.setRawMode(Boolean(wasRaw)); } catch { /* Terminal may be gone. */ }
    if (wasPaused) input.pause();
    else input.resume();
    if (started && !output.destroyed) {
      try { output.write('\x1b[0m\x1b[?25h\x1b[?1049l'); } catch { /* Output may be gone. */ }
    }
  }

  function finish(code = 0) {
    cleanup();
    lifecycle.exitCode = code;
  }

  function onError(error) {
    finish(1);
    errorOutput.write(`Tetris: ${String(error?.message ?? error).replace(/[\r\n\x1b]/g, ' ')}\n`);
  }

  function onResize() {
    if (stopped) return;
    nextTick = now() + game.gravityIntervalMs;
    draw();
  }

  function onKey(text, key = {}) {
    if (stopped) return;
    if ((key.ctrl && key.name === 'c') || key.name === 'q' || text === 'q' || text === 'Q') {
      finish();
      return;
    }
    if (!fits()) return;
    if (key.name === 'r' && game.gameOver) {
      game.restart();
      nextTick = now() + game.gravityIntervalMs;
    } else if (!game.gameOver) {
      switch (key.name) {
        case 'left': game.move(-1); break;
        case 'right': game.move(1); break;
        case 'up': game.rotate(); break;
        case 'down':
          game.softDrop();
          nextTick = now() + game.gravityIntervalMs;
          break;
        case 'space':
          game.hardDrop();
          nextTick = now() + game.gravityIntervalMs;
          break;
        default: return;
      }
    }
    draw();
  }

  const signals = [
    ['SIGINT', () => finish(130)],
    ['SIGTERM', () => finish(143)],
    ['SIGHUP', () => finish(129)],
  ];
  try {
    for (const [signal, handler] of signals) lifecycle.on(signal, handler);
    lifecycle.on('uncaughtException', onError);
    lifecycle.on('unhandledRejection', onError);
    lifecycle.on('exit', cleanup);
    output.on('error', onError);
    output.on('resize', onResize);
    setupKeypress(input);
    input.on('keypress', onKey);
    input.setRawMode(true);
    input.resume();
    started = true;
    output.write('\x1b[?1049h\x1b[?25l');
    draw();
    if (!stopped) timer = scheduler.setInterval(() => {
      if (stopped) return;
      if (!fits() || game.gameOver) {
        nextTick = now() + game.gravityIntervalMs;
        return;
      }
      if (now() >= nextTick) {
        game.tick();
        nextTick = now() + game.gravityIntervalMs;
        draw();
      }
    }, 25);
  } catch (error) {
    onError(error);
  }
  return { stop: cleanup };
}
