// Pure gameplay state: terminal input, rendering, and timers belong to the UI.
export const SHAPES = Object.freeze({
  I: ['....', 'IIII', '....', '....'],
  J: ['J..', 'JJJ', '...'],
  L: ['..L', 'LLL', '...'],
  O: ['OO', 'OO'],
  S: ['.SS', 'SS.', '...'],
  T: ['.T.', 'TTT', '...'],
  Z: ['ZZ.', '.ZZ', '...'],
});

export class PieceBag {
  constructor(random = Math.random) {
    this.random = random;
    this.remaining = [];
  }

  next() {
    if (this.remaining.length === 0) {
      this.remaining = Object.keys(SHAPES);
      for (let i = this.remaining.length - 1; i > 0; i--) {
        const j = Math.floor(this.random() * (i + 1));
        [this.remaining[i], this.remaining[j]] = [this.remaining[j], this.remaining[i]];
      }
    }
    return this.remaining.pop();
  }
}

export function rotateMatrix(matrix, clockwise = true) {
  const size = matrix.length;
  return Array.from({ length: size }, (_, y) =>
    Array.from({ length: size }, (_, x) =>
      clockwise ? matrix[size - 1 - x][y] : matrix[x][size - 1 - y],
    ),
  );
}

export class Game {
  constructor({ width = 10, height = 20, random = Math.random } = {}) {
    if (!Number.isInteger(width) || width < 4 || !Number.isInteger(height) || height < 4) {
      throw new RangeError('Board dimensions must be integers of at least four');
    }
    this.width = width;
    this.height = height;
    this.board = Array.from({ length: height }, () => Array(width).fill(null));
    this.bag = new PieceBag(random);
    this.score = 0;
    this.lines = 0;
    this.gameOver = false;
    this.active = null;
    this.nextType = this.bag.next();
    this.spawn();
  }

  get level() {
    return 1 + Math.floor(this.lines / 10);
  }

  get gravityInterval() {
    return Math.max(100, Math.floor(1000 * 0.8 ** (this.level - 1)));
  }

  spawn() {
    if (this.gameOver) return false;
    const type = this.nextType;
    const matrix = SHAPES[type].map(row => [...row].map(cell => cell === '.' ? null : cell));
    this.nextType = this.bag.next();
    this.active = { type, matrix, x: Math.floor((this.width - matrix.length) / 2), y: 0 };
    if (this.collides(this.active)) {
      this.active = null;
      this.gameOver = true;
      return false;
    }
    return true;
  }

  cells(piece = this.active) {
    if (!piece) return [];
    const cells = [];
    piece.matrix.forEach((row, y) => row.forEach((type, x) => {
      if (type) cells.push({ x: piece.x + x, y: piece.y + y, type });
    }));
    return cells;
  }

  collides(piece) {
    return this.cells(piece).some(({ x, y }) =>
      x < 0 || x >= this.width || y >= this.height ||
      (y >= 0 && this.board[y][x] !== null),
    );
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
    if (this.active.type === 'O') return true;
    const matrix = rotateMatrix(this.active.matrix, clockwise);
    // Simple wall/floor kicks, not the full SRS rotation system.
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
      this.score += 1;
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
    const cells = this.cells();
    if (cells.some(({ y }) => y < 0)) {
      this.gameOver = true;
      this.active = null;
      return;
    }
    for (const { x, y, type } of cells) this.board[y][x] = type;
    this.active = null;
    this.clearLines();
    this.spawn();
  }

  clearLines() {
    const remaining = this.board.filter(row => row.some(cell => cell === null));
    const count = this.height - remaining.length;
    if (count === 0) return 0;
    // Score at the level before the clear; the next piece uses the new level.
    this.score += [0, 100, 300, 500, 800][count] * this.level;
    this.lines += count;
    this.board = [
      ...Array.from({ length: count }, () => Array(this.width).fill(null)),
      ...remaining,
    ];
    return count;
  }
}
