export const SHAPES = {
  I: [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
  J: [[1, 0, 0], [1, 1, 1], [0, 0, 0]],
  L: [[0, 0, 1], [1, 1, 1], [0, 0, 0]],
  O: [[1, 1], [1, 1]],
  S: [[0, 1, 1], [1, 1, 0], [0, 0, 0]],
  T: [[0, 1, 0], [1, 1, 1], [0, 0, 0]],
  Z: [[1, 1, 0], [0, 1, 1], [0, 0, 0]],
};

const clone = matrix => matrix.map(row => [...row]);

/** Pure game state, independent of terminal input, rendering, or timers. */
export class Tetris {
  constructor({ width = 10, height = 20, random = Math.random } = {}) {
    if (!Number.isInteger(width) || width < 4 || !Number.isInteger(height) || height < 4) {
      throw new RangeError('Board dimensions must be integers of at least four');
    }
    this.width = width;
    this.height = height;
    this.random = random;
    this.reset();
  }

  reset() {
    this.board = Array.from({ length: this.height }, () => Array(this.width).fill(null));
    this.score = 0;
    this.lines = 0;
    this.gameOver = false;
    this.bag = [];
    this.active = null;
    this.next = this.drawType();
    this.spawn();
  }

  get level() {
    return Math.floor(this.lines / 10) + 1;
  }

  get gravityMs() {
    return Math.max(80, 800 - (this.level - 1) * 60);
  }

  drawType() {
    if (this.bag.length === 0) {
      this.bag = Object.keys(SHAPES);
      for (let i = this.bag.length - 1; i > 0; i--) {
        const j = Math.floor(this.random() * (i + 1));
        [this.bag[i], this.bag[j]] = [this.bag[j], this.bag[i]];
      }
    }
    return this.bag.pop();
  }

  spawn() {
    if (this.gameOver) return false;
    const type = this.next;
    const matrix = clone(SHAPES[type]);
    this.active = { type, matrix, x: Math.floor((this.width - matrix.length) / 2), y: 0 };
    this.next = this.drawType();
    if (!this.canPlace(this.active)) {
      this.gameOver = true;
      return false;
    }
    return true;
  }

  canPlace({ matrix, x, y }) {
    return matrix.every((row, dy) => row.every((filled, dx) => {
      if (!filled) return true;
      const bx = x + dx;
      const by = y + dy;
      return bx >= 0 && bx < this.width && by < this.height &&
        (by < 0 || this.board[by][bx] === null);
    }));
  }

  move(dx, dy = 0) {
    if (this.gameOver || !this.active) return false;
    const candidate = { ...this.active, x: this.active.x + dx, y: this.active.y + dy };
    if (!this.canPlace(candidate)) return false;
    this.active = candidate;
    return true;
  }

  rotate(direction = 1) {
    if (this.gameOver || !this.active) return false;
    const old = this.active.matrix;
    const size = old.length;
    const matrix = old.map((row, y) => row.map((_, x) => direction >= 0
      ? old[size - 1 - x][y]
      : old[x][size - 1 - y]));
    // Small wall/floor kicks allow rotation near edges without crossing blocks.
    for (const [dx, dy] of [[0, 0], [-1, 0], [1, 0], [-2, 0], [2, 0], [0, -1], [0, -2]]) {
      const candidate = { ...this.active, matrix, x: this.active.x + dx, y: this.active.y + dy };
      if (this.canPlace(candidate)) {
        this.active = candidate;
        return true;
      }
    }
    return false;
  }

  tick() {
    if (this.gameOver) return false;
    if (!this.move(0, 1)) this.lock();
    return true;
  }

  softDrop() {
    if (this.gameOver) return false;
    if (this.move(0, 1)) {
      this.score++;
    } else {
      this.lock();
    }
    return true;
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
    matrix.forEach((row, dy) => row.forEach((filled, dx) => {
      if (!filled) return;
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
    const cleared = this.height - remaining.length;
    if (cleared) {
      this.score += ([0, 100, 300, 500, 800][cleared] ?? cleared * 200) * this.level;
      this.lines += cleared;
      this.board = [
        ...Array.from({ length: cleared }, () => Array(this.width).fill(null)),
        ...remaining,
      ];
    }
    return cleared;
  }

  /** Return a renderable copy; never expose mutable board rows to a renderer. */
  visibleBoard() {
    const board = clone(this.board);
    if (this.active && !this.gameOver) {
      const { matrix, x, y, type } = this.active;
      matrix.forEach((row, dy) => row.forEach((filled, dx) => {
        if (filled && y + dy >= 0 && y + dy < this.height && x + dx >= 0 && x + dx < this.width) {
          board[y + dy][x + dx] = type;
        }
      }));
    }
    return board;
  }
}
