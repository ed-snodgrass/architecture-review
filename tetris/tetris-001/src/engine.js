export const WIDTH = 10;
export const HEIGHT = 20;
export const SHAPES = Object.freeze({
  I: [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
  O: [[1, 1], [1, 1]],
  T: [[0, 1, 0], [1, 1, 1], [0, 0, 0]],
  S: [[0, 1, 1], [1, 1, 0], [0, 0, 0]],
  Z: [[1, 1, 0], [0, 1, 1], [0, 0, 0]],
  J: [[1, 0, 0], [1, 1, 1], [0, 0, 0]],
  L: [[0, 0, 1], [1, 1, 1], [0, 0, 0]],
});

export class Game {
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
    this.spawn();
  }

  get level() { return Math.floor(this.lines / 10) + 1; }
  get gravityMs() { return Math.max(100, 800 - (this.level - 1) * 60); }

  nextType() {
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
    const type = this.nextType();
    const cells = SHAPES[type].map(row => [...row]);
    this.active = { type, cells, x: Math.floor((WIDTH - cells.length) / 2), y: 0 };
    if (!this.fits(this.active)) this.gameOver = true;
  }

  fits({ cells, x, y }) {
    return cells.every((row, dy) => row.every((cell, dx) => {
      if (!cell) return true;
      const bx = x + dx, by = y + dy;
      return bx >= 0 && bx < WIDTH && by >= 0 && by < HEIGHT && !this.board[by][bx];
    }));
  }

  move(dx) {
    if (this.gameOver) return false;
    const candidate = { ...this.active, x: this.active.x + dx };
    if (!this.fits(candidate)) return false;
    this.active = candidate;
    return true;
  }

  rotate() {
    if (this.gameOver) return false;
    const cells = this.active.cells[0].map((_, x) =>
      this.active.cells.map(row => row[x]).reverse());
    // Small horizontal wall kicks allow rotation beside walls and stacks.
    for (const dx of [0, -1, 1, -2, 2]) {
      const candidate = { ...this.active, cells, x: this.active.x + dx };
      if (this.fits(candidate)) {
        this.active = candidate;
        return true;
      }
    }
    return false;
  }

  tick({ softDrop = false } = {}) {
    if (this.gameOver) return false;
    const candidate = { ...this.active, y: this.active.y + 1 };
    if (this.fits(candidate)) {
      this.active = candidate;
      if (softDrop) this.score++;
      return true;
    }
    this.lock();
    return false;
  }

  hardDrop() {
    if (this.gameOver) return 0;
    let distance = 0;
    while (this.fits({ ...this.active, y: this.active.y + 1 })) {
      this.active.y++;
      distance++;
    }
    this.score += distance * 2;
    this.lock();
    return distance;
  }

  lock() {
    if (this.gameOver) return;
    this.active.cells.forEach((row, dy) => row.forEach((cell, dx) => {
      if (cell) this.board[this.active.y + dy][this.active.x + dx] = this.active.type;
    }));
    this.clearLines();
    this.spawn();
  }

  clearLines() {
    const remaining = this.board.filter(row => row.some(cell => !cell));
    const count = HEIGHT - remaining.length;
    this.score += ([0, 100, 300, 500, 800][count] ?? count * 200) * this.level;
    this.lines += count;
    this.board = [
      ...Array.from({ length: count }, () => Array(WIDTH).fill(null)),
      ...remaining,
    ];
    return count;
  }

  // Return an independent frame; the renderer cannot mutate engine state.
  frame() {
    const board = this.board.map(row => [...row]);
    if (!this.gameOver) {
      this.active.cells.forEach((row, dy) => row.forEach((cell, dx) => {
        if (cell) board[this.active.y + dy][this.active.x + dx] = this.active.type;
      }));
    }
    return board;
  }
}
