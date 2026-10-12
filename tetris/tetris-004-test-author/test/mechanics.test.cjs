const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

// Mechanics boundary for the first unfinished task (no terminal I/O):
// src/game.js exports createGame, getActiveCells, move, rotate, and tick.
// createGame({ pieceSequence: ['T', ...], fallIntervalMs: 1000 }) returns
// { board, active, ... }, with a 20x10 board whose empty cells are null.
// pieceSequence deterministically selects tetrominoes; active.type is its name.
// getActiveCells(game) returns four absolute { x, y } coordinates.
// move(game, dx, dy) attempts one orthogonal cell of movement; rotate(game)
// attempts a quarter turn. Both mutate only when the candidate is legal.
// tick(game, elapsedMs) advances the elapsed-time accumulator and gravity.
// Tests intentionally do not require return values, a rotation direction,
// a pivot convention, wall kicks, or a particular internal piece encoding.
// Locking, line removal, scoring, controls, and rendering are later tasks.
const moduleUrl = pathToFileURL(path.join(__dirname, '../src/game.js')).href;
const loadGame = () => import(moduleUrl);
const names = ['I', 'O', 'T', 'S', 'Z', 'J', 'L'];
const shapes = {
  I: [[0, 0], [1, 0], [2, 0], [3, 0]],
  O: [[0, 0], [1, 0], [0, 1], [1, 1]],
  T: [[0, 0], [1, 0], [2, 0], [1, 1]],
  S: [[1, 0], [2, 0], [0, 1], [1, 1]],
  Z: [[0, 0], [1, 0], [1, 1], [2, 1]],
  J: [[0, 0], [0, 1], [1, 1], [2, 1]],
  L: [[2, 0], [0, 1], [1, 1], [2, 1]],
};
const key = cells => cells.map(({ x, y }) => `${x},${y}`).sort().join(';');
function normalized(points) {
  const minX = Math.min(...points.map(([x]) => x));
  const minY = Math.min(...points.map(([, y]) => y));
  return key(points.map(([x, y]) => ({ x: x - minX, y: y - minY })));
}
function orientations(points) {
  const result = new Set();
  for (let n = 0; n < 4; n++) {
    result.add(normalized(points));
    points = points.map(([x, y]) => [-y, x]);
  }
  return result;
}
function cells(api, game) {
  const result = api.getActiveCells(game);
  assert.equal(result.length, 4);
  assert.equal(new Set(result.map(({ x, y }) => `${x},${y}`)).size, 4);
  for (const { x, y } of result) {
    assert.ok(Number.isInteger(x) && Number.isInteger(y));
    assert.ok(x >= 0 && x < 10 && y >= 0 && y < 20, 'active cells stay inside the board');
    assert.equal(game.board[y][x], null, 'active piece never overlaps settled cells');
  }
  return result;
}
function fresh(api, type = 'T') {
  return api.createGame({ pieceSequence: [type], fallIntervalMs: 1000 });
}
function shift(points, dx, dy) {
  return key(points.map(({ x, y }) => ({ x: x + dx, y: y + dy })));
}
function moveToMiddle(api, game) {
  for (let n = 0; n < 6; n++) api.move(game, 0, 1);
}

test('mechanics module exposes the deterministic test boundary', async () => {
  const api = await loadGame();
  for (const name of ['createGame', 'getActiveCells', 'move', 'rotate', 'tick']) {
    assert.equal(typeof api[name], 'function', `${name} must be exported`);
  }
});

for (const type of names) {
  test(`${type} spawns as its own tetromino on an empty, independent 10x20 board`, async () => {
    const api = await loadGame();
    const game = fresh(api, type);
    assert.equal(game.board.length, 20);
    for (const row of game.board) {
      assert.equal(row.length, 10);
      assert.ok(row.every(cell => cell === null));
    }
    assert.equal(new Set(game.board).size, 20, 'rows must not share arrays');
    assert.equal(game.active.type, type);
    const spawned = cells(api, game);
    assert.ok(orientations(shapes[type]).has(normalized(spawned.map(({ x, y }) => [x, y]))));
    assert.ok(Math.min(...spawned.map(cell => cell.y)) <= 1, 'spawn near the top');
    assert.ok(Math.min(...spawned.map(cell => cell.x)) >= 3 &&
      Math.max(...spawned.map(cell => cell.x)) <= 6, 'spawn centered horizontally');
    game.board[19][0] = 'X';
    assert.equal(fresh(api, type).board[19][0], null, 'games must not share boards');
  });

  test(`${type} rotates legally and returns to the original cells after four turns`, async () => {
    const api = await loadGame();
    const game = fresh(api, type);
    moveToMiddle(api, game);
    const before = key(cells(api, game));
    const boardBefore = JSON.stringify(game.board);
    api.rotate(game);
    const turned = cells(api, game);
    assert.ok(orientations(shapes[type]).has(normalized(turned.map(({ x, y }) => [x, y]))));
    if (type !== 'O') assert.notEqual(key(turned), before, 'non-square pieces actually rotate');
    for (let n = 0; n < 3; n++) api.rotate(game);
    assert.equal(key(cells(api, game)), before);
    assert.equal(JSON.stringify(game.board), boardBefore, 'rotation does not settle the piece');
  });
}

