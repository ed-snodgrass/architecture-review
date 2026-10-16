export const WIDTH = 10;
export const HEIGHT = 20;

// Square matrices rotate around their centers; the O piece stays unchanged.
const shapes = {
  I: [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
  J: [[1, 0, 0], [1, 1, 1], [0, 0, 0]],
  L: [[0, 0, 1], [1, 1, 1], [0, 0, 0]],
  O: [[1, 1], [1, 1]],
  S: [[0, 1, 1], [1, 1, 0], [0, 0, 0]],
  T: [[0, 1, 0], [1, 1, 1], [0, 0, 0]],
  Z: [[1, 1, 0], [0, 1, 1], [0, 0, 0]],
};

function clockwise(matrix) {
  return matrix[0].map((_, x) => matrix.map(row => row[x]).reverse());
}

export const TETROMINOES = Object.freeze(Object.fromEntries(
  Object.entries(shapes).map(([type, initial]) => {
    const rotations = [initial];
    for (let i = 1; i < 4; i++) rotations.push(clockwise(rotations[i - 1]));
    return [type, Object.freeze(rotations.map(matrix =>
      Object.freeze(matrix.map(row => Object.freeze(row))),
    ))];
  }),
));
export const PIECE_TYPES = Object.freeze(Object.keys(TETROMINOES));

export function createBoard() {
  return Array.from({ length: HEIGHT }, () => Array(WIDTH).fill(null));
}

/** A shuffled seven-bag. Inject random() returning [0, 1) for reproducibility. */
export class PieceBag {
  constructor(random = Math.random) {
    this.random = random;
    this.pieces = [];
  }

  next() {
    if (this.pieces.length === 0) {
      this.pieces = [...PIECE_TYPES];
      for (let i = this.pieces.length - 1; i > 0; i--) {
        const value = this.random();
        if (!Number.isFinite(value) || value < 0 || value >= 1) {
          throw new RangeError('random() must return a number in [0, 1)');
        }
        const j = Math.floor(value * (i + 1));
        [this.pieces[i], this.pieces[j]] = [this.pieces[j], this.pieces[i]];
      }
    }
    return this.pieces.pop();
  }
}

/**
 * No timers or terminal I/O: call tick() at gravityIntervalMs intervals.
 * Board cells are null or piece letters. active and nextType support rendering.
 * Rotation uses fixed centers without wall kicks; blocked actions change nothing.
 */
export class Game {
  constructor({ random = Math.random } = {}) {
    this.random = random;
    this.restart();
  }

  restart() {
    this.board = createBoard();
    this.score = 0;
    this.lines = 0;
    this.gameOver = false;
    this.active = null;
    this.bag = new PieceBag(this.random);
    this.nextType = this.bag.next();
    this.spawn();
  }

  get level() {
    return 1 + Math.floor(this.lines / 10);
  }

  get gravityIntervalMs() {
    return Math.max(80, Math.round(1000 * 0.8 ** (this.level - 1)));
  }

  /** Occupied coordinates for a piece (defaults to the active piece). */
  cells(piece = this.active) {
    if (!piece) return [];
    const matrix = TETROMINOES[piece.type][piece.rotation];
    return matrix.flatMap((row, y) => row.flatMap((filled, x) =>
      filled ? [{ x: piece.x + x, y: piece.y + y }] : [],
    ));
  }

  canPlace(piece) {
    return this.cells(piece).every(({ x, y }) =>
      x >= 0 && x < WIDTH && y >= 0 && y < HEIGHT && this.board[y][x] === null,
    );
  }

  spawn() {
    if (this.gameOver || this.active) return false;
    const type = this.nextType;
    const size = TETROMINOES[type][0].length;
    const piece = { type, rotation: 0, x: Math.floor((WIDTH - size) / 2), y: 0 };
    if (!this.canPlace(piece)) {
      this.gameOver = true;
      return false;
    }
    this.active = piece;
    this.nextType = this.bag.next();
    return true;
  }

  // Moves at most one column to avoid skipping over occupied cells.
  move(direction) {
    if (direction !== -1 && direction !== 1) return false;
    return this.tryTransform({ x: this.active?.x + direction });
  }

  rotate(direction = 1) {
    if (direction !== -1 && direction !== 1) return false;
    return this.tryTransform({ rotation: (this.active?.rotation + direction + 4) % 4 });
  }

  tryTransform(changes) {
    if (this.gameOver || !this.active) return false;
    const candidate = { ...this.active, ...changes };
    if (!this.canPlace(candidate)) return false;
    this.active = candidate;
    return true;
  }

  /** Advance one gravity step. A blocked step locks and spawns immediately. */
  tick() {
    if (this.gameOver || !this.active) return false;
    if (this.tryTransform({ y: this.active.y + 1 })) return true;
    this.lock();
    return false;
  }

  softDrop() {
    const moved = this.tick();
    if (moved) this.score++;
    return moved;
  }

  /** Drop and lock, awarding two points per row; returns the distance. */
  hardDrop() {
    if (this.gameOver || !this.active) return 0;
    let distance = 0;
    while (this.tryTransform({ y: this.active.y + 1 })) distance++;
    this.score += distance * 2;
    this.lock();
    return distance;
  }

  /** Lock only when grounded; calling this on a falling piece is a no-op. */
  lock() {
    if (this.gameOver || !this.active) return false;
    if (this.canPlace({ ...this.active, y: this.active.y + 1 })) return false;
    for (const { x, y } of this.cells()) this.board[y][x] = this.active.type;
    this.active = null;
    const remaining = this.board.filter(row => row.some(cell => cell === null));
    const cleared = HEIGHT - remaining.length;
    // Score uses the level before these lines are added.
    this.score += [0, 100, 300, 500, 800][cleared] * this.level;
    this.lines += cleared;
    this.board = [
      ...Array.from({ length: cleared }, () => Array(WIDTH).fill(null)),
      ...remaining,
    ];
    this.spawn();
    return true;
  }
}
