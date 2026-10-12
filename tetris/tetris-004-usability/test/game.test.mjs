import test from 'node:test';
import assert from 'node:assert/strict';
import { Game, PIECES, WIDTH, HEIGHT, cells, createBag } from '../src/game.mjs';
import { render } from '../src/render.mjs';

const gameWith = type => new Game({ nextPiece: () => type });
const snapshot = game => JSON.stringify({ board: game.board, active: game.active, score: game.score, lines: game.lines });

test('every tetromino spawns with four cells and rotates through a full cycle', () => {
  for (const type of PIECES) {
    const game = gameWith(type);
    assert.equal(cells(game.active).length, 4);
    assert.ok(game.fits(game.active));
    const original = snapshot(game);
    for (let i = 0; i < 4; i++) assert.ok(game.rotate());
    assert.equal(snapshot(game), original);
  }
});

test('seven-bag supplies every type once per bag', () => {
  const next = createBag(() => 0.25);
  for (let i = 0; i < 3; i++) {
    assert.deepEqual(Array.from({ length: 7 }, next).sort(), [...PIECES].sort());
  }
});

test('wall and settled-block collisions reject movement without mutation', () => {
  const game = gameWith('O');
  while (game.move(-1)) {}
  let before = snapshot(game);
  assert.equal(game.move(-1), false);
  assert.equal(snapshot(game), before);
  while (game.move(1)) {}
  before = snapshot(game);
  assert.equal(game.move(1), false);
  assert.equal(snapshot(game), before);
  game.board[0][game.active.x - 1] = 'I';
  before = snapshot(game);
  assert.equal(game.move(-1), false);
  assert.equal(snapshot(game), before);
});

test('blocked rotation leaves active piece unchanged', () => {
  const game = gameWith('T');
  game.active.y = 5;
  game.board = game.board.map(row => row.map(() => 'J'));
  for (const { x, y } of cells(game.active)) game.board[y][x] = null;
  const before = snapshot(game);
  assert.equal(game.rotate(), false);
  assert.equal(snapshot(game), before);
});

test('rotation kicks away from walls and floor', () => {
  const game = gameWith('I');
  assert.ok(game.rotate());
  while (game.move(-1)) {}
  assert.ok(game.rotate());
  assert.ok(game.fits(game.active));
  game.active.y = 18;
  assert.ok(game.rotate());
  assert.ok(game.fits(game.active));
});

test('gravity and soft drop reach the floor then lock and spawn', () => {
  const game = gameWith('O');
  assert.ok(game.step());
  assert.equal(game.score, 0);
  assert.ok(game.step(true));
  assert.equal(game.score, 1);
  while (game.step()) {}
  assert.equal(game.board.flat().filter(Boolean).length, 4);
  assert.equal(game.active.y, 0);
  assert.equal(game.board.length, HEIGHT);
});

test('hard drop scores distance, lands on settled cells and immediately locks', () => {
  const game = gameWith('O');
  assert.equal(game.hardDrop(), 18);
  assert.equal(game.score, 36);
  assert.equal(game.hardDrop(), 16);
  assert.equal(game.score, 68);
  assert.equal(game.board.flat().filter(Boolean).length, 8);
});

for (let count = 1; count <= 4; count++) {
  test(`clears ${count} lines simultaneously and scores correctly`, () => {
    const game = gameWith('I');
    game.rotate();
    game.active.x = 2; // Vertical I occupies column 4.
    game.active.y = 16;
    for (let y = HEIGHT - count; y < HEIGHT; y++) {
      game.board[y] = Array(WIDTH).fill('J');
      game.board[y][4] = null;
    }
    game.lock();
    assert.equal(game.lines, count);
    assert.equal(game.score, [0, 100, 300, 500, 800][count]);
    assert.equal(game.board.length, HEIGHT);
    assert.equal(game.board.flat().filter(Boolean).length, 4 - count);
    assert.ok(game.board.slice(0, count).every(row => row.every(cell => cell === null)));
    assert.notEqual(game.board[0], game.board[1]);
  });
}

test('line scoring uses the current level and gravity accelerates', () => {
  const game = gameWith('I');
  game.lines = 9;
  const interval = game.fallInterval;
  game.active.x = 0;
  game.active.y = 18;
  game.board[19] = Array(WIDTH).fill('T');
  game.board[19].fill(null, 0, 4);
  game.lock();
  assert.equal(game.score, 100);
  assert.equal(game.level, 2);
  assert.ok(game.fallInterval < interval);
});

test('blocked spawn ends the game and all gameplay actions freeze', () => {
  const game = gameWith('O');
  game.board[0][4] = 'T';
  game.hardDrop();
  assert.ok(game.gameOver);
  assert.equal(game.active, null);
  const before = snapshot(game);
  game.move(1);
  game.rotate();
  game.step(true);
  game.hardDrop();
  game.lock();
  assert.equal(snapshot(game), before);
});

test('invalid lock never writes outside the board', () => {
  const game = gameWith('O');
  game.active.y = HEIGHT;
  game.lock();
  assert.ok(game.gameOver);
  assert.equal(game.board.flat().filter(Boolean).length, 0);
});

test('display overlays active cells without changing state and fits 24 rows', () => {
  const game = gameWith('T');
  const before = snapshot(game);
  const frame = render(game);
  assert.equal(snapshot(game), before);
  assert.equal(frame.split('\n').length, 24);
  assert.ok(frame.split('\n').every(line => line.length <= 80));
  assert.match(frame, /Score 0/);
  assert.match(frame, /Arrows/);
  game.gameOver = true;
  game.active = null;
  assert.match(render(game), /GAME OVER/);
  assert.equal(render(game).split('\n').length, 24);
});
