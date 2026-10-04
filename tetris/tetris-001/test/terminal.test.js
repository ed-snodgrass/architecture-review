import test from 'node:test';
import assert from 'node:assert/strict';
import { PassThrough } from 'node:stream';
import { EventEmitter } from 'node:events';
import { Game } from '../src/engine.js';
import { render, startTerminal, MIN_COLUMNS } from '../src/terminal.js';

function terminal(game) {
  const input = new PassThrough();
  input.isTTY = true;
  input.setRawMode = value => { input.isRaw = value; };
  const output = new PassThrough();
  Object.assign(output, { isTTY: true, columns: MIN_COLUMNS, rows: 24 });
  let text = '';
  output.on('data', chunk => { text += chunk.toString(); });
  const signals = new EventEmitter();
  const stop = startTerminal({ input, output, signals, game });
  return { input, output, signals, stop, text: () => text,
    key: name => input.emit('keypress', '', { name }) };
}

test('playing, paused and game-over frames fit the terminal budget', () => {
  const game = new Game();
  for (const state of ['playing', 'paused', 'over']) {
    game.gameOver = state === 'over';
    const lines = render(game, { paused: state === 'paused' }).split('\n');
    assert.equal(lines.length, 22);
    assert.ok(lines.every(line => line.length <= MIN_COLUMNS));
    assert.match(lines.join('\n'), /Score: 0/);
    if (game.gameOver) assert.match(lines.join('\n'), /GAME OVER/);
  }
});

test('keyboard controls, pause, restart and quit restore terminal state', () => {
  const game = new Game();
  const ui = terminal(game);
  try {
    const x = game.active.x;
    ui.key('left');
    assert.equal(game.active.x, x - 1);
    ui.key('p');
    ui.key('right');
    assert.equal(game.active.x, x - 1);
    ui.key('p');
    ui.key('space');
    assert.ok(game.score > 0);
    ui.key('r');
    assert.equal(game.score, 0);
    ui.key('q');
    assert.equal(ui.input.isRaw, false);
    assert.equal(ui.signals.listenerCount('SIGTERM'), 0);
    assert.ok(ui.text().endsWith('\x1b[?25h\x1b[?1049l'));
  } finally { ui.stop(); }
});

test('gravity advances and pause stops the timer', async () => {
  const game = new Game();
  Object.defineProperty(game, 'gravityMs', { value: 10 });
  const ui = terminal(game);
  try {
    await new Promise(resolve => setTimeout(resolve, 35));
    assert.ok(game.active.y > 0);
    ui.key('p');
    const y = game.active.y;
    await new Promise(resolve => setTimeout(resolve, 35));
    assert.equal(game.active.y, y);
  } finally { ui.stop(); }
});

test('undersized terminals suspend play and signals clean up', () => {
  const game = new Game();
  const ui = terminal(game);
  try {
    ui.output.columns = 30;
    ui.output.emit('resize');
    const x = game.active.x;
    ui.key('left');
    assert.equal(game.active.x, x);
    assert.match(ui.text(), /Resize terminal/);
    ui.signals.emit('SIGTERM');
    assert.equal(ui.input.isRaw, false);
  } finally { ui.stop(); }
});
