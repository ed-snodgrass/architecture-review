import test from 'node:test';
import assert from 'node:assert/strict';
import { Tetris, SHAPES } from '../src/engine.js';

const create = () => new Tetris({ random: () => 0.5 });
const piece = (game, type, x, y) => {
  game.active = { type, x, y, matrix: SHAPES[type].map(row => [...row]) };
};

test('seven-bag contains each tetromino and fresh boards are independent', () => {
  const game = create();
  const types = [game.active.type, game.next];
  for (let i = 0; i < 5; i++) types.push(game.drawType());
  assert.deepEqual(types.sort(), Object.keys(SHAPES).sort());
  for (const shape of Object.values(SHAPES)) {
    assert.equal(shape.flat().reduce((a, b) => a + b), 4);
  }
  game.board[0][0] = 'T';
  assert.equal(game.board[1][0], null);
  assert.equal(create().board[0][0], null);
  assert.throws(() => new Tetris({ width: 3 }), RangeError);
});

test('movement respects walls, floor and settled blocks', () => {
  const game = create();
  piece(game, 'O', 0, 0);
  assert.equal(game.move(-1), false);
  assert.equal(game.move(1), true);
  game.board[0][3] = 'I';
  assert.equal(game.move(1), false);
  piece(game, 'O', 8, 18);
  assert.equal(game.move(1), false);
  assert.equal(game.move(0, 1), false);
});

test('rotation is reversible and kicks away from walls', () => {
  const game = create();
  piece(game, 'T', 3, 3);
  const original = structuredClone(game.active);
  assert.equal(game.rotate(), true);
  assert.equal(game.rotate(-1), true);
  assert.deepEqual(game.active, original);
  piece(game, 'I', 0, 4);
  game.rotate();
  assert.equal(game.move(-2), true);
  assert.equal(game.rotate(), true);
  assert.equal(game.canPlace(game.active), true);
});

test('gravity locks and spawns; drops award points', () => {
  const game = create();
  piece(game, 'O', 0, 0);
  game.tick();
  assert.equal(game.active.y, 1);
  assert.equal(game.score, 0);
  game.softDrop();
  assert.equal(game.score, 1);
  assert.equal(game.hardDrop(), 16);
  assert.equal(game.score, 33);
  assert.equal(game.board[19][0], 'O');
  assert.ok(game.active);
  piece(game, 'O', 4, 18);
  game.tick();
  assert.equal(game.board[19][4], 'O');
  piece(game, 'O', 6, 18);
  game.softDrop();
  assert.equal(game.board[19][6], 'O');
});

test('clears one through four lines with score and level progression', () => {
  for (const [count, points] of [[1, 100], [2, 300], [3, 500], [4, 800]]) {
    const game = create();
    game.lines = 10;
    game.board[0][0] = 'T';
    for (let y = 20 - count; y < 20; y++) game.board[y].fill('I');
    assert.equal(game.clearLines(), count);
    assert.equal(game.score, points * 2);
    assert.equal(game.lines, 10 + count);
    assert.equal(game.board[count][0], 'T');
    assert.equal(game.board.length, 20);
    assert.ok(game.board[0].every(cell => cell === null));
  }
  const game = create();
  game.lines = 9;
  game.board[19].fill('I');
  game.clearLines();
  assert.equal(game.level, 2);
  assert.equal(game.gravityMs, 740);
  game.lines = 1000;
  assert.equal(game.gravityMs, 80);
});

test('blocked spawn ends play and restart resets all state', () => {
  const game = create();
  game.board[0].fill('Z');
  game.board[1].fill('Z');
  assert.equal(game.spawn(), false);
  assert.equal(game.gameOver, true);
  const before = structuredClone(game.board);
  assert.equal(game.move(1), false);
  assert.equal(game.rotate(), false);
  assert.equal(game.tick(), false);
  assert.equal(game.softDrop(), false);
  assert.equal(game.hardDrop(), 0);
  assert.deepEqual(game.board, before);
  game.reset();
  assert.equal(game.gameOver, false);
  assert.equal(game.score, 0);
  assert.equal(game.lines, 0);
  assert.ok(game.board.flat().every(cell => cell === null));
  assert.ok(game.active);
});

test('locking above the board ends play and visibleBoard is a copy', () => {
  const game = create();
  const visible = game.visibleBoard();
  assert.equal(visible.flat().filter(Boolean).length, 4);
  visible[19][0] = 'Z';
  assert.equal(game.board[19][0], null);
  piece(game, 'O', 0, -1);
  game.lock();
  assert.equal(game.gameOver, true);
});
