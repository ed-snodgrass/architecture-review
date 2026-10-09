import test from 'node:test';
import assert from 'node:assert/strict';
import { Game } from '../src/game.js';
import { renderGame } from '../src/render.js';

for (const gameOver of [false, true]) {
  test(`${gameOver ? 'game-over' : 'playing'} display includes everything within 24 rows`, () => {
    const game = new Game({ random: () => 0 });
    game.gameOver = gameOver;
    game.score = 123456;
    game.lines = 42;
    const frame = renderGame(game);
    const rows = frame.split('\n');
    assert.equal(rows.length, 24);
    assert.equal(frame.endsWith('\n'), false, 'a trailing newline would scroll a 24-row terminal');
    assert.equal(rows[0], '+' + '-'.repeat(20) + '+');
    assert.equal(rows[21], rows[0]);
    for (const row of rows.slice(1, 21)) {
      assert.match(row, /^\|(?:  |\[\]){10}\|$/);
    }
    assert.ok(rows[22].includes('Score: 123456 | Lines: 42'));
    assert.equal(rows[22].includes('GAME OVER'), gameOver);
    assert.equal(rows[23], 'Arrows: move/rotate | Space: drop | Q: quit');
    assert.equal(frame.includes('\r'), false);
  });
}

test('render overlays falling cells without modifying the board or game', () => {
  const game = new Game({ random: () => 0 });
  game.active = null;
  game.spawn('O');
  game.board[19][0] = 'J';
  const before = JSON.stringify(game);
  const rows = renderGame(game).split('\n');
  const cell = (x, y) => rows[y + 1].slice(1 + x * 2, 3 + x * 2);
  assert.equal(cell(0, 19), '[]');
  for (const y of [0, 1]) {
    for (const x of [4, 5]) assert.equal(cell(x, y), '[]');
  }
  assert.equal(cell(0, 0), '  ');
  assert.equal(JSON.stringify(game), before);
  game.gameOver = true;
  assert.equal(renderGame(game).split('\n')[1].includes('[]'), false,
    'game-over frames show only locked cells');
});