test('legal left, right, and downward moves translate exactly one cell', async () => {
  const api = await loadGame();
  const game = fresh(api);
  const boardBefore = JSON.stringify(game.board);
  for (const [dx, dy] of [[-1, 0], [1, 0], [0, 1]]) {
    const before = cells(api, game);
    api.move(game, dx, dy);
    assert.equal(key(cells(api, game)), shift(before, dx, dy));
  }
  assert.equal(JSON.stringify(game.board), boardBefore);
});

for (const [label, dx, dy] of [['left wall', -1, 0], ['right wall', 1, 0], ['floor', 0, 1]]) {
  test(`movement cannot cross the ${label}`, async () => {
    const api = await loadGame();
    const game = fresh(api);
    for (let n = 0; n < 25; n++) api.move(game, dx, dy);
    const before = cells(api, game);
    if (dx === -1) assert.equal(Math.min(...before.map(c => c.x)), 0);
    if (dx === 1) assert.equal(Math.max(...before.map(c => c.x)), 9);
    if (dy === 1) assert.equal(Math.max(...before.map(c => c.y)), 19);
    api.move(game, dx, dy);
    assert.equal(key(cells(api, game)), key(before));
  });
}

for (const [dx, dy] of [[-1, 0], [1, 0], [0, 1]]) {
  test(`settled cells block movement (${dx}, ${dy}) without partial movement`, async () => {
    const api = await loadGame();
    const game = fresh(api);
    moveToMiddle(api, game);
    const before = cells(api, game);
    const occupied = new Set(before.map(c => `${c.x},${c.y}`));
    const blocker = before.map(({ x, y }) => ({ x: x + dx, y: y + dy }))
      .find(c => !occupied.has(`${c.x},${c.y}`));
    game.board[blocker.y][blocker.x] = 'X';
    const boardBefore = JSON.stringify(game.board);
    api.move(game, dx, dy);
    assert.equal(key(cells(api, game)), key(before));
    assert.equal(JSON.stringify(game.board), boardBefore);
  });
}

test('rotation cannot overlap settled cells, even if wall kicks are supported', async () => {
  const api = await loadGame();
  const game = fresh(api);
  moveToMiddle(api, game);
  const before = cells(api, game);
  const occupied = new Set(before.map(c => `${c.x},${c.y}`));
  for (let y = 0; y < 20; y++) {
    for (let x = 0; x < 10; x++) {
      if (!occupied.has(`${x},${y}`)) game.board[y][x] = 'X';
    }
  }
  const boardBefore = JSON.stringify(game.board);
  api.rotate(game);
  assert.equal(key(cells(api, game)), key(before));
  assert.equal(JSON.stringify(game.board), boardBefore);
});

test('rotations at either wall remain inside the board', async () => {
  const api = await loadGame();
  for (const type of names) {
    for (const dx of [-1, 1]) {
      const game = fresh(api, type);
      moveToMiddle(api, game);
      for (let n = 0; n < 10; n++) api.move(game, dx, 0);
      for (let n = 0; n < 4; n++) {
        api.rotate(game);
        cells(api, game);
      }
    }
  }
});

test('gravity waits for an interval and retains fractional elapsed time', async () => {
  const api = await loadGame();
  const game = fresh(api);
  const before = cells(api, game);
  const boardBefore = JSON.stringify(game.board);
  api.tick(game, 0);
  api.tick(game, 999);
  assert.equal(key(cells(api, game)), key(before));
  api.tick(game, 1);
  assert.equal(key(cells(api, game)), shift(before, 0, 1));
  api.tick(game, 400);
  api.tick(game, 599);
  assert.equal(key(cells(api, game)), shift(before, 0, 1));
  api.tick(game, 1);
  assert.equal(key(cells(api, game)), shift(before, 0, 2));
  assert.equal(JSON.stringify(game.board), boardBefore);
});

test('elapsed-time gravity is independent of how elapsed time is partitioned', async () => {
  const api = await loadGame();
  const whole = fresh(api);
  const split = fresh(api);
  const before = cells(api, whole);
  api.tick(whole, 3500);
  for (let n = 0; n < 7; n++) api.tick(split, 500);
  assert.equal(key(cells(api, whole)), shift(before, 0, 3));
  assert.equal(key(cells(api, split)), key(cells(api, whole)));
  api.tick(whole, 500);
  api.tick(split, 500);
  assert.equal(key(cells(api, whole)), shift(before, 0, 4));
  assert.equal(key(cells(api, split)), key(cells(api, whole)));
});
