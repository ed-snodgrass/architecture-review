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
  const type = pieceSequence?.[0] ?? names[Math.floor(Math.random() * names.length)];
  const shape = SHAPES[type];
  return {
    board: Array.from({ length: HEIGHT }, () => Array(WIDTH).fill(null)),
    active: {
      type,
      x: Math.floor((WIDTH - shape.size) / 2),
      y: 0,
      cells: shape.cells.map(([x, y]) => ({ x, y })),
    },
    fallIntervalMs,
    elapsedMs: 0,
  };
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
  if (!Number.isInteger(dx) || !Number.isInteger(dy) || Math.abs(dx) + Math.abs(dy) !== 1) {
    return false;
  }
  const candidate = { ...game.active, x: game.active.x + dx, y: game.active.y + dy };
  if (!isLegal(game, candidate)) return false;
  game.active = candidate;
  return true;
}

export function rotate(game) {
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
  if (!Number.isFinite(elapsedMs) || elapsedMs < 0) {
    throw new RangeError('elapsedMs must be a nonnegative finite number');
  }
  const total = game.elapsedMs + elapsedMs;
  const steps = Math.floor(total / game.fallIntervalMs);
  game.elapsedMs = total % game.fallIntervalMs;
  for (let step = 0; step < steps; step++) {
    // Locking and spawning the next piece belong to the next task.
    if (!move(game, 0, 1)) break;
  }
}
