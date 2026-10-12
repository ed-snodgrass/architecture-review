import test from 'node:test';
import assert from 'node:assert/strict';
import { Game } from '../src/game.mjs';
import { render, DISPLAY_COLUMNS, DISPLAY_ROWS } from '../src/render.mjs';

for (const gameOver of [false, true]) {
  for (const largeCounters of [false, true]) {
    test(`display fits 24 rows (gameOver=${gameOver}, largeCounters=${largeCounters})`, () => {
      const game = new Game({ nextPiece: () => 'T' });
      game.gameOver = gameOver;
      if (gameOver) game.active = null;
      if (largeCounters) {
        game.score = Number.MAX_SAFE_INTEGER;
        game.lines = Number.MAX_SAFE_INTEGER;
      }
      const text = render(game);
      const rows = text.split('\n');
      assert.equal(rows.length, DISPLAY_ROWS);
      assert.ok(rows.every(row => [...row].length <= DISPLAY_COLUMNS));
      assert.match(rows[0], gameOver ? /^GAME OVER/ : /^TETRIS/);
      assert.match(rows[0], /Score .*Lines .*Level /);
      assert.equal(rows[1], '+--------------------+');
      assert.ok(rows.slice(2, 22).every(row => /^\|.{20}\|$/.test(row)));
      assert.equal(rows[22], '+--------------------+');
      assert.match(rows[23], /Q\/\^C quit$/);
      assert.ok(!text.endsWith('\n'), 'no extra row after controls');
    });
  }
}
