import test from 'node:test';
import assert from 'node:assert/strict';
import { PassThrough } from 'node:stream';
import { EventEmitter } from 'node:events';
import { MIN_COLUMNS, startTerminalGame } from '../src/terminal.js';

test('quitting pauses initially idle input so the CLI can exit', () => {
  const input = new PassThrough();
  Object.assign(input, { isTTY: true, isRaw: false });
  input.setRawMode = value => { input.isRaw = value; };
  assert.equal(input.isPaused(), false);
  assert.equal(input.readableFlowing, null);
  const output = new EventEmitter();
  Object.assign(output, { isTTY: true, columns: MIN_COLUMNS, rows: 24, write() {} });
  const stop = startTerminalGame({ input, output });
  try {
    input.emit('keypress', 'q', { name: 'q' });
    assert.equal(input.isPaused(), true);
    assert.equal(input.isRaw, false);
    assert.equal(input.listenerCount('data'), 0);
  } finally {
    stop();
    input.destroy();
  }
});
