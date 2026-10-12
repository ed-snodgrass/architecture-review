const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

// Contract for the locking/clearing/scoring/game-over task:
// Reuse the existing mutable mechanics API and deterministic pieceSequence.
// A gravity step that cannot descend settles the piece, clears full rows,
// updates numeric game.score, and spawns the next sequence entry.
// game.gameOver is a boolean; a blocked spawn ends the game without
// overwriting settled cells. Movement, rotation, and ticks then do nothing.
// No scoring formula, hard drop, lock delay, or rendering API is prescribed.
const loadGame = () => import(pathToFileURL(path.join(__dirname, '../src/game.js')).href);
const key = cells => cells.map(({ x, y }) => `${x},${y}`).sort().join(';');
const occupied = board => board.flat().filter(cell => cell !== null).length;

function atFloor(api, game) {
  // Existing move() only attempts movement; use tick() for the lock trigger.
  for (let n = 0; n < 20; n++) {
    const before = key(api.getActiveCells(game));
    api.move(game, 0, 1);
    if (key(api.getActiveCells(game)) === before) break;
  }
  assert.equal(Math.max(...api.getActiveCells(game).map(c => c.y)), 19);
}

function assertLegalSpawn(api, game, type) {
  assert.equal(game.active.type, type);
  const cells = api.getActiveCells(game);
  assert.equal(cells.length, 4);
  assert.equal(new Set(cells.map(c => `${c.x},${c.y}`)).size, 4);
  assert.ok(Math.min(...cells.map(c => c.y)) <= 1, 'next piece spawns near the top');
  for (const { x, y } of cells) {
    assert.ok(x >= 0 && x < 10 && y >= 0 && y < 20);
    assert.equal(game.board[y][x], null, 'spawn must not overlap settled cells');
  }
}

function assertBoard(game, expected) {
  assert.equal(game.board.length, 20);
  assert.ok(game.board.every(row => row.length === 10));
  assert.equal(new Set(game.board).size, 20, 'compacted rows remain independent');
  // The occupied-cell encoding is unspecified. Compare occupancy, preserving
  // fixture markers separately where their identity matters.
  assert.deepEqual(game.board.map(row => row.map(c => c !== null)),
    expected.map(row => row.map(c => c !== null)));
}

test('a new game exposes initial score and game-over state', async () => {
  const api = await loadGame();
  const game = api.createGame({ pieceSequence: ['O', 'T'] });
  assert.equal(game.score, 0);
  assert.equal(game.gameOver, false);
});

test('a blocked gravity step locks exactly four cells and consumes the next piece', async () => {
  const api = await loadGame();
  const game = api.createGame({ pieceSequence: ['O', 'T', 'I'], fallIntervalMs: 1000 });
  atFloor(api, game);
  const landed = api.getActiveCells(game);
  game.board[10][0] = 'existing';
  api.tick(game, 999);
  assert.equal(occupied(game.board), 1, 'no premature lock before a gravity interval');
  api.tick(game, 1);
  assert.equal(occupied(game.board), 5);
  for (const { x, y } of landed) assert.notEqual(game.board[y][x], null);
  assert.equal(game.board[10][0], 'existing');
  assertLegalSpawn(api, game, 'T');
  assert.equal(game.gameOver, false);
  assert.equal(game.score, 0, 'locking without a completed line earns no line-clear points');
  // Move right to avoid both the first piece and the marker in column 0.
  for (let n = 0; n < 4; n++) api.move(game, 1, 0);
  atFloor(api, game);
  const nextLanded = api.getActiveCells(game);
  api.tick(game, 1000);
  assert.equal(occupied(game.board), 9, 'each piece settles once');
  for (const { x, y } of nextLanded) assert.notEqual(game.board[y][x], null);
  assertLegalSpawn(api, game, 'I');
});

test('gravity locks against a stack, not just against the floor', async () => {
  const api = await loadGame();
  const game = api.createGame({ pieceSequence: ['O', 'T'], fallIntervalMs: 1000 });
  const spawn = api.getActiveCells(game);
  const bottom = Math.max(...spawn.map(c => c.y));
  const blocker = { x: spawn.find(c => c.y === bottom).x, y: bottom + 4 };
  game.board[blocker.y][blocker.x] = 'support';
  for (let n = 0; n < 3; n++) api.tick(game, 1000);
  const landed = api.getActiveCells(game);
  assert.equal(Math.max(...landed.map(c => c.y)), blocker.y - 1);
  assert.equal(occupied(game.board), 1);
  api.tick(game, 1000);
  assert.equal(occupied(game.board), 5);
  for (const { x, y } of landed) assert.notEqual(game.board[y][x], null);
  assert.equal(game.board[blocker.y][blocker.x], 'support');
  assertLegalSpawn(api, game, 'T');
});

