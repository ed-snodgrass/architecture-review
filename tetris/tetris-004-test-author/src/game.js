// Pure game mechanics: coordinates use x rightward and y downward.
const WIDTH = 10;
const HEIGHT = 20;
const SHAPES = {
  I: { size: 4, cells: [[0, 0], [1, 0], [2, 0], [3, 0]] },
  O: { size: 2, cells: [[0, 0], [1, 0], [0, 1], [1, 1]] },
  T: { size: 3, cells: [[0, 0], [1, 0], [2, 0], [1, 1]] },
  S: { size: 3, cells: [[1, 0], [2, 0], [0, 1], [1, 1]] },
  Z: { size: 3, cells: [[0, 0], [1, 0], [1, 1], [2, 1]] },
  J: { size: 3, cells: [[0, 0], [0, 1], [1, 1], [2, 1]] },
  L: { size: 3, cells: [[2, 0], [0, 1], [1, 1], [2, 1]] },
};

export function createGame({ pieceSequence, fallIntervalMs = 1000 } = {}) {
  if (!Number.isFinite(fallIntervalMs) || fallIntervalMs <= 0) {
    throw new RangeError('fallIntervalMs must be a positive finite number');
  }
  const names = Object.keys(SHAPES);
  if (pieceSequence !== undefined &&
      (!Array.isArray(pieceSequence) || pieceSequence.length === 0 ||
       pieceSequence.some(type => !names.includes(type)))) {
    throw new TypeError('pieceSequence must contain valid tetromino names');
  }
  const game = {
    board: Array.from({ length: HEIGHT }, () => Array(WIDTH).fill(null)),
    active: null,
    pieceSequence: pieceSequence ? [...pieceSequence] : null,
    pieceIndex: 0,
    score: 0,
    gameOver: false,
    fallIntervalMs,
    elapsedMs: 0,
  };
  spawnPiece(game);
  return game;
}

function spawnPiece(game) {
  const names = Object.keys(SHAPES);
  // Repeat supplied sequences for deterministic games of any length.
  const type = game.pieceSequence
    ? game.pieceSequence[game.pieceIndex++ % game.pieceSequence.length]
    : names[Math.floor(Math.random() * names.length)];
  const shape = SHAPES[type];
  game.active = {
    type,
    x: Math.floor((WIDTH - shape.size) / 2),
    y: 0,
    cells: shape.cells.map(([x, y]) => ({ x, y })),
  };
  game.gameOver = !isLegal(game, game.active);
}

function lockPiece(game) {
  for (const { x, y } of getActiveCells(game)) {
    game.board[y][x] = game.active.type;
  }
  clearCompletedLines(game);
  // Clearing must happen before checking whether the next spawn is blocked.
  spawnPiece(game);
}

function clearCompletedLines(game) {
  const survivors = game.board.filter(row => row.some(cell => cell === null));
  const cleared = HEIGHT - survivors.length;
  if (cleared > 0) {
    game.board = [
      ...Array.from({ length: cleared }, () => Array(WIDTH).fill(null)),
      ...survivors,
    ];
    // Classic line-clear rewards; score persists across spawns.
    game.score += [0, 100, 300, 500, 800][cleared] ?? cleared * 200;
  }
}

function absoluteCells(active) {
  return active.cells.map(({ x, y }) => ({ x: active.x + x, y: active.y + y }));
}

export function getActiveCells(game) {
  return absoluteCells(game.active);
}

function isLegal(game, active) {
  return absoluteCells(active).every(({ x, y }) =>
    x >= 0 && x < WIDTH && y >= 0 && y < HEIGHT && game.board[y][x] === null);
}

export function move(game, dx, dy) {
  if (game.gameOver) return false;
  if (!Number.isInteger(dx) || !Number.isInteger(dy) || Math.abs(dx) + Math.abs(dy) !== 1) {
    return false;
  }
  const candidate = { ...game.active, x: game.active.x + dx, y: game.active.y + dy };
  if (!isLegal(game, candidate)) return false;
  game.active = candidate;
  return true;
}

export function rotate(game) {
  if (game.gameOver) return false;
  const size = SHAPES[game.active.type].size;
  const candidate = {
    ...game.active,
    cells: game.active.cells.map(({ x, y }) => ({ x: size - 1 - y, y: x })),
  };
  // No wall kicks: a blocked rotation leaves the entire piece unchanged.
  if (!isLegal(game, candidate)) return false;
  game.active = candidate;
  return true;
}

export function tick(game, elapsedMs) {
  if (game.gameOver) return;
  if (!Number.isFinite(elapsedMs) || elapsedMs < 0) {
    throw new RangeError('elapsedMs must be a nonnegative finite number');
  }
  const total = game.elapsedMs + elapsedMs;
  const steps = Math.floor(total / game.fallIntervalMs);
  game.elapsedMs = total % game.fallIntervalMs;
  for (let step = 0; step < steps && !game.gameOver; step++) {
    if (!move(game, 0, 1)) lockPiece(game);
  }
}
