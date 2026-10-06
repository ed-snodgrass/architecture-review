export const WIDTH = 10;
export const HEIGHT = 20;

// Square matrices preserve a consistent rotation center, including the I piece.
export const SHAPES = Object.freeze({
  I: [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
  O: [[1, 1], [1, 1]],
  T: [[0, 1, 0], [1, 1, 1], [0, 0, 0]],
  S: [[0, 1, 1], [1, 1, 0], [0, 0, 0]],
  Z: [[1, 1, 0], [0, 1, 1], [0, 0, 0]],
  J: [[1, 0, 0], [1, 1, 1], [0, 0, 0]],
  L: [[0, 0, 1], [1, 1, 1], [0, 0, 0]],
});
for (const shape of Object.values(SHAPES)) {
  shape.forEach(Object.freeze);
  Object.freeze(shape);
}

export function rotateMatrix(matrix, clockwise = true) {
  const size = matrix.length;
  return Array.from({ length: size }, (_, y) =>
    Array.from({ length: size }, (_, x) =>
      clockwise ? matrix[size - 1 - x][y] : matrix[x][size - 1 - y]));
}

export class Tetris {
  constructor({ random = Math.random } = {}) {
    this.random = random;
    this.reset();
  }

  reset() {
    this.board = Array.from({ length: HEIGHT }, () => Array(WIDTH).fill(null));
    this.score = 0;
    this.lines = 0;
    this.gameOver = false;
    this.bag = [];
    this.active = null;
    this.next = this.takePiece();
    this.spawn();
  }

  get level() {
    return 1 + Math.floor(this.lines / 10);
  }

  get gravityMs() {
    return Math.max(100, 800 - (this.level - 1) * 60);
  }

  takePiece() {
    if (!this.bag.length) {
      this.bag = Object.keys(SHAPES);
      for (let i = this.bag.length - 1; i > 0; i--) {
        const j = Math.floor(this.random() * (i + 1));
        [this.bag[i], this.bag[j]] = [this.bag[j], this.bag[i]];
      }
    }
    return this.bag.pop();
  }

  spawn() {
    const type = this.next;
    this.next = this.takePiece();
    const matrix = SHAPES[type].map(row => [...row]);
    this.active = { type, matrix, x: Math.floor((WIDTH - matrix.length) / 2), y: 0 };
    if (this.collides(this.active)) {
      this.gameOver = true;
      this.active = null;
    }
  }

  collides({ matrix, x, y }) {
    return matrix.some((row, dy) => row.some((cell, dx) => {
      if (!cell) return false;
      const bx = x + dx;
      const by = y + dy;
      return bx < 0 || bx >= WIDTH || by >= HEIGHT ||
        (by >= 0 && this.board[by][bx] !== null);
    }));
  }

  move(dx, dy = 0) {
    if (this.gameOver || !this.active) return false;
    const candidate = { ...this.active, x: this.active.x + dx, y: this.active.y + dy };
    if (this.collides(candidate)) return false;
    this.active = candidate;
    return true;
  }

  rotate(clockwise = true) {
    if (this.gameOver || !this.active) return false;
    const matrix = rotateMatrix(this.active.matrix, clockwise);
    // Simple kicks let pieces rotate alongside a wall or near the floor.
    for (const [dx, dy] of [[0, 0], [-1, 0], [1, 0], [-2, 0], [2, 0], [0, -1], [0, -2]]) {
      const candidate = { ...this.active, matrix, x: this.active.x + dx, y: this.active.y + dy };
      if (!this.collides(candidate)) {
        this.active = candidate;
        return true;
      }
    }
    return false;
  }

  tick() {
    if (this.gameOver) return false;
    if (this.move(0, 1)) return true;
    this.lock();
    return false;
  }

  softDrop() {
    if (this.gameOver) return false;
    if (this.move(0, 1)) {
      this.score++;
      return true;
    }
    this.lock();
    return false;
  }

  hardDrop() {
    if (this.gameOver) return 0;
    let distance = 0;
    while (this.move(0, 1)) distance++;
    this.score += distance * 2;
    this.lock();
    return distance;
  }

  lock() {
    if (this.gameOver || !this.active) return;
    const { matrix, x, y, type } = this.active;
    let aboveBoard = false;
    matrix.forEach((row, dy) => row.forEach((cell, dx) => {
      if (!cell) return;
      if (y + dy < 0) aboveBoard = true;
      else this.board[y + dy][x + dx] = type;
    }));
    this.active = null;
    if (aboveBoard) {
      this.gameOver = true;
      return;
    }
    this.clearLines();
    this.spawn();
  }

  clearLines() {
    const remaining = this.board.filter(row => row.some(cell => cell === null));
    const cleared = HEIGHT - remaining.length;
    this.score += [0, 100, 300, 500, 800][cleared] * this.level;
    this.lines += cleared;
    this.board = [
      ...Array.from({ length: cleared }, () => Array(WIDTH).fill(null)),
      ...remaining,
    ];
    return cleared;
  }

  // Return a fresh view so rendering cannot mutate the settled board.
  getDisplayBoard() {
    const board = this.board.map(row => [...row]);
    if (this.active) {
      const { matrix, x, y, type } = this.active;
      matrix.forEach((row, dy) => row.forEach((cell, dx) => {
        if (cell && y + dy >= 0 && y + dy < HEIGHT && x + dx >= 0 && x + dx < WIDTH) {
          board[y + dy][x + dx] = type;
        }
      }));
    }
    return board;
  }
}
