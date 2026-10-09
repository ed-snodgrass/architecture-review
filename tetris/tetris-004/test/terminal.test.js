import test from 'node:test';
import assert from 'node:assert/strict';
import { Game } from '../src/game.js';
import { CONTROLS, MIN_COLUMNS, renderFrame, handleKey, startTerminalGame } from '../src/terminal.js';

test('complete frame uses 24 rows with board, score, preview and controls', () => {
  const game = new Game();
  const frame = renderFrame(game).split('\n');
  assert.equal(frame.length, 24);
  assert.match(frame[0], /Score:0 Lines:0 Level:1 Next:/);
  assert.equal(frame[1], '+--------------------+');
  assert.equal(frame[22], frame[1]);
  assert.equal(frame[23], CONTROLS);
  assert.equal((frame.join('').match(/\[\]/g) || []).length, 4);
  assert.ok(frame.every(row => row.length <= MIN_COLUMNS));
});

test('render overlays active cells without modifying the settled board', () => {
  const game = new Game();
  game.board[19][0] = 'J';
  const before = structuredClone(game.board);
  assert.ok(renderFrame(game).split('\n')[21].startsWith('|[]'));
  assert.deepEqual(game.board, before);
});

test('game over and large scores remain within the frame dimensions', () => {
  const game = new Game();
  game.gameOver = true;
  game.active = null;
  game.score = Number.MAX_SAFE_INTEGER;
  const rows = renderFrame(game).split('\n');
  assert.equal(rows.length, 24);
  assert.match(rows[0], /^GAME OVER/);
  assert.equal(rows[23], CONTROLS);
  assert.ok(rows.every(row => row.length <= MIN_COLUMNS));
});

test('arrow and space keys dispatch to the gameplay actions', () => {
  const calls = [];
  const game = {
    move: (...args) => calls.push(['move', ...args]),
    rotate: () => calls.push(['rotate']),
    softDrop: () => calls.push(['softDrop']),
    hardDrop: () => calls.push(['hardDrop']),
  };
  for (const name of ['left', 'right', 'up', 'down', 'space']) {
    assert.equal(handleKey(game, { name }), 'update');
  }
  assert.deepEqual(calls, [['move', -1], ['move', 1], ['rotate'], ['softDrop'], ['hardDrop']]);
  assert.equal(handleKey(game, { name: 'q' }), 'quit');
  assert.equal(handleKey(game, { name: 'c', ctrl: true }), 'quit');
  assert.equal(handleKey(game, { name: 'a' }), 'ignored');
  game.gameOver = true;
  assert.equal(handleKey(game, { name: 'space' }), 'ignored');
  assert.equal(calls.length, 5);
});

test('noninteractive startup gives a useful error without enabling raw mode', () => {
  let message = '';
  assert.equal(startTerminalGame({ input: { isTTY: false }, output: { write: text => { message += text; } } }), false);
  assert.match(message, /interactive terminal/);
});
