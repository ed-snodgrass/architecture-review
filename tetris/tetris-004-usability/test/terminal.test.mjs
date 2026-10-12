import test from 'node:test';
import assert from 'node:assert/strict';
import { PassThrough } from 'node:stream';
import { EventEmitter } from 'node:events';
import { Game } from '../src/game.mjs';
import { startTerminal } from '../src/terminal.mjs';

function fixture(t, { raw = false } = {}) {
  const input = new PassThrough();
  input.isTTY = true;
  input.isRaw = raw;
  const rawModes = [];
  input.setRawMode = value => { rawModes.push(value); input.isRaw = value; };
  const output = new EventEmitter();
  Object.assign(output, { isTTY: true, columns: 80, rows: 24 });
  let text = '';
  output.write = chunk => { text += chunk; };
  const lifecycle = new EventEmitter();
  const timers = new Map();
  let nextTimer = 0;
  const errors = [];
  const game = new Game({ nextPiece: () => 'T' });
  const session = startTerminal({
    input, output, lifecycle, game,
    setTimer: callback => { timers.set(++nextTimer, callback); return nextTimer; },
    clearTimer: id => timers.delete(id),
    reportError: error => errors.push(error),
  });
  t.after(() => { session.cleanup(); input.destroy(); });
  return { input, output, lifecycle, game, session, timers, errors, rawModes,
    text: () => text,
    tick: () => { const [id, callback] = timers.entries().next().value; timers.delete(id); callback(); },
  };
}

function assertRestored(f, raw = false) {
  assert.equal(f.input.isRaw, raw);
  assert.equal(f.input.isPaused(), true);
  assert.equal(f.timers.size, 0);
  assert.equal(f.input.listenerCount('keypress'), 0);
  assert.equal(f.output.listenerCount('resize'), 0);
  for (const name of ['exit', 'SIGINT', 'SIGTERM', 'SIGHUP', 'uncaughtException']) {
    assert.equal(f.lifecycle.listenerCount(name), 0);
  }
  assert.ok(f.text().endsWith('\x1b[?25h\x1b[?1049l'));
}

test('raw byte input maps arrows, soft drop and space to gameplay immediately', t => {
  const f = fixture(t);
  assert.equal(f.input.isRaw, true);
  const x = f.game.active.x;
  // A split escape sequence must be decoded as one arrow, not stray keys.
  f.input.write('\x1b[');
  f.input.write('D');
  assert.equal(f.game.active.x, x - 1);
  f.input.write('\x1b[C');
  assert.equal(f.game.active.x, x);
  const shape = [...f.game.active.shape];
  f.input.write('\x1b[A');
  assert.notDeepEqual(f.game.active.shape, shape);
  f.input.write('\x1b[B');
  assert.equal(f.game.active.y, 1);
  assert.equal(f.game.score, 1);
  f.input.write(' ');
  assert.equal(f.game.board.flat().filter(Boolean).length, 4);
  const state = JSON.stringify(f.game);
  f.input.write('z');
  f.input.write('\x1b[1;5D'); // Ctrl-left is not a move.
  assert.equal(JSON.stringify(f.game), state);
});

for (const key of ['q', 'Q', '\x03']) {
  test(`quit input ${JSON.stringify(key)} restores the terminal exactly once`, t => {
    const f = fixture(t, { raw: true });
    f.input.write(key);
    assertRestored(f, true);
    const text = f.text();
    f.session.cleanup();
    assert.equal(f.text(), text);
    assert.deepEqual(f.rawModes, [true, true]);
  });
}

for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP', 'exit']) {
  test(`${signal} cleans up timers, listeners, screen and raw mode`, t => {
    const f = fixture(t);
    f.lifecycle.emit(signal);
    assertRestored(f);
  });
}

for (const event of ['end', 'close']) {
  test(`input ${event} restores the terminal`, t => {
    const f = fixture(t);
    f.input.emit(event);
    assertRestored(f);
  });
}

for (const source of ['input', 'output', 'lifecycle']) {
  test(`${source} error restores the terminal and reports failure`, t => {
    const f = fixture(t);
    const error = new Error('test failure');
    f[source].emit(source === 'lifecycle' ? 'uncaughtException' : 'error', error);
    assertRestored(f);
    assert.equal(f.lifecycle.exitCode, 1);
    assert.deepEqual(f.errors, [error]);
  });
}

test('resize pauses input and gravity, resumes on enlargement, and permits quit', t => {
  const f = fixture(t);
  f.output.columns = 40;
  f.output.emit('resize');
  assert.match(f.text(), /Paused: resize/);
  const state = JSON.stringify(f.game);
  f.input.write(' ');
  f.tick();
  assert.equal(JSON.stringify(f.game), state);
  f.output.columns = 80;
  f.output.emit('resize');
  f.tick();
  assert.equal(f.game.active.y, 1);
  f.output.rows = 10;
  f.input.write('q');
  assertRestored(f);
});

test('resize warning fits even a narrow terminal without wrapping', t => {
  const f = fixture(t);
  for (const columns of [40, 20, 1]) {
    f.output.columns = columns;
    f.output.emit('resize');
    const frame = f.text().split('\x1b[H\x1b[2J').at(-1);
    assert.ok(frame.length <= columns);
    assert.ok(!frame.includes('\n'));
  }
});

test('game over stops gravity and gameplay but still accepts quit', t => {
  const f = fixture(t);
  f.game.board[0][4] = 'O';
  f.input.write(' ');
  assert.equal(f.game.gameOver, true);
  assert.equal(f.timers.size, 0);
  const state = JSON.stringify(f.game);
  f.input.write('\x1b[D ');
  assert.equal(JSON.stringify(f.game), state);
  f.input.write('q');
  assertRestored(f);
});

test('timer exceptions clean up and report rather than leaving raw mode enabled', t => {
  const f = fixture(t);
  f.game.step = () => { throw new Error('gravity failed'); };
  f.tick();
  assertRestored(f);
  assert.equal(f.errors[0].message, 'gravity failed');
});

test('non-interactive launch rejects before changing terminal state', () => {
  assert.throws(() => startTerminal({ input: { isTTY: false }, output: { isTTY: true } }),
    /requires an interactive terminal/);
});