for (const [label, type, rows] of [
  ['one row', 'O', [19]],
  ['two adjacent rows', 'O', [18, 19]],
  ['four rows', 'I', [16, 17, 18, 19]],
  ['two nonadjacent rows', 'I', [16, 18]],
]) {
  test(`locking clears ${label}, compacts survivors, and awards points`, async () => {
    const api = await loadGame();
    const game = api.createGame({ pieceSequence: [type, 'T'], fallIntervalMs: 1000 });
    if (type === 'I') api.rotate(game);
    atFloor(api, game);
    const landed = api.getActiveCells(game);
    const holes = new Set(landed.map(c => `${c.x},${c.y}`));
    for (const y of rows) {
      for (let x = 0; x < 10; x++) {
        if (!holes.has(`${x},${y}`)) game.board[y][x] = `row-${y}`;
      }
    }
    game.board[5][0] = 'upper-marker';
    game.board[12][9] = 'lower-marker';
    const expected = game.board.map(row => [...row]);
    for (const { x, y } of landed) expected[y][x] = 'piece';
    const survivors = expected.filter((_, y) => !rows.includes(y));
    const compacted = [
      ...Array.from({ length: rows.length }, () => Array(10).fill(null)),
      ...survivors,
    ];
    const beforeScore = game.score;
    api.tick(game, 1000);
    assertBoard(game, compacted);
    assert.equal(game.board[5 + rows.length][0], 'upper-marker');
    assert.equal(game.board[12 + rows.length][9], 'lower-marker');
    assert.ok(Number.isFinite(game.score) && game.score > beforeScore,
      'cleared lines earn a positive score; exact formula is unspecified');
    assert.ok(game.board.every(row => row.some(c => c === null)), 'no full rows remain');
    assertLegalSpawn(api, game, 'T');
    assert.equal(game.gameOver, false);
  });
}

test('line-clear score accumulates across locks rather than resetting on spawn', async () => {
  const api = await loadGame();
  const game = api.createGame({ pieceSequence: ['O', 'O', 'T'], fallIntervalMs: 1000 });
  let previousScore = 0;
  for (let n = 0; n < 2; n++) {
    atFloor(api, game);
    const holes = new Set(api.getActiveCells(game).map(c => `${c.x},${c.y}`));
    for (const y of [18, 19]) {
      for (let x = 0; x < 10; x++) {
        if (!holes.has(`${x},${y}`)) game.board[y][x] = 'fill';
      }
    }
    api.tick(game, 1000);
    assert.equal(occupied(game.board), 0);
    assert.ok(Number.isFinite(game.score) && game.score > previousScore);
    previousScore = game.score;
  }
  assertLegalSpawn(api, game, 'T');
});

test('line removal happens before checking whether the next spawn is blocked', async () => {
  const api = await loadGame();
  const game = api.createGame({ pieceSequence: ['O', 'T'], fallIntervalMs: 1000 });
  atFloor(api, game);
  const landed = api.getActiveCells(game);
  const holes = new Set(landed.filter(c => c.y === 19).map(c => c.x));
  for (let x = 0; x < 10; x++) {
    if (!holes.has(x)) game.board[19][x] = 'fill';
  }
  const probe = api.createGame({ pieceSequence: ['T'] });
  const spawnCells = api.getActiveCells(probe);
  const blocker = spawnCells.reduce((lowest, cell) => cell.y > lowest.y ? cell : lowest);
  game.board[blocker.y][blocker.x] = 'spawn-marker';
  const expected = game.board.map(row => [...row]);
  for (const { x, y } of landed) expected[y][x] = 'piece';
  expected.pop();
  expected.unshift(Array(10).fill(null));

  api.tick(game, 1000);

  assertBoard(game, expected);
  assert.equal(game.board[blocker.y + 1][blocker.x], 'spawn-marker');
  assert.ok(Number.isFinite(game.score) && game.score > 0);
  assert.equal(game.gameOver, false, 'clearing moves the obstruction below the spawn');
  assertLegalSpawn(api, game, 'T');
});

test('a lock with no completed lines preserves an earned score', async () => {
  const api = await loadGame();
  const game = api.createGame({ pieceSequence: ['O', 'O', 'T'], fallIntervalMs: 1000 });
  atFloor(api, game);
  const holes = new Set(api.getActiveCells(game).map(c => `${c.x},${c.y}`));
  for (const y of [18, 19]) {
    for (let x = 0; x < 10; x++) {
      if (!holes.has(`${x},${y}`)) game.board[y][x] = 'fill';
    }
  }
  api.tick(game, 1000);
  const earned = game.score;
  assert.ok(Number.isFinite(earned) && earned > 0);
  atFloor(api, game);
  api.tick(game, 1000);
  assert.equal(occupied(game.board), 4);
  assert.equal(game.score, earned, 'a subsequent spawn must not reset earned points');
  assertLegalSpawn(api, game, 'T');
});

test('a blocked next spawn ends the game, preserves the stack, and freezes mechanics', async () => {
  const api = await loadGame();
  const game = api.createGame({ pieceSequence: ['O', 'T'], fallIntervalMs: 1000 });
  atFloor(api, game);
  const landed = api.getActiveCells(game);
  // Obtain spawn coordinates through the public API, not a hardcoded pivot.
  const probe = api.createGame({ pieceSequence: ['T'] });
  const blocker = api.getActiveCells(probe)[0];
  game.board[blocker.y][blocker.x] = 'spawn-blocker';
  api.tick(game, 1000);
  assert.equal(game.gameOver, true);
  assert.equal(occupied(game.board), 5);
  assert.equal(game.board[blocker.y][blocker.x], 'spawn-blocker');
  for (const { x, y } of landed) assert.notEqual(game.board[y][x], null);
  const ended = structuredClone(game);
  api.move(game, -1, 0);
  api.move(game, 0, 1);
  api.rotate(game);
  api.tick(game, 10000);
  assert.deepEqual(game, ended, 'game-over state is terminal until a new game is created');
});
