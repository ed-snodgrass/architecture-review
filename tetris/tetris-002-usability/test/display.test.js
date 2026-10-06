import test from 'node:test';
import assert from 'node:assert/strict';
import { Tetris, SHAPES } from '../src/engine.js';
import { renderFrame, DISPLAY_ROWS, MIN_COLUMNS } from '../src/display.js';

test('active blocks remain distinct when touching settled blocks of the same type', () => {
  const game = new Tetris();
  game.active = { type: 'O', matrix: [[1, 1], [1, 1]], x: 4, y: 17 };
  game.board[19][4] = 'O';
  game.board[19][5] = 'O';
  const before = JSON.stringify(game.board);
  const rows = renderFrame(game).split('\n');
  assert.equal(rows[19].slice(1, 21), '        <><>        ');
  assert.equal(rows[20].slice(1, 21), '        <><>        ');
  assert.equal(rows[21].slice(1, 21), '        [][]        ');
  assert.ok(rows.some(row => row.includes('<> falling; [] settled')));
  assert.equal(rows.length, DISPLAY_ROWS);
  assert.ok(rows.every(row => row.length <= MIN_COLUMNS));
  assert.equal(JSON.stringify(game.board), before);
});

test('locked blocks and game-over display use settled glyphs', () => {
  const game = new Tetris();
  game.active = { type: 'O', matrix: [[1, 1], [1, 1]], x: 4, y: 18 };
  game.lock();
  assert.equal(renderFrame(game).split('\n')[20].slice(1, 21), '        [][]        ');
  game.active = null;
  game.gameOver = true;
  const rows = renderFrame(game).split('\n');
  assert.equal(rows.length, DISPLAY_ROWS);
  assert.equal(rows[21].slice(1, 21), '        [][]        ');
  assert.ok(rows.at(-1).startsWith('GAME OVER'));
  assert.ok(rows.slice(2, 22).every(row => !row.slice(1, 21).includes('<>')));
});

test('every piece and game-over frame fit the terminal with controls and stats visible', () => {
  const game = new Tetris();
  for (const type of Object.keys(SHAPES)) {
    game.active = { type, matrix: SHAPES[type], x: 3, y: 0 };
    const frame = renderFrame(game);
    const rows = frame.split('\n');
    assert.equal(rows.length, 24);
    // The UI reserves the final column to avoid automatic wrapping.
    assert.ok(rows.every(row => row.length < MIN_COLUMNS));
    assert.equal((frame.match(/<>/g) ?? []).length, 5); // four cells plus legend
    for (const label of ['Score: 0', 'Lines: 0', 'Level: 1', 'Next:',
      'Left / A', 'Right / D', 'Down / S', 'Up / W / X', 'Z:', 'Space:', 'R:', 'Q / Ctrl-C']) {
      assert.ok(frame.includes(label), label);
    }
  }
  game.active = null;
  game.gameOver = true;
  const rows = renderFrame(game).split('\n');
  assert.equal(rows.length, 24);
  assert.ok(rows.every(row => row.length < MIN_COLUMNS));
  assert.equal(rows.at(-1), 'GAME OVER - R to restart, Q to quit');
});
