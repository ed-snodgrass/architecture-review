import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { PassThrough } from 'node:stream';
import { EventEmitter } from 'node:events';
import { Game, SHAPES } from '../src/game.js';
import { MIN_COLUMNS, startTerminalGame } from '../src/terminal.js';

function session(t, game = new Game()) {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const input = new PassThrough();
  Object.assign(input, { isTTY: true, isRaw: false });
  input.setRawMode = value => { input.isRaw = value; };
  input.pause();
  const output = new EventEmitter();
  Object.assign(output, { isTTY: true, columns: MIN_COLUMNS, rows: 24 });
  const writes = [];
  output.write = text => { writes.push(text); };
  const stop = startTerminalGame({ input, output, game });
  t.after(() => { stop(); input.destroy(); });
  // Feed bytes through readline rather than synthesizing keypress events.
  const press = async bytes => {
    input.write(bytes);
    await new Promise(resolve => setImmediate(resolve));
  };
  return { input, output, writes, press };
}

function piece(game, type, x, y) {
  game.active = {
    type, x, y,
    matrix: SHAPES[type].map(row => [...row].map(cell => cell === '.' ? null : cell)),
  };
}

test('npm start invokes the entry point and rejects redirected input cleanly', () => {
  const result = spawnSync('npm', ['start'], {
    cwd: new URL('..', import.meta.url), encoding: 'utf8', timeout: 10000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 1);
  assert.match(result.stdout, /node src\/main.js/);
  assert.match(result.stdout, /requires an interactive terminal/);
  assert.equal(result.stderr, '');
  assert.ok(!result.stdout.includes('\x1b'));
});

test('raw arrow, space and quit bytes drive real gameplay and scoring', async t => {
  const game = new Game();
  piece(game, 'T', 3, 0);
  const { input, writes, press } = session(t, game);
  assert.equal(input.isRaw, true);
  await press('\x1b[D');
  assert.equal(game.active.x, 2);
  await press('\x1b[C');
  assert.equal(game.active.x, 3);
  const matrix = structuredClone(game.active.matrix);
  await press('\x1b[A');
  assert.notDeepEqual(game.active.matrix, matrix);
  await press('\x1b[B');
  assert.equal(game.active.y, 1);
  assert.equal(game.score, 1);
  t.mock.timers.tick(1000);
  assert.equal(game.active.y, 2);
  assert.equal(game.score, 1, 'gravity earns no drop points');
  await press(' ');
  assert.ok(game.score > 1);
  assert.equal(game.board.flat().filter(Boolean).length, 4);
  assert.equal(game.active.y, 0);
  for (const frame of writes.filter(text => text.startsWith('\x1b[H'))) {
    const rows = frame.replace(/\x1b\[[0-9;?]*[A-Za-z]/g, '').split('\r\n');
    assert.equal(rows.length, 24);
    assert.ok(rows.every(row => row.length <= MIN_COLUMNS));
    assert.match(rows[0], /Score:/);
    assert.match(rows[23], /Q: quit/);
  }
  await press('q');
  assert.equal(input.isRaw, false);
  const count = writes.length;
  t.mock.timers.tick(10000);
  assert.equal(writes.length, count);
});

test('keyboard lock clears lines, displays score, then blocked spawn ends the session', async t => {
  const game = new Game();
  game.board[18] = Array(10).fill('J');
  game.board[19] = Array(10).fill('J');
  for (const y of [18, 19]) {
    game.board[y][0] = null;
    game.board[y][1] = null;
  }
  piece(game, 'O', 0, 18);
  const { input, writes, press } = session(t, game);
  await press(' ');
  assert.equal(game.lines, 2);
  assert.equal(game.score, 300);
  assert.ok(game.board.flat().every(cell => cell === null));
  assert.match(writes.at(-1), /Score:300 Lines:2/);
  // Block every possible spawn footprint without making complete rows,
  // which would be cleared by the locking piece before the spawn check.
  game.board[0].fill('J', 3, 7);
  game.board[1].fill('J', 3, 7);
  piece(game, 'O', 0, 18);
  await press(' ');
  assert.equal(game.gameOver, true);
  assert.equal(input.isRaw, false);
  assert.match(writes.at(-1), /GAME OVER.*Score:300/);
  assert.equal(writes.at(-1).split('\r\n').length, 24);
});

test('undersized startup is rejected without changing terminal state', () => {
  for (const [columns, rows] of [[MIN_COLUMNS - 1, 24], [MIN_COLUMNS, 23]]) {
    let message = '';
    const input = { isTTY: true, setRawMode: () => assert.fail('must not enable raw mode') };
    const output = { isTTY: true, columns, rows, write: text => { message += text; } };
    assert.equal(startTerminalGame({ input, output }), false);
    assert.match(message, /at least .* columns by 24 rows/);
  }
});

test('resize pauses gravity and input until the full 24-row display fits again', async t => {
  const game = new Game();
  piece(game, 'O', 3, 0);
  const { output, writes, press } = session(t, game);
  output.rows = 23;
  output.emit('resize');
  assert.match(writes.at(-1), /Resize to at least/);
  assert.equal(writes.at(-1).split('\r\n').length, 1);
  t.mock.timers.tick(5000);
  await press('\x1b[D');
  assert.equal(game.active.x, 3);
  assert.equal(game.active.y, 0);
  output.rows = 24;
  output.emit('resize');
  assert.equal(writes.at(-1).split('\r\n').length, 24);
  t.mock.timers.tick(1000);
  assert.equal(game.active.y, 1);
  await press('\x03');
  assert.ok(writes.at(-1).includes('\x1b[?1049l'));
});
