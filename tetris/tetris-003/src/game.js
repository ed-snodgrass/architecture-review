export const BOARD_WIDTH = 10;
export const BOARD_HEIGHT = 20;

// Square matrices retain the rotation origin, including the I piece's padding.
export const TETROMINOES = Object.freeze(Object.fromEntries(
  Object.entries({
    I: [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
    J: [[1, 0, 0], [1, 1, 1], [0, 0, 0]],
    L: [[0, 0, 1], [1, 1, 1], [0, 0, 0]],
    O: [[1, 1], [1, 1]],
    S: [[0, 1, 1], [1, 1, 0], [0, 0, 0]],
    T: [[0, 1, 0], [1, 1, 1], [0, 0, 0]],
    Z: [[1, 1, 0], [0, 1, 1], [0, 0, 0]],
  }).map(([type, rows]) => [type, Object.freeze(rows.map(row => Object.freeze(row)))])
));

export function createBoard() {
  return Array.from({ length: BOARD_HEIGHT }, () => Array(BOARD_WIDTH).fill(null));
}

function rotated(matrix, direction) {
  const size = matrix.length;
  return Array.from({ length: size }, (_, y) =>
    Array.from({ length: size }, (_, x) => direction === 1
      ? matrix[size - 1 - x][y]
      : matrix[x][size - 1 - y]));
}

export class Game {
  constructor({ random = Math.random } = {}) {
    this.board = createBoard();
    this.random = random;
    this.bag = [];
    this.active = null;
    this.spawn();
  }

  nextType() {
    if (this.bag.length === 0) {
      this.bag = Object.keys(TETROMINOES);
      for (let i = this.bag.length - 1; i > 0; i--) {
        const j = Math.floor(this.random() * (i + 1));
        [this.bag[i], this.bag[j]] = [this.bag[j], this.bag[i]];
      }
    }
    return this.bag.pop();
  }

  // Do not replace a falling piece. A blocked spawn returns false; the caller
  // can later use this signal to implement game-over handling.
  spawn(type) {
    if (this.active) return false;
    type ??= this.nextType();
    if (!Object.hasOwn(TETROMINOES, type)) {
      throw new RangeError(`Unknown tetromino: ${type}`);
    }
    const matrix = TETROMINOES[type].map(row => [...row]);
    const piece = {
      type,
      matrix,
      x: Math.floor((BOARD_WIDTH - matrix.length) / 2),
      y: 0,
    };
    if (!this.canPlace(piece)) return false;
    this.active = piece;
    return true;
  }

  canPlace(piece) {
    for (let y = 0; y < piece.matrix.length; y++) {
      for (let x = 0; x < piece.matrix[y].length; x++) {
        if (!piece.matrix[y][x]) continue;
        const boardX = piece.x + x;
        const boardY = piece.y + y;
        if (boardX < 0 || boardX >= BOARD_WIDTH ||
            boardY < 0 || boardY >= BOARD_HEIGHT ||
            this.board[boardY][boardX] !== null) return false;
      }
    }
    return true;
  }

  // A move is one cell horizontally or downwards, never a teleport through cells.
  move(dx, dy = 0) {
    if (!this.active || !Number.isInteger(dx) || !Number.isInteger(dy) ||
        Math.abs(dx) + Math.abs(dy) !== 1 || dy < 0) return false;
    const candidate = { ...this.active, x: this.active.x + dx, y: this.active.y + dy };
    if (!this.canPlace(candidate)) return false;
    this.active = candidate;
    return true;
  }

  rotate(direction = 1) {
    if (!this.active || (direction !== 1 && direction !== -1)) return false;
    const matrix = rotated(this.active.matrix, direction);
    // Small horizontal wall kicks keep rotation usable beside the walls.
    for (const offset of [0, -1, 1, -2, 2]) {
      const candidate = { ...this.active, matrix, x: this.active.x + offset };
      if (this.canPlace(candidate)) {
        this.active = candidate;
        return true;
      }
    }
    return false;
  }

  // One gravity pulse. The terminal loop will determine the pulse interval.
  tick() {
    if (!this.active) return false;
    if (this.move(0, 1)) return true;
    return this.lock();
  }

  lock() {
    if (!this.active || !this.canPlace(this.active) ||
        this.canPlace({ ...this.active, y: this.active.y + 1 })) return false;
    const { type, matrix, x, y } = this.active;
    for (let row = 0; row < matrix.length; row++) {
      for (let col = 0; col < matrix[row].length; col++) {
        if (matrix[row][col]) this.board[y + row][x + col] = type;
      }
    }
    this.active = null;
    this.spawn();
    return true;
  }
}
