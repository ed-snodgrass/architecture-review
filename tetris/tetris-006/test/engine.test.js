import test from 'node:test';
import assert from 'node:assert/strict';
import { Game, WIDTH, HEIGHT, PIECE_TYPES, createBag } from '../src/engine.js';

const gameWith = (type = 'T') => new Game({ nextPiece: () => type });
const occupied = board => board.flat().filter(Boolean).length;

function lineFixture(count) {
  const game = gameWith('I');
  game.rotate();
  // Vertical I occupies column 5, rows 0..3 at spawn.
  for (let y = HEIGHT - count; y < HEIGHT; y++) {
    game.board[y].fill('J');
    game.board[y][5] = null;
  }
  game.active.y = HEIGHT - 4;
  return game;
}

test('creates a separate 10 by 20 board and spawns all seven tetrominoes', () => {
  assert.equal(PIECE_TYPES.length, 7);
  for (const type of PIECE_TYPES) {
    const game = gameWith(type);
    assert.equal(game.board.length, HEIGHT);
    assert.ok(game.board.every(row => row.length === WIDTH && row.every(c => c === null)));
    assert.notEqual(game.board[0], game.board[1]);
    assert.equal(game.active.type, type);
    assert.equal(game.active.matrix.flat().filter(Boolean).length, 4);
    assert.equal(game.active.y, 0);
    assert.equal(game.fits(game.active), true);
    assert.equal(game.score, 0);
    assert.equal(game.gameOver, false);
  }
});

test('seeded seven-bag draws contain every piece once per bag', () => {
  const draw = createBag(() => 0.25);
  for (let bag = 0; bag < 3; bag++) {
    assert.deepEqual(Array.from({ length: 7 }, draw).sort(), [...PIECE_TYPES].sort());
  }
});

test('rejects unknown piece types', () => {
  assert.throws(() => gameWith('unknown'), /Invalid tetromino/);
});

test('horizontal motion stops at both boundaries without mutating on failure', () => {
  const game = gameWith('O');
  while (game.move(-1)) { /* reach left wall */ }
  assert.equal(game.active.x, 0);
  const left = structuredClone(game.active);
  assert.equal(game.move(-1), false);
  assert.deepEqual(game.active, left);
  while (game.move(1)) { /* reach right wall */ }
  assert.equal(game.active.x, WIDTH - 2);
  assert.equal(game.move(1), false);
  assert.equal(game.move(0), false);
});

test('movement rejects settled blocks; empty matrix cells do not collide', () => {
  const game = gameWith('T');
  game.board[0][game.active.x] = 'J'; // Empty corner of the T.
  assert.equal(game.fits(game.active), true);
  game.board[1][game.active.x + 3] = 'J';
  const before = structuredClone(game.active);
  assert.equal(game.move(1), false);
  assert.deepEqual(game.active, before);
  assert.equal(game.fits({ ...game.active, y: -2 }), false);
  assert.equal(game.fits({ ...game.active, y: HEIGHT }), false);
});

test('rotation cycles through four orientations and inverse rotation restores shape', () => {
  for (const type of PIECE_TYPES) {
    const game = gameWith(type);
    const before = structuredClone(game.active);
    for (let i = 0; i < 4; i++) assert.equal(game.rotate(), true);
    assert.deepEqual(game.active, before);
    game.rotate();
    game.rotate(-1);
    assert.deepEqual(game.active, before);
  }
});

test('rotation kicks a vertical I away from the right wall', () => {
  const game = gameWith('I');
  game.rotate();
  while (game.move(1)) { /* reach right wall */ }
  assert.equal(game.active.x, 7);
  assert.equal(game.rotate(), true);
  assert.equal(game.active.x, 6);
  assert.equal(game.fits(game.active), true);
});

