import test from 'node:test';
import assert from 'node:assert/strict';
import { Game, PieceBag, PIECE_TYPES, WIDTH, HEIGHT, createBoard } from '../src/engine.js';

const newGame = () => new Game({ random: () => 0 });
const square = (x, y) => ({ type: 'O', rotation: 0, x, y });

test('board is an independent, empty 10-by-20 grid', () => {
  const board = createBoard();
  assert.equal(WIDTH, 10);
  assert.equal(HEIGHT, 20);
  assert.equal(board.length, 20);
  assert.ok(board.every(row => row.length === 10 && row.every(cell => cell === null)));
  board[0][0] = 'T';
  assert.equal(board[1][0], null);
  assert.equal(createBoard()[0][0], null);
});

test('injected randomness produces reproducible complete seven-piece bags', () => {
  const a = new PieceBag(() => 0);
  const b = new PieceBag(() => 0);
  for (let bag = 0; bag < 3; bag++) {
    const draws = Array.from({ length: 7 }, () => a.next());
    assert.deepEqual(draws, Array.from({ length: 7 }, () => b.next()));
    assert.deepEqual([...draws].sort(), [...PIECE_TYPES].sort());
  }
});

test('every tetromino spawns within the board with four cells', () => {
  for (const type of PIECE_TYPES) {
    const game = newGame();
    game.active = null;
    game.nextType = type;
    assert.equal(game.spawn(), true);
    assert.equal(game.active.type, type);
    assert.equal(game.active.rotation, 0);
    assert.equal(game.cells().length, 4);
    assert.equal(game.canPlace(game.active), true);
  }
});

test('placement rejects all four boundaries and occupied cells', () => {
  const game = newGame();
  assert.equal(game.canPlace(square(0, 0)), true);
  assert.equal(game.canPlace(square(8, 18)), true);
  for (const piece of [square(-1, 0), square(9, 0), square(0, -1), square(0, 19)]) {
    assert.equal(game.canPlace(piece), false);
  }
  game.board[5][5] = 'J';
  assert.equal(game.canPlace(square(4, 4)), false);
  assert.equal(game.canPlace(square(2, 4)), true);
});

test('movement stops at walls and settled blocks without changing state', () => {
  const game = newGame();
  game.active = square(0, 5);
  assert.equal(game.move(-1), false);
  assert.deepEqual(game.active, square(0, 5));
  assert.equal(game.move(1), true);
  assert.deepEqual(game.active, square(1, 5));
  game.board[5][3] = 'Z';
  assert.equal(game.move(1), false);
  assert.deepEqual(game.active, square(1, 5));
  game.active = square(8, 5);
  assert.equal(game.move(1), false);
  assert.deepEqual(game.active, square(8, 5));
});

test('gravity moves one row, then locks on the floor and spawns', () => {
  const game = newGame();
  game.active = square(4, 17);
  const nextType = game.nextType;
  assert.equal(game.lock(), false);
  assert.equal(game.tick(), true);
  assert.deepEqual(game.active, square(4, 18));
  assert.equal(game.tick(), false);
  for (const y of [18, 19]) {
    for (const x of [4, 5]) assert.equal(game.board[y][x], 'O');
  }
  assert.equal(game.board.flat().filter(Boolean).length, 4);
  assert.equal(game.active.type, nextType);
  assert.equal(game.active.y, 0);
  assert.equal(game.score, 0);
});

test('gravity locks on a stack without overwriting it', () => {
  const game = newGame();
  game.active = square(4, 16);
  game.board[18][4] = 'J';
  assert.equal(game.tick(), false);
  assert.equal(game.board[18][4], 'J');
  for (const { x, y } of game.cells(square(4, 16))) assert.equal(game.board[y][x], 'O');
});

test('soft and hard drop award points only for rows traveled', () => {
  const game = newGame();
  game.active = square(4, 0);
  assert.equal(game.softDrop(), true);
  assert.equal(game.score, 1);
  assert.equal(game.hardDrop(), 17);
  assert.equal(game.score, 35);
  assert.equal(game.board[19][4], 'O');
  game.active = square(0, 18);
  assert.equal(game.softDrop(), false);
  assert.equal(game.score, 35);
});

