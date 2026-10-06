import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { Tetris, SHAPES } from '../src/engine.js';
import { renderScreen, SCREEN_ROWS, SCREEN_COLUMNS } from '../src/display.js';

test('all pieces and game-over screen fit in 24 rows without wrapping', () => {
  const game = new Tetris();
  for (const type of Object.keys(SHAPES)) {
    for (const gameOver of [false, true]) {
      game.active = { type, matrix: SHAPES[type], x: 3, y: 0 };
      game.gameOver = gameOver;
      const lines = renderScreen(game);
      assert.equal(lines.length, SCREEN_ROWS);
      assert.ok(lines.length <= 24);
      assert.ok(lines.every(line => line.length <= SCREEN_COLUMNS));
      const screen = lines.join('\n');
      for (const label of ['Score:', 'Lines:', 'Level:', 'Next:', 'move', 'rotate', 'soft drop', 'hard drop', 'restart', 'quit']) {
        assert.ok(screen.includes(label), label);
      }
      assert.ok(screen.includes(gameOver ? 'GAME OVER' : 'Playing'));
      if (gameOver) assert.ok(screen.includes('Press R to play again'));
    }
  }
});

test('rendering does not mutate the board and bounded status stays within width', () => {
  const game = new Tetris();
  game.score = Number.MAX_SAFE_INTEGER;
  game.lines = Number.MAX_SAFE_INTEGER;
  const before = structuredClone(game.board);
  assert.ok(renderScreen(game).every(line => line.length <= SCREEN_COLUMNS));
  assert.deepEqual(game.board, before);
});

test('startup without a terminal exits with a helpful error', () => {
  const result = spawnSync(process.execPath, ['src/cli.js'], { encoding: 'utf8' });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /interactive terminal/);
});
