import test from 'node:test';
import assert from 'node:assert/strict';
import { Tetris, SHAPES, WIDTH, HEIGHT, rotateMatrix } from '../src/engine.js';

const createGame = () => new Tetris({ random: () => 0.5 });
const square = (game, x = 4, y = 0) => {
  game.active = { type: 'O', matrix: SHAPES.O.map(row => [...row]), x, y };
};

test('initial board and seven-piece bag are valid', () => {
  const game = createGame();
  assert.equal(game.board.length, HEIGHT);
  assert.ok(game.board.every(row => row.length === WIDTH && row.every(cell => cell === null)));
  assert.equal(new Set(game.board).size, HEIGHT);
  const firstBag = [game.active.type, game.next];
  for (let i = 0; i < 5; i++) firstBag.push(game.takePiece());
  assert.deepEqual(firstBag.sort(), Object.keys(SHAPES).sort());
  const secondBag = Array.from({ length: 7 }, () => game.takePiece());
  assert.deepEqual(secondBag.sort(), Object.keys(SHAPES).sort());
  for (const matrix of Object.values(SHAPES)) {
    assert.equal(matrix.flat().filter(Boolean).length, 4);
  }
  assert.equal(game.collides(game.active), false);
});

test('movement respects both walls, floor, and settled cells', () => {
  const game = createGame();
  square(game, 0, 18);
  assert.equal(game.move(-1), false);
  assert.equal(game.move(0, 1), false);
  assert.equal(game.move(8), true);
  assert.equal(game.move(1), false);
  square(game, 4, 5);
  game.board[5][6] = 'T';
  assert.equal(game.move(1), false);
  assert.equal(game.move(-1), true);
});

test('rotation is reversible and does not mutate shape definitions', () => {
  const original = SHAPES.T.map(row => [...row]);
  assert.deepEqual(rotateMatrix(rotateMatrix(original), false), original);
  let matrix = original;
  for (let i = 0; i < 4; i++) matrix = rotateMatrix(matrix);
  assert.deepEqual(matrix, original);
  const game = createGame();
  game.active = { type: 'T', matrix: original, x: 4, y: 5 };
  assert.equal(game.rotate(), true);
  assert.equal(game.rotate(false), true);
  assert.deepEqual(game.active.matrix, SHAPES.T);
});

test('rotation kicks away from walls and rejects fully obstructed rotations', () => {
  const game = createGame();
  game.active = { type: 'I', matrix: rotateMatrix(SHAPES.I), x: -2, y: 4 };
  assert.equal(game.collides(game.active), false);
  assert.equal(game.rotate(), true);
  assert.equal(game.active.x, 0);
  game.board = game.board.map(row => row.map(() => 'O'));
  const before = game.active;
  assert.equal(game.rotate(), false);
  assert.equal(game.active, before);
});

test('gravity moves without awarding points and locks at the floor', () => {
  const game = createGame();
  square(game, 4, 17);
  assert.equal(game.tick(), true);
  assert.equal(game.active.y, 18);
  assert.equal(game.score, 0);
  assert.equal(game.tick(), false);
  assert.deepEqual(game.board[19].slice(4, 6), ['O', 'O']);
  assert.equal(game.active.y, 0);
});

test('soft and hard drops award distance points and spawn the next piece', () => {
  const game = createGame();
  square(game);
  assert.equal(game.softDrop(), true);
  assert.equal(game.score, 1);
  const next = game.next;
  assert.equal(game.hardDrop(), 17);
  assert.equal(game.score, 35);
  assert.equal(game.active.type, next);
  assert.deepEqual(game.board[18].slice(4, 6), ['O', 'O']);
  square(game, 0, 18);
  assert.equal(game.softDrop(), false);
  assert.deepEqual(game.board[19].slice(0, 2), ['O', 'O']);
});

for (const [count, points] of [[1, 100], [2, 300], [3, 500], [4, 800]]) {
  test(`clearing ${count} rows compacts the board and scores at the current level`, () => {
    const game = createGame();
    game.lines = 10;
    game.board[HEIGHT - count - 1][0] = 'T';
    for (let y = HEIGHT - count; y < HEIGHT; y++) game.board[y].fill('I');
    assert.equal(game.clearLines(), count);
    assert.equal(game.score, points * 2);
    assert.equal(game.lines, 10 + count);
    assert.equal(game.board[HEIGHT - 1][0], 'T');
    assert.ok(game.board.slice(0, count).every(row => row.every(cell => cell === null)));
    assert.equal(new Set(game.board).size, HEIGHT);
    assert.equal(game.clearLines(), 0);
    assert.equal(game.score, points * 2);
  });
}

test('levels accelerate gravity with a minimum interval', () => {
  const game = createGame();
  assert.equal(game.level, 1);
  assert.equal(game.gravityMs, 800);
  game.lines = 9;
  game.board[19].fill('I');
  game.clearLines();
  assert.equal(game.score, 100);
  assert.equal(game.level, 2);
  assert.equal(game.gravityMs, 740);
  game.lines = 1000;
  assert.equal(game.gravityMs, 100);
});

test('blocked spawning ends play; reset clears the game', () => {
  const game = createGame();
  game.board[0].fill('I');
  game.board[1].fill('I');
  game.spawn();
  assert.equal(game.gameOver, true);
  assert.equal(game.active, null);
  const before = JSON.stringify(game.board);
  assert.equal(game.move(1), false);
  assert.equal(game.rotate(), false);
  assert.equal(game.tick(), false);
  assert.equal(game.softDrop(), false);
  assert.equal(game.hardDrop(), 0);
  game.lock();
  assert.equal(JSON.stringify(game.board), before);
  game.score = 100;
  game.lines = 10;
  game.reset();
  assert.equal(game.gameOver, false);
  assert.equal(game.score, 0);
  assert.equal(game.lines, 0);
  assert.ok(game.active);
  assert.ok(game.board.flat().every(cell => cell === null));
});

test('locking a piece above the board ends the game', () => {
  const game = createGame();
  square(game, 4, -1);
  game.lock();
  assert.equal(game.gameOver, true);
  assert.equal(game.active, null);
});

test('display snapshots include the active piece without sharing board rows', () => {
  const game = createGame();
  square(game);
  const view = game.getDisplayBoard();
  assert.equal(view[0][4], 'O');
  assert.equal(game.board[0][4], null);
  view[19][0] = 'I';
  assert.equal(game.board[19][0], null);
});