for (const [count, points] of [[1, 100], [2, 300], [3, 500], [4, 800]]) {
  test(`clearing ${count} lines compacts the board and awards ${points} points`, () => {
    const game = newGame();
    game.active = { type: 'I', rotation: 1, x: 2, y: 16 };
    game.board[10][0] = 'T';
    for (let y = HEIGHT - count; y < HEIGHT; y++) {
      game.board[y].fill('J');
      game.board[y][4] = null;
    }
    assert.equal(game.canPlace(game.active), true);
    assert.equal(game.lock(), true);
    assert.equal(game.lines, count);
    assert.equal(game.score, points);
    assert.equal(game.board.length, HEIGHT);
    assert.ok(game.board.every(row => row.length === WIDTH));
    assert.ok(game.board.slice(0, count).every(row => row.every(cell => cell === null)));
    assert.equal(game.board[10 + count][0], 'T');
    assert.equal(game.board.flat().filter(Boolean).length, 5 - count);
  });
}

test('line scoring uses the pre-clear level and gravity accelerates with level', () => {
  const game = newGame();
  game.lines = 9;
  game.active = { type: 'I', rotation: 1, x: 2, y: 16 };
  game.board[19].fill('J');
  game.board[19][4] = null;
  assert.equal(game.gravityIntervalMs, 1000);
  assert.equal(game.lock(), true);
  assert.equal(game.score, 100);
  assert.equal(game.lines, 10);
  assert.equal(game.level, 2);
  assert.equal(game.gravityIntervalMs, 800);
  game.active = { type: 'I', rotation: 1, x: 2, y: 16 };
  game.board = createBoard();
  game.board[19].fill('J');
  game.board[19][4] = null;
  assert.equal(game.lock(), true);
  assert.equal(game.score, 300);
});

test('rotation is reversible and rejects walls, floor, and stack without mutation', () => {
  const game = newGame();
  game.active = { type: 'T', rotation: 0, x: 3, y: 5 };
  const original = { ...game.active };
  assert.equal(game.rotate(), true);
  assert.equal(game.active.rotation, 1);
  assert.equal(game.rotate(-1), true);
  assert.deepEqual(game.active, original);
  const rejected = [
    { type: 'I', rotation: 1, x: -2, y: 5 },
    { type: 'I', rotation: 1, x: 7, y: 5 },
    { type: 'I', rotation: 0, x: 3, y: 18 },
    original,
  ];
  game.board[7][4] = 'Z'; // Hits only the rotated T, not its initial orientation.
  for (const piece of rejected) {
    game.active = { ...piece };
    assert.equal(game.canPlace(game.active), true);
    const before = structuredClone({ active: game.active, board: game.board });
    assert.equal(game.rotate(), false);
    assert.deepEqual({ active: game.active, board: game.board }, before);
  }
});

test('blocked spawn ends the game; actions stop and restart resets state', () => {
  const game = newGame();
  game.active = square(0, 18);
  game.nextType = 'O';
  game.board[0][4] = 'T';
  assert.equal(game.tick(), false);
  assert.equal(game.gameOver, true);
  assert.equal(game.active, null);
  const snapshot = () => JSON.parse(JSON.stringify(game));
  const before = snapshot();
  assert.equal(game.spawn(), false);
  assert.equal(game.move(1), false);
  assert.equal(game.rotate(), false);
  assert.equal(game.tick(), false);
  assert.equal(game.softDrop(), false);
  assert.equal(game.hardDrop(), 0);
  assert.equal(game.lock(), false);
  assert.deepEqual(snapshot(), before);
  game.restart();
  assert.equal(game.gameOver, false);
  assert.equal(game.score, 0);
  assert.equal(game.lines, 0);
  assert.ok(game.active);
  assert.equal(game.canPlace(game.active), true);
  assert.ok(game.board.flat().every(cell => cell === null));
});
