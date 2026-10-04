import test from 'node:test';
import assert from 'node:assert/strict';
import { Game, SHAPES, WIDTH, HEIGHT } from '../src/engine.js';

const game = () => new Game({ random: () => 0.5 });
const usePiece = (g, type, x = 3, y = 0) => {
  g.active = { type, cells: SHAPES[type].map(row => [...row]), x, y };
};

test('seven tetrominoes each have four blocks and bags contain all seven', () => {
  assert.equal(Object.keys(SHAPES).length, 7);
  for (const shape of Object.values(SHAPES)) {
    assert.equal(shape.flat().filter(Boolean).length, 4);
  }
  const g = game();
  const bag = [g.active.type, ...Array.from({ length: 6 }, () => g.nextType())];
  assert.equal(new Set(bag).size, 7);
  assert.equal(new Set(Array.from({ length: 7 }, () => g.nextType())).size, 7);
});

test('movement respects walls and occupied cells', () => {
  const g = game();
  usePiece(g, 'O', 0);
  assert.equal(g.move(-1), false);
  assert.equal(g.move(1), true);
  g.board[0][3] = 'T';
  assert.equal(g.move(1), false);
  usePiece(g, 'O', WIDTH - 2);
  assert.equal(g.move(1), false);
});

test('rotation turns clockwise, preserves blocks, and supports wall kicks', () => {
  const g = game();
  usePiece(g, 'T');
  const original = g.active.cells;
  assert.equal(g.rotate(), true);
  assert.deepEqual(g.active.cells, [[0, 1, 0], [0, 1, 1], [0, 1, 0]]);
  for (let i = 0; i < 3; i++) g.rotate();
  assert.deepEqual(g.active.cells, original);
  usePiece(g, 'I');
  g.rotate();
  g.active.x = -2;
  assert.equal(g.fits(g.active), true);
  assert.equal(g.rotate(), true);
  assert.equal(g.active.x, 0);
});

test('blocked rotation leaves the active piece unchanged', () => {
  const g = game();
  usePiece(g, 'T', 3, HEIGHT - 2);
  const before = structuredClone(g.active);
  assert.equal(g.rotate(), false);
  assert.deepEqual(g.active, before);
});

test('gravity moves, locks on the floor, and spawns a new piece', () => {
  const g = game();
  usePiece(g, 'O', 3, HEIGHT - 3);
  assert.equal(g.tick(), true);
  assert.equal(g.active.y, HEIGHT - 2);
  assert.equal(g.tick(), false);
  assert.equal(g.board[HEIGHT - 1][3], 'O');
  assert.equal(g.board.flat().filter(Boolean).length, 4);
  assert.equal(g.active.y, 0);
});

test('soft and hard drops award points and lock on stacks', () => {
  const g = game();
  usePiece(g, 'O');
  assert.equal(g.tick({ softDrop: true }), true);
  assert.equal(g.score, 1);
  g.board[10][3] = 'J';
  assert.equal(g.hardDrop(), 7);
  assert.equal(g.score, 15);
  assert.equal(g.board[9][3], 'O');
});

for (const [count, points] of [[1, 100], [2, 300], [3, 500], [4, 800]]) {
  test(`clearing ${count} lines compacts the board and scores ${points}`, () => {
    const g = game();
    for (let y = HEIGHT - count; y < HEIGHT; y++) g.board[y].fill('I');
    g.board[HEIGHT - count - 1][0] = 'T';
    assert.equal(g.clearLines(), count);
    assert.equal(g.lines, count);
    assert.equal(g.score, points);
    assert.equal(g.board.length, HEIGHT);
    assert.equal(g.board[HEIGHT - 1][0], 'T');
    assert.ok(g.board[0].every(cell => cell === null));
  });
}

test('locking completes lines and scoring scales with level', () => {
  const g = game();
  g.lines = 10;
  g.board[HEIGHT - 1].fill('T');
  g.board[HEIGHT - 1][4] = null;
  g.board[HEIGHT - 1][5] = null;
  usePiece(g, 'O', 4, HEIGHT - 2);
  g.tick();
  assert.equal(g.lines, 11);
  assert.equal(g.score, 200);
  assert.equal(g.level, 2);
  assert.ok(g.gravityMs < 800);
});

test('blocked spawn ends play; reset starts a fresh game', () => {
  const g = game();
  g.board[0].fill('Z');
  g.board[1].fill('Z');
  g.spawn();
  assert.equal(g.gameOver, true);
  const before = structuredClone(g.board);
  assert.equal(g.move(1), false);
  assert.equal(g.rotate(), false);
  assert.equal(g.tick(), false);
  assert.equal(g.hardDrop(), 0);
  assert.deepEqual(g.board, before);
  g.reset();
  assert.equal(g.gameOver, false);
  assert.equal(g.score, 0);
  assert.equal(g.lines, 0);
  assert.ok(g.fits(g.active));
});

test('frame includes the active piece without altering the settled board', () => {
  const g = game();
  const frame = g.frame();
  assert.equal(frame.length, HEIGHT);
  assert.ok(frame.every(row => row.length === WIDTH));
  assert.equal(frame.flat().filter(Boolean).length, 4);
  frame[HEIGHT - 1][0] = 'Z';
  assert.equal(g.board.flat().filter(Boolean).length, 0);
});
