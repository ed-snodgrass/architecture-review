const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

// Regression for the first unfinished plan finding: moving the second T
// left encounters board[10][0]; only the rightward fixture can reach the floor.
// Drive descent with gravity, independently of the existing move-based test.
for (const [direction, bottomRow, intervals] of [
  [-1, 10, 9],
  [1, 19, 18],
]) {
  test(`second-piece gravity respects the ${direction < 0 ? 'obstructed left' : 'clear right'} path`, async () => {
    const api = await import(pathToFileURL(path.join(__dirname, '../src/game.js')).href);
    const game = api.createGame({ pieceSequence: ['O', 'T', 'I'], fallIntervalMs: 1000 });
    while (api.move(game, 0, 1)) {}
    const firstCells = api.getActiveCells(game);
    game.board[10][0] = 'marker';
    api.tick(game, 1000);
    assert.equal(game.active.type, 'T');
    for (let step = 0; step < 4; step++) api.move(game, direction, 0);
    const settled = structuredClone(game.board);

    for (let step = 0; step < intervals; step++) {
      const before = api.getActiveCells(game);
      api.tick(game, 1000);
      assert.deepEqual(api.getActiveCells(game), before.map(({ x, y }) => ({ x, y: y + 1 })),
        'each unobstructed gravity interval descends exactly one row');
      assert.deepEqual(game.board, settled, 'descent must not lock early');
    }
    const landed = api.getActiveCells(game);
    assert.equal(Math.max(...landed.map(cell => cell.y)), bottomRow);
    if (direction < 0) {
      assert.ok(landed.some(cell => cell.x === 0 && cell.y === 9),
        'the left path rests immediately above the marker');
    } else {
      assert.ok(landed.every(cell => cell.x > 0), 'the right path avoids column zero');
    }
    api.tick(game, 999);
    assert.deepEqual(game.board, settled, 'locking waits for the full gravity interval');
    api.tick(game, 1);
    assert.equal(game.active.type, 'I');
    assert.equal(game.board[10][0], 'marker', 'collision must preserve the obstruction');
    for (const { x, y } of [...firstCells, ...landed]) assert.notEqual(game.board[y][x], null);
    assert.equal(game.board.flat().filter(cell => cell !== null).length, 9);
    assert.equal(game.score, 0);
    assert.equal(game.gameOver, false);
  });
}
