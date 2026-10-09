import test from 'node:test';
import assert from 'node:assert/strict';
import { Game, createBoard, TETROMINOES, BOARD_WIDTH, BOARD_HEIGHT } from '../src/game.js';

function gameWith(type = 'O') {
  const game = new Game({ random: () => 0 });
  game.active = null;
  assert.equal(game.spawn(type), true);
  return game;
}

function snapshot(game) {
  return JSON.stringify({ board: game.board, active: game.active, score: game.score,
    lines: game.lines, gameOver: game.gameOver });
}

test('board has 20 independent empty rows of 10 cells', () => {
  const board = createBoard();
  assert.equal(board.length, 20);
  assert.ok(board.every(row => row.length === 10 && row.every(cell => cell === null)));
  board[0][0] = 'T';
  assert.equal(board[1][0], null);
  assert.equal(createBoard()[0][0], null);
});

test('all seven tetrominoes spawn centered with four cells and independent matrices', () => {
  assert.deepEqual(Object.keys(TETROMINOES).sort(), ['I', 'J', 'L', 'O', 'S', 'T', 'Z']);
  for (const type of Object.keys(TETROMINOES)) {
    const game = gameWith(type);
    assert.equal(game.active.matrix.flat().filter(Boolean).length, 4);
    assert.equal(game.active.x, Math.floor((BOARD_WIDTH - game.active.matrix.length) / 2));
    assert.equal(game.active.y, 0);
    assert.ok(game.canPlace(game.active));
    game.active.matrix[0][0] = 9;
    assert.notEqual(TETROMINOES[type][0][0], 9);
  }
});

test('each seven-piece bag contains every type exactly once', () => {
  const game = new Game({ random: () => 0.5 });
  const first = [game.active.type, ...Array.from({ length: 6 }, () => game.nextType())];
  const second = Array.from({ length: 7 }, () => game.nextType());
  const expected = Object.keys(TETROMINOES).sort();
  assert.deepEqual(first.sort(), expected);
  assert.deepEqual(second.sort(), expected);
});

test('movement is one cell and cannot cross walls, floor, or settled blocks', () => {
  const game = gameWith();
  const x = game.active.x;
  assert.equal(game.move(-1), true);
  assert.equal(game.active.x, x - 1);
  assert.equal(game.move(1), true);
  for (const args of [[2, 0], [0, -1], [1, 1], [0, 0], [0.5, 0]]) {
    const before = snapshot(game);
    assert.equal(game.move(...args), false);
    assert.equal(snapshot(game), before);
  }
  while (game.move(-1)) {}
  assert.equal(game.active.x, 0);
  assert.equal(game.move(-1), false);
  while (game.move(1)) {}
  assert.equal(game.active.x, BOARD_WIDTH - 2);
  game.board[2][game.active.x] = 'J';
  assert.equal(game.move(0, 1), false);
  game.board[2][game.active.x] = null;
  while (game.move(0, 1)) {}
  assert.equal(game.active.y, BOARD_HEIGHT - 2);
  assert.equal(game.move(0, 1), false);
});

test('rotation is reversible and four clockwise turns restore the shape', () => {
  const game = gameWith('T');
  const before = snapshot(game);
  assert.equal(game.rotate(), true);
  assert.notEqual(snapshot(game), before);
  assert.equal(game.rotate(-1), true);
  assert.equal(snapshot(game), before);
  for (let i = 0; i < 4; i++) assert.equal(game.rotate(), true);
  assert.equal(snapshot(game), before);
  assert.equal(game.rotate(0), false);
});

test('rotation kicks away from a wall and rejects fully obstructed rotations', () => {
  const game = gameWith('I');
  assert.equal(game.rotate(), true);
  while (game.move(-1)) {}
  assert.equal(game.active.x, -2);
  assert.equal(game.rotate(), true);
  assert.equal(game.active.x, 0);
  assert.ok(game.canPlace(game.active));

  const blocked = gameWith('T');
  blocked.board = blocked.board.map(row => row.map(() => 'J'));
  for (let y = 0; y < 3; y++) {
    for (let x = 0; x < 3; x++) {
      if (blocked.active.matrix[y][x]) blocked.board[y][blocked.active.x + x] = null;
    }
  }
  const before = snapshot(blocked);
  assert.equal(blocked.rotate(), false);
  assert.equal(snapshot(blocked), before);
});

