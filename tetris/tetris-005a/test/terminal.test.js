import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { Game } from '../src/engine.js';
import { render } from '../src/terminal.js';

for (const columns of [64, 80, 120]) {
  for (const gameOver of [false, true]) {
    test(`render at ${columns} columns, gameOver=${gameOver}, fits 24 rows`, () => {
      const game = new Game({ random: () => 0 });
      game.board[19][0] = 'J';
      if (gameOver) {
        game.active = null;
        game.gameOver = true;
      }
      const before = JSON.stringify(game);
      const frame = render(game, columns);
      const rows = frame.split('\n');
      assert.equal(rows.length, 24);
      assert.ok(rows.every(row => row.length < columns), 'no terminal wrapping');
      assert.ok(!frame.includes('\x1b'));
      assert.equal(rows[0], '+--------------------+');
      assert.equal(rows[21], rows[0]);
      assert.ok(rows.slice(1, 21).every(row => /^\|.{20}\|$/.test(row)));
      assert.ok(rows[20].startsWith('|[]'));
      assert.equal((rows.slice(1, 21).join('').match(/\[\]/g) || []).length,
        gameOver ? 1 : 5, 'settled board and active piece are visible');
      assert.match(rows[22], /Score: 0.*Lines: 0.*Level: 1.*Next:/);
      assert.equal(rows[22].includes('GAME OVER! R: restart'), gameOver);
      assert.match(rows[23], /Arrows: move\/rotate\/drop.*Space: hard drop.*R: restart.*Q: quit/);
      assert.equal(JSON.stringify(game), before, 'render does not mutate game');
    });
  }
}

test('noninteractive npm start fails cleanly without escape sequences', () => {
  const result = spawnSync('npm', ['start'], { encoding: 'utf8', timeout: 10000 });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /requires an interactive terminal/);
  assert.ok(!`${result.stdout}${result.stderr}`.includes('\x1b'));
  assert.ok(result.stdout.length + result.stderr.length < 2000);
});

test('actual npm start passes PTY interaction and restoration checks', {
  timeout: 30000,
  skip: process.platform === 'win32' ? 'requires POSIX PTYs and Python 3' : false,
}, () => {
  const result = spawnSync('python3', ['test/terminal-pty.py'], {
    encoding: 'utf8', timeout: 25000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
});
