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
      schedule();
    }, game.gravityInterval);
  };
  const stop = () => {
    if (stopped) return;
    stopped = true;
    clearTimeout(timer);
    input.off('keypress', onKey);
    output.off('resize', onResize);
    input.setRawMode(Boolean(wasRaw));
    input.pause();
    output.write('\x1b[?25h\x1b[?1049l');
  };
  const onKey = (_text, key) => {
    if (key?.name === 'q' || (key?.ctrl && key.name === 'c')) {
      stop();
      return;
    }
    if (!fits()) return;
    const result = handleKey(game, key);
    if (result === 'update') {
      draw();
      // Preserve the gravity deadline during movement; adjust on level changes.
      if (game.gameOver) clearTimeout(timer);
    }
  };
  const onResize = () => {
    draw();
    schedule();
  };

  emitKeypressEvents(input);
  input.setRawMode(true);
  input.on('keypress', onKey);
  output.on('resize', onResize);
  input.resume();
  output.write('\x1b[?1049h\x1b[?25l');
  draw();
  schedule();
  return stop;
}
