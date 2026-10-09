import test from 'node:test';
import assert from 'node:assert/strict';
import { PassThrough } from 'node:stream';
import { EventEmitter } from 'node:events';
import { Game } from '../src/game.js';
import { MIN_COLUMNS, startTerminalGame } from '../src/terminal.js';

function terminal(t, game = new Game(), raw = false) {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const input = new PassThrough();
  input.isTTY = true;
  input.isRaw = raw;
  input.setRawMode = value => { input.isRaw = value; };
  input.pause();
  const output = new EventEmitter();
  Object.assign(output, { isTTY: true, columns: MIN_COLUMNS, rows: 24, text: '' });
  output.write = text => { output.text += text; };
  const signals = ['SIGINT', 'SIGTERM', 'exit'];
  const before = signals.map(name => process.listenerCount(name));
  const stop = startTerminalGame({ input, output, game });
  t.after(() => { stop(); input.destroy(); });
  const assertClean = () => {
    assert.equal(input.isRaw, raw);
    assert.equal(input.isPaused(), true);
    assert.equal(input.listenerCount('keypress'), 0);
    assert.equal(input.listenerCount('data'), 0);
    assert.equal(input.listenerCount('newListener'), 0);
    assert.equal(output.listenerCount('resize'), 0);
    assert.deepEqual(signals.map(name => process.listenerCount(name)), before);
    assert.ok(output.text.includes('\x1b[?25h\x1b[?1049l'));
    const text = output.text;
    t.mock.timers.tick(10000);
    assert.equal(output.text, text, 'no pending gravity redraws');
  };
  return { input, output, stop, assertClean };
}

for (const key of [{ name: 'q' }, { name: 'c', ctrl: true }]) {
  test(`quit via ${key.name} restores terminal and removes handlers`, t => {
    const session = terminal(t);
    session.input.emit('keypress', '', key);
    session.assertClean();
    const text = session.output.text;
    session.stop();
    assert.equal(session.output.text, text, 'cleanup is idempotent');
  });
}

test('explicit cleanup preserves existing raw mode and input listeners', t => {
  const session = terminal(t, new Game(), true);
  const listener = () => {};
  session.input.on('keypress', listener);
  session.stop();
  assert.equal(session.input.isRaw, true);
  assert.deepEqual(session.input.listeners('keypress'), [listener]);
  session.input.off('keypress', listener);
  session.assertClean();
});

for (const trigger of ['keyboard', 'gravity']) {
  test(`game over from ${trigger} cleans up and leaves the final frame visible`, t => {
    const game = new Game();
    const end = () => { game.gameOver = true; game.active = null; };
    game.hardDrop = end;
    game.tick = end;
    const session = terminal(t, game);
    if (trigger === 'keyboard') session.input.emit('keypress', '', { name: 'space' });
    else t.mock.timers.tick(game.gravityInterval);
    session.assertClean();
    const finalFrame = session.output.text.split('\x1b[?1049l')[1];
    assert.match(finalFrame, /GAME OVER/);
    assert.equal(finalFrame.split('\r\n').length, 24);
  });
}

test('an already finished game cleans up at startup', t => {
  const game = new Game();
  game.gameOver = true;
  terminal(t, game).assertClean();
});

test('SIGTERM cleans up and sets the conventional exit status', t => {
  const session = terminal(t);
  const previous = process.exitCode;
  try {
    process.emit('SIGTERM', 'SIGTERM');
    assert.equal(process.exitCode, 143);
    session.assertClean();
  } finally {
    process.exitCode = previous;
  }
});