test('gravity moves then locks grounded pieces and spawns a successor', () => {
  const game = gameWith();
  assert.equal(game.lock(), false, 'airborne pieces cannot lock');
  assert.equal(game.tick(), true);
  assert.equal(game.active.y, 1);
  assert.ok(game.board.flat().every(cell => cell === null));
  while (game.move(0, 1)) {}
  assert.equal(game.tick(), true);
  assert.equal(game.board.flat().filter(cell => cell === 'O').length, 4);
  assert.ok(game.active);
  assert.equal(game.active.y, 0);
});

test('hard drop lands on an obstacle, locks immediately, and spawns once', () => {
  const game = gameWith();
  const x = game.active.x;
  game.board[10][x] = 'J';
  game.bag = ['T'];
  assert.equal(game.hardDrop(), true);
  for (const y of [8, 9]) {
    assert.equal(game.board[y][x], 'O');
    assert.equal(game.board[y][x + 1], 'O');
  }
  assert.equal(game.board[10][x], 'J');
  assert.equal(game.active.type, 'T');
  assert.equal(game.active.y, 0);
});

for (const [count, score] of [[1, 100], [2, 300], [3, 500], [4, 800]]) {
  test(`clearing ${count} lines preserves remaining rows and awards ${score} points`, () => {
    const game = gameWith();
    game.board[BOARD_HEIGHT - count - 1][0] = 'T';
    for (let y = BOARD_HEIGHT - count; y < BOARD_HEIGHT; y++) game.board[y].fill('I');
    assert.equal(game.clearLines(), count);
    assert.equal(game.score, score);
    assert.equal(game.lines, count);
    assert.equal(game.board.length, BOARD_HEIGHT);
    assert.equal(game.board[BOARD_HEIGHT - 1][0], 'T');
    assert.ok(game.board.slice(0, count).every(row => row.every(cell => cell === null)));
    assert.equal(game.clearLines(), 0);
    assert.equal(game.score, score);
    game.board[BOARD_HEIGHT - 1].fill('I');
    assert.equal(game.clearLines(), 1);
    assert.equal(game.score, score + 100);
    assert.equal(game.lines, count + 1);
  });
}

test('locking clears completed lines before testing the next spawn', () => {
  const game = gameWith('I');
  game.active.y = 18;
  game.board[19].fill('J');
  for (let x = 3; x < 7; x++) game.board[19][x] = null;
  // The I spawn occupies row 1; clearing shifts this blocker to row 2.
  game.board[1][4] = 'J';
  game.bag = ['I'];
  assert.equal(game.lock(), true);
  assert.equal(game.lines, 1);
  assert.equal(game.score, 100);
  assert.equal(game.gameOver, false);
  assert.equal(game.active.type, 'I');
});

test('blocked spawn ends the game and subsequent actions leave state unchanged', () => {
  const game = gameWith();
  game.board[0][4] = 'J';
  game.bag = ['O'];
  assert.equal(game.hardDrop(), true);
  assert.equal(game.gameOver, true);
  assert.equal(game.active, null);
  const before = snapshot(game);
  for (const action of [() => game.spawn(), () => game.move(1), () => game.rotate(),
    () => game.tick(), () => game.hardDrop(), () => game.lock()]) {
    assert.equal(action(), false);
    assert.equal(snapshot(game), before);
  }
  assert.equal(game.clearLines(), 0);
  assert.equal(snapshot(game), before);
});

test('spawn cannot replace an active piece and rejects unknown types', () => {
  const game = gameWith();
  const before = snapshot(game);
  assert.equal(game.spawn('T'), false);
  assert.equal(snapshot(game), before);
  game.active = null;
  assert.throws(() => game.spawn('unknown'), RangeError);
});
