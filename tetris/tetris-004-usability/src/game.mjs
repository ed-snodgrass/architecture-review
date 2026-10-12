export const WIDTH = 10;
export const HEIGHT = 20;

// Square rotation frames preserve each tetromino's pivot.
const SHAPES = {
  I: ['....', 'IIII', '....', '....'],
  J: ['J..', 'JJJ', '...'],
  L: ['..L', 'LLL', '...'],
  O: ['OO', 'OO'],
  S: ['.SS', 'SS.', '...'],
  T: ['.T.', 'TTT', '...'],
  Z: ['ZZ.', '.ZZ', '...'],
};
export const PIECES = Object.keys(SHAPES);

export function cells(piece) {
  return piece.shape.flatMap((row, y) => [...row].flatMap((cell, x) =>
    cell === '.' ? [] : [{ x: piece.x + x, y: piece.y + y, type: cell }]));
}

export function createBag(random = Math.random) {
  let bag = [];
  return () => {
    if (!bag.length) {
      bag = [...PIECES];
      for (let i = bag.length - 1; i > 0; i--) {
        const j = Math.floor(random() * (i + 1));
        [bag[i], bag[j]] = [bag[j], bag[i]];
      }
    }
    return bag.pop();
  };
}

export class Game {
  constructor({ nextPiece = createBag() } = {}) {
    this.board = Array.from({ length: HEIGHT }, () => Array(WIDTH).fill(null));
    this.score = 0;
    this.lines = 0;
    this.gameOver = false;
    this.nextPiece = nextPiece;
    this.spawn();
  }

  get level() { return 1 + Math.floor(this.lines / 10); }
  get fallInterval() { return Math.max(80, 800 - (this.level - 1) * 60); }

  spawn() {
    const type = this.nextPiece();
    if (!Object.hasOwn(SHAPES, type)) throw new Error(`Unknown piece: ${type}`);
    const shape = [...SHAPES[type]];
    this.active = { type, shape, x: Math.floor((WIDTH - shape.length) / 2), y: 0 };
    if (!this.fits(this.active)) {
      this.gameOver = true;
      this.active = null;
    }
  }

  fits(piece) {
    return cells(piece).every(({ x, y }) =>
      x >= 0 && x < WIDTH && y >= 0 && y < HEIGHT && !this.board[y][x]);
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
    if (this.active.type === 'O') return true;
    const { shape } = this.active;
    const rotated = shape.map((_, y) => shape.map(row => row[y]).reverse().join(''));
    // Simple kicks, not SRS: try in place, then 1/2 cells sideways, then up.
    for (const [dx, dy] of [[0, 0], [-1, 0], [1, 0], [-2, 0], [2, 0], [0, -1], [0, -2]]) {
      const candidate = { ...this.active, shape: rotated, x: this.active.x + dx, y: this.active.y + dy };
      if (this.fits(candidate)) {
        this.active = candidate;
        return true;
      }
    }
    return false;
  }

  step(softDrop = false) {
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
    // Guard against writing outside the board even if a caller corrupts state.
    if (!this.fits(this.active)) {
      this.gameOver = true;
      this.active = null;
      return;
    }
    for (const { x, y, type } of cells(this.active)) this.board[y][x] = type;
    const remaining = this.board.filter(row => row.some(cell => cell === null));
    const cleared = HEIGHT - remaining.length;
    this.score += [0, 100, 300, 500, 800][cleared] * this.level;
    this.lines += cleared;
    this.board = [
      ...Array.from({ length: cleared }, () => Array(WIDTH).fill(null)),
      ...remaining,
    ];
    this.spawn();
  }
}
