import { emitKeypressEvents } from 'node:readline';
import { Game } from './game.js';

export const CONTROLS = 'Arrows: move/rotate/drop | Space: hard drop | Q: quit';
export const MIN_COLUMNS = CONTROLS.length;
export const MIN_ROWS = 24;

// A frame has no trailing newline, so writing row 24 does not scroll.
export function renderFrame(game) {
  const board = game.board.map(row => [...row]);
  for (const { x, y, type } of game.cells()) {
    if (y >= 0 && y < game.height && x >= 0 && x < game.width) board[y][x] = type;
  }
  const border = `+${'-'.repeat(game.width * 2)}+`;
  const status = `${game.gameOver ? 'GAME OVER' : 'Tetris'} | Score:${game.score} Lines:${game.lines} Level:${game.level} Next:${game.nextType}`;
  return [
    status.slice(0, MIN_COLUMNS),
    border,
    ...board.map(row => `|${row.map(cell => cell ? '[]' : '  ').join('')}|`),
    border,
    CONTROLS,
  ].join('\n');
}

export function handleKey(game, key = {}) {
  if (key.name === 'q' || (key.ctrl && key.name === 'c')) return 'quit';
  if (game.gameOver) return 'ignored';
  switch (key.name) {
    case 'left': game.move(-1); break;
    case 'right': game.move(1); break;
    case 'up': game.rotate(); break;
    case 'down': game.softDrop(); break;
    case 'space': game.hardDrop(); break;
    default: return 'ignored';
  }
  return 'update';
}

export function startTerminalGame({ input = process.stdin, output = process.stdout, game = new Game() } = {}) {
  if (!input.isTTY || !output.isTTY) {
    output.write('Tetris requires an interactive terminal. Run npm start in a terminal.\n');
    return false;
  }
  if (output.columns < MIN_COLUMNS || output.rows < MIN_ROWS) {
    output.write(`Tetris needs a terminal at least ${MIN_COLUMNS} columns by ${MIN_ROWS} rows.\n`);
    return false;
  }

  let timer;
  let stopped = false;
  const wasRaw = input.isRaw;
  const wasPaused = input.isPaused();
  const wasFlowing = input.readableFlowing;
  const inputListeners = new Map(input.eventNames().map(name => [name, input.listeners(name)]));
  let readlineListeners = [];
  const fits = () => output.columns >= MIN_COLUMNS && output.rows >= MIN_ROWS;
  const draw = () => {
    const frame = fits()
      ? renderFrame(game)
      : `Resize to at least ${MIN_COLUMNS} columns by ${MIN_ROWS} rows. Q: quit`;
    // Clear each row to remove stale status text; use CRLF in raw mode.
    output.write(`\x1b[H${frame.split('\n').map(line => `\x1b[2K${line}`).join('\r\n')}\x1b[J`);
  };
  const schedule = () => {
    clearTimeout(timer);
    if (stopped || game.gameOver || !fits()) return;
    timer = setTimeout(() => {
      game.tick();
      draw();
      if (game.gameOver) stop(true);
      else schedule();
    }, game.gravityInterval);
  };
  const stop = (showGameOver = false) => {
    if (stopped) return;
    stopped = true;
    clearTimeout(timer);
    input.off('keypress', onKey);
    for (const [name, listener] of readlineListeners) input.off(name, listener);
    output.off('resize', onResize);
    process.off('SIGINT', onSignal);
    process.off('SIGTERM', onSignal);
    process.off('exit', onExit);
    try {
      input.setRawMode(Boolean(wasRaw));
      // A fresh stdin has readableFlowing === null, not isPaused() === true.
      // Leaving that stream resumed keeps the CLI alive after quitting.
      if (wasPaused || wasFlowing !== true) input.pause();
    } finally {
      output.write('\x1b[?25h\x1b[?1049l');
      // The alternate screen disappears on exit. Keep the result visible on
      // the normal screen, still using only the game's 24-row frame.
      if (showGameOver && fits()) draw();
    }
  };
  const onSignal = signal => {
    stop();
    process.exitCode = signal === 'SIGINT' ? 130 : 143;
  };
  const onExit = () => stop();
  const onKey = (_text, key) => {
    if (stopped) return;
    if (key?.name === 'q' || (key?.ctrl && key.name === 'c')) {
      stop();
      return;
    }
    if (!fits()) return;
    const result = handleKey(game, key);
    if (result === 'update') {
      draw();
      // Preserve the gravity deadline during movement; adjust on level changes.
      if (game.gameOver) stop(true);
    }
  };
  const onResize = () => {
    draw();
    schedule();
  };

  try {
    emitKeypressEvents(input);
    input.on('keypress', onKey);
    // readline installs its own data/newListener handlers. Remove only the
    // handlers added by this session, preserving the caller's listeners.
    readlineListeners = input.eventNames().flatMap(name =>
      input.listeners(name)
        .filter(listener => listener !== onKey && !(inputListeners.get(name) || []).includes(listener))
        .map(listener => [name, listener]),
    );
    output.on('resize', onResize);
    process.on('SIGINT', onSignal);
    process.on('SIGTERM', onSignal);
    process.on('exit', onExit);
    input.setRawMode(true);
    input.resume();
    output.write('\x1b[?1049h\x1b[?25l');
    draw();
    if (game.gameOver) stop(true);
    else schedule();
  } catch (error) {
    stop();
    throw error;
  }
  return stop;
}
