import test from 'node:test';
import assert from 'node:assert/strict';
import { Game, PieceBag, SHAPES, rotateMatrix } from '../src/game.js';

function setPiece(game, type, x, y) {
  game.active = {
    type, x, y,
    matrix: SHAPES[type].map(row => [...row].map(cell => cell === '.' ? null : cell)),
  };
}

test('each seven-bag contains all tetrominoes', () => {
  const bag = new PieceBag(() => 0.5);
  for (let i = 0; i < 3; i++) {
    assert.deepEqual(Array.from({ length: 7 }, () => bag.next()).sort(), Object.keys(SHAPES).sort());
  }
});

test('initial board and preview are ready for play', () => {
  const game = new Game();
  assert.equal(game.board.length, 20);
  assert.ok(game.board.every(row => row.length === 10 && row.every(cell => cell === null)));
  assert.equal(game.cells().length, 4);
  assert.ok(SHAPES[game.nextType]);
  assert.equal(game.level, 1);
  assert.equal(game.gravityInterval, 1000);
});

test('movement rejects walls, floor, and settled blocks without changing state', () => {
  const game = new Game();
  setPiece(game, 'O', 0, 18);
  const original = game.active;
  assert.equal(game.move(-1), false);
  assert.equal(game.move(0, 1), false);
  game.board[18][2] = 'T';
  assert.equal(game.move(1), false);
  assert.equal(game.active, original);
  assert.equal(game.move(0, -1), true);
});

test('rotation is reversible and returns to the original after four turns', () => {
  for (const shape of Object.values(SHAPES)) {
    const matrix = shape.map(row => [...row]);
    assert.deepEqual(rotateMatrix(rotateMatrix(matrix), false), matrix);
    let rotated = matrix;
    for (let i = 0; i < 4; i++) rotated = rotateMatrix(rotated);
    assert.deepEqual(rotated, matrix);
  }
});

test('rotation kicks away from a wall and floor', () => {
  const game = new Game();
  setPiece(game, 'I', -1, 5);
  game.active.matrix = rotateMatrix(game.active.matrix);
  assert.equal(game.rotate(), true);
  assert.equal(game.collides(game.active), false);
  setPiece(game, 'I', 3, 18);
  assert.equal(game.rotate(), true);
  assert.equal(game.collides(game.active), false);
});

test('blocked rotation leaves the piece unchanged', () => {
  const game = new Game();
  game.board = game.board.map(row => row.map(() => 'J'));
  setPiece(game, 'T', 3, 5);
  for (const { x, y } of game.cells()) game.board[y][x] = null;
  const original = game.active;
  assert.equal(game.rotate(), false);
  assert.equal(game.active, original);
});

test('gravity locks at the floor and spawns another piece without drop points', () => {
  const game = new Game();
  setPiece(game, 'O', 0, 17);
  assert.equal(game.tick(), true);
  assert.equal(game.tick(), false);
  assert.equal(game.board[19][0], 'O');
  assert.equal(game.board[18][1], 'O');
  assert.equal(game.score, 0);
  assert.equal(game.active.y, 0);
});

test('soft and hard drops award points and hard drop locks immediately', () => {
  const game = new Game();
  setPiece(game, 'O', 0, 0);
  assert.equal(game.softDrop(), true);
  assert.equal(game.score, 1);
  assert.equal(game.hardDrop(), 17);
  assert.equal(game.score, 35);
  assert.equal(game.board[19][0], 'O');
});

test('locking clears multiple lines, preserves other rows, and scores at the old level', () => {
  const game = new Game({ width: 4, height: 6 });
  game.lines = 9;
  game.board[3][0] = 'T';
  game.board[4] = ['J', 'J', null, null];
  game.board[5] = ['J', 'J', null, null];
  setPiece(game, 'O', 2, 4);
  game.lock();
  assert.equal(game.score, 300);
  assert.equal(game.lines, 11);
  assert.equal(game.level, 2);
  assert.equal(game.gravityInterval, 800);
  assert.equal(game.board[5][0], 'T');
  assert.ok(game.board.slice(0, 5).every(row => row.every(cell => cell === null)));
});

test('four-line clear awards 800 points per level', () => {
  const game = new Game({ width: 4, height: 8 });
  game.lines = 10;
  for (let y = 4; y < 8; y++) game.board[y] = ['J', 'J', null, 'J'];
  setPiece(game, 'I', 0, 4);
  game.active.matrix = rotateMatrix(game.active.matrix);
  game.lock();
  assert.equal(game.score, 1600);
  assert.equal(game.lines, 14);
  assert.ok(game.board.every(row => row.every(cell => cell === null)));
});

test('blocked spawn ends the game and subsequent actions are inert', () => {
  const game = new Game();
  game.board[0].fill('J');
  game.board[1].fill('J');
  assert.equal(game.spawn(), false);
  assert.equal(game.gameOver, true);
  assert.equal(game.active, null);
  const board = structuredClone(game.board);
  assert.equal(game.move(1), false);
  assert.equal(game.rotate(), false);
  assert.equal(game.tick(), false);
  assert.equal(game.softDrop(), false);
  assert.equal(game.hardDrop(), 0);
  assert.deepEqual(game.board, board);
  assert.equal(game.score, 0);
});

test('locking above the board causes top-out without partial placement', () => {
  const game = new Game();
  setPiece(game, 'O', 0, -1);
  assert.equal(game.collides(game.active), false);
  game.lock();
  assert.equal(game.gameOver, true);
  assert.equal(game.active, null);
  assert.ok(game.board.every(row => row.every(cell => cell === null)));
});
