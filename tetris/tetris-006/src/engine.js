export const WIDTH = 10;
export const HEIGHT = 20;

// Square matrices keep a piece's rotation origin stable.
const SHAPES = {
  I: ['0000', '1111', '0000', '0000'],
  J: ['100', '111', '000'],
  L: ['001', '111', '000'],
  O: ['11', '11'],
  S: ['011', '110', '000'],
  T: ['010', '111', '000'],
  Z: ['110', '011', '000'],
};
export const PIECE_TYPES = Object.freeze(Object.keys(SHAPES));

/** Each group of seven draws contains every tetromino exactly once. */
export function createBag(random = Math.random) {
  let bag = [];
  return () => {
    if (bag.length === 0) {
      bag = [...PIECE_TYPES];
      for (let i = bag.length - 1; i > 0; i--) {
        const j = Math.floor(random() * (i + 1));
        [bag[i], bag[j]] = [bag[j], bag[i]];
      }
    }
    return bag.pop();
  };
}

/** Pure game state: no timers, terminal access, or I/O.
 * Board cells are null or a piece type. Active coordinates are board-relative.
 * nextPiece can be injected for deterministic simulations.
 */
export class Game {
  constructor({ nextPiece = createBag() } = {}) {
    this.nextPiece = nextPiece;
    this.reset();
  }

  reset() {
    this.board = Array.from({ length: HEIGHT }, () => Array(WIDTH).fill(null));
    this.score = 0;
    this.lines = 0;
    this.gameOver = false;
    this.active = null;
    this.spawn();
  }

  get level() {
    return Math.floor(this.lines / 10) + 1;
  }

  spawn() {
    const type = this.nextPiece();
    if (!Object.hasOwn(SHAPES, type)) {
      throw new Error(`Invalid tetromino type: ${type}`);
    }
    const matrix = SHAPES[type].map(row => [...row].map(Number));
    const piece = { type, matrix, x: Math.floor((WIDTH - matrix.length) / 2), y: 0 };
    if (!this.fits(piece)) {
      this.active = null;
      this.gameOver = true;
      return false;
    }
    this.active = piece;
    return true;
  }

  fits({ matrix, x, y }) {
    return matrix.every((row, dy) => row.every((cell, dx) => {
      if (!cell) return true;
      const bx = x + dx;
      const by = y + dy;
      return bx >= 0 && bx < WIDTH && by >= 0 && by < HEIGHT &&
        this.board[by][bx] === null;
    }));
  }

  /** Attempt one horizontal step; failure does not change state. */
  move(direction) {
    if (this.gameOver || !this.active || ![-1, 1].includes(direction)) return false;
    const candidate = { ...this.active, x: this.active.x + direction };
    if (!this.fits(candidate)) return false;
    this.active = candidate;
    return true;
  }

  /** Rotate clockwise (1) or counterclockwise (-1), with small wall kicks. */
  rotate(direction = 1) {
    if (this.gameOver || !this.active || ![-1, 1].includes(direction)) return false;
    if (this.active.type === 'O') return true;
    const old = this.active.matrix;
    const n = old.length;
    const matrix = old.map((row, y) => row.map((_, x) =>
      direction === 1 ? old[n - 1 - x][y] : old[x][n - 1 - y]));
    for (const offset of [0, -1, 1, -2, 2]) {
      const candidate = { ...this.active, matrix, x: this.active.x + offset };
      if (this.fits(candidate)) {
        this.active = candidate;
        return true;
      }
    }
    return false;
  }

  /** One gravity step. A blocked step locks immediately, then spawns. */
  tick() {
    if (this.gameOver || !this.active) return false;
    const candidate = { ...this.active, y: this.active.y + 1 };
    if (this.fits(candidate)) {
      this.active = candidate;
      return true;
    }
    this.lock();
    return false;
  }

  softDrop() {
    const moved = this.tick();
    if (moved) this.score += 1;
    return moved;
  }

  /** Drop and lock immediately, awarding two points per traveled row. */
  hardDrop() {
    if (this.gameOver || !this.active) return 0;
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
    if (this.gameOver || !this.active) return;
    const { matrix, x, y, type } = this.active;
    matrix.forEach((row, dy) => row.forEach((cell, dx) => {
      if (cell) this.board[y + dy][x + dx] = type;
    }));
    const remaining = this.board.filter(row => row.some(cell => cell === null));
    const cleared = HEIGHT - remaining.length;
    // Score with the level before this clear advances the line count.
    this.score += [0, 100, 300, 500, 800][cleared] * this.level;
    this.lines += cleared;
    this.board = [
      ...Array.from({ length: cleared }, () => Array(WIDTH).fill(null)),
      ...remaining,
    ];
    this.active = null;
    this.spawn();
  }
}