test('rotation blocked by the floor or settled blocks leaves state unchanged', () => {
  const game = gameWith('I');
  game.active.y = HEIGHT - 2;
  const before = structuredClone(game.active);
  assert.equal(game.rotate(), false);
  assert.deepEqual(game.active, before);

  const blocked = gameWith('T');
  // Fill every cell except those occupied by the current piece.
  blocked.board = blocked.board.map(row => row.map(() => 'J'));
  blocked.active.matrix.forEach((row, dy) => row.forEach((cell, dx) => {
    if (cell) blocked.board[dy][blocked.active.x + dx] = null;
  }));
  const original = structuredClone(blocked.active);
  assert.equal(blocked.rotate(), false);
  assert.deepEqual(blocked.active, original);
});

test('gravity descends without points then locks at the floor and spawns', () => {
  const game = gameWith('O');
  for (let i = 0; i < HEIGHT - 2; i++) assert.equal(game.tick(), true);
  assert.equal(occupied(game.board), 0);
  assert.equal(game.tick(), false);
  assert.equal(occupied(game.board), 4);
  assert.deepEqual(game.board[19].slice(4, 6), ['O', 'O']);
  assert.equal(game.active.y, 0);
  assert.equal(game.score, 0);
});

test('soft drop awards only traveled rows, including no points on locking', () => {
  const game = gameWith('O');
  assert.equal(game.softDrop(), true);
  assert.equal(game.score, 1);
  game.active.y = HEIGHT - 2;
  assert.equal(game.softDrop(), false);
  assert.equal(game.score, 1);
});

test('hard drop stops on stacked blocks, locks and awards two points per row', () => {
  const game = gameWith('O');
  game.board[18][4] = 'J';
  assert.equal(game.hardDrop(), 16);
  assert.equal(game.score, 32);
  assert.equal(occupied(game.board), 5);
  assert.equal(game.board[17][4], 'O');
  assert.equal(game.board[18][4], 'J');
  assert.equal(game.active.y, 0);
});

test('one through four simultaneous line clears use the scoring table', () => {
  for (const [count, points] of [[1, 100], [2, 300], [3, 500], [4, 800]]) {
    const game = lineFixture(count);
    assert.equal(game.hardDrop(), 0);
    assert.equal(game.lines, count);
    assert.equal(game.score, points);
    assert.equal(game.board.length, HEIGHT);
    assert.equal(occupied(game.board), 4 - count);
    assert.ok(game.board.slice(0, count).every(row => row.every(c => c === null)));
  }
});

test('line clears shift surviving rows down, without aliasing empty rows', () => {
  const game = lineFixture(2);
  game.board[10][0] = 'Z';
  game.hardDrop();
  assert.equal(game.board[12][0], 'Z');
  assert.equal(game.board[10][0], null);
  game.board[0][0] = 'T';
  assert.equal(game.board[1][0], null);
});

test('line scoring uses the old level before advancing at ten lines', () => {
  const game = lineFixture(1);
  game.lines = 9;
  game.hardDrop();
  assert.equal(game.score, 100);
  assert.equal(game.lines, 10);
  assert.equal(game.level, 2);

  const higher = lineFixture(4);
  higher.lines = 10;
  higher.hardDrop();
  assert.equal(higher.score, 1600);
});

test('blocked spawn ends game; further inputs are inert; reset starts fresh', () => {
  const game = gameWith('O');
  game.board[0][4] = 'J';
  game.active.y = HEIGHT - 2;
  game.tick();
  assert.equal(game.gameOver, true);
  assert.equal(game.active, null);
  const before = structuredClone(game.board);
  assert.equal(game.tick(), false);
  assert.equal(game.move(1), false);
  assert.equal(game.rotate(), false);
  assert.equal(game.softDrop(), false);
  assert.equal(game.hardDrop(), 0);
  assert.deepEqual(game.board, before);
  assert.equal(game.score, 0);
  game.reset();
  assert.equal(game.gameOver, false);
  assert.equal(game.active.type, 'O');
  assert.equal(occupied(game.board), 0);
  assert.equal(game.lines, 0);
  assert.equal(game.score, 0);
});

test('a completed top row is cleared before checking the next spawn', () => {
  const game = gameWith('O');
  game.active.y = HEIGHT - 2;
  game.board[0].fill('J');
  game.tick();
  assert.equal(game.lines, 1);
  assert.equal(game.gameOver, false);
  assert.equal(game.active.type, 'O');
});
