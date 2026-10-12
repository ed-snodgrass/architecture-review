const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { spawnSync } = require('node:child_process');
const { EventEmitter } = require('node:events');
const { PassThrough } = require('node:stream');
const { createRequire } = require('node:module');
const path = require('node:path');
const vm = require('node:vm');

// Exercise the entry point with a terminal and observable mechanics, without
// depending on rendering (a later task), real-time gravity, or random pieces.
// Node's VM module linker needs this flag; the wrapper keeps ordinary
// `node --test test/*.test.cjs` usable as well.
if (!vm.SourceTextModule) {
  test('terminal control contract in an isolated VM', () => {
    const result = spawnSync(process.execPath,
      ['--experimental-vm-modules', '--test', __filename], {
        encoding: 'utf8', timeout: 15000,
      });
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stdout + result.stderr);
  });
} else {
  const root = path.resolve(__dirname, '..');
  const requireFromRoot = createRequire(path.join(root, 'package.json'));

  async function launch() {
    const input = new PassThrough();
    input.isTTY = true;
    input.isRaw = false;
    const rawChanges = [];
    input.setRawMode = enabled => {
      input.isRaw = enabled;
      rawChanges.push(enabled);
      return input;
    };
    const output = new PassThrough();
    output.isTTY = true;
    output.columns = 80;
    output.rows = 24;
    output.resume();
    const proc = new EventEmitter();
    const exits = [];
    Object.assign(proc, {
      stdin: input, stdout: output, stderr: output,
      env: { TERM: 'xterm' }, argv: [process.execPath, 'src/main.js'],
      exit: code => exits.push(code ?? 0), cwd: () => root,
    });
    const calls = [];
    const game = {
      board: Array.from({ length: 20 }, () => Array(10).fill(null)),
      active: { type: 'T', x: 3, y: 0, cells: [] },
      score: 0, gameOver: false,
    };
    const mechanics = {
      createGame: () => { calls.push(['createGame']); return game; },
      getActiveCells: () => [{ x: 3, y: 0 }, { x: 4, y: 0 }, { x: 5, y: 0 }, { x: 4, y: 1 }],
      move: (state, dx, dy) => { calls.push(['move', dx, dy]); return true; },
      rotate: () => { calls.push(['rotate']); return true; },
      tick: () => { calls.push(['tick']); },
    };
    const timers = new Set();
    const schedule = () => { const token = {}; timers.add(token); return token; };
    const clear = token => timers.delete(token);
    const context = vm.createContext({
      process: proc, console: { log() {}, error() {} }, Buffer,
      setInterval: schedule, clearInterval: clear,
      setTimeout: schedule, clearTimeout: clear,
      setImmediate, clearImmediate, Date, performance,
    });
    const cache = new Map();
    async function link(specifier, parent) {
      const file = specifier.startsWith('.')
        ? path.resolve(path.dirname(parent.identifier), specifier) : specifier;
      if (cache.has(file)) return cache.get(file);
      let module;
      if (file === path.join(root, 'src/game.js')) {
        module = new vm.SyntheticModule(Object.keys(mechanics), function () {
          for (const [name, value] of Object.entries(mechanics)) this.setExport(name, value);
        }, { context, identifier: file });
      } else if (path.isAbsolute(file)) {
        module = new vm.SourceTextModule(readFileSync(file, 'utf8'), { context, identifier: file });
      } else {
        const builtin = requireFromRoot(file);
        const exports = { ...builtin, default: builtin };
        module = new vm.SyntheticModule(Object.keys(exports), function () {
          for (const [name, value] of Object.entries(exports)) this.setExport(name, value);
        }, { context, identifier: file });
      }
      cache.set(file, module);
      if (module instanceof vm.SourceTextModule) await module.link(link);
      return module;
    }
    const entry = new vm.SourceTextModule(readFileSync(path.join(root, 'src/main.js'), 'utf8'), {
      context, identifier: path.join(root, 'src/main.js'),
    });
    await entry.link(link);
    await entry.evaluate();
    const settle = () => new Promise(resolve => setImmediate(resolve));
    await settle();
    return {
      input, proc, calls, exits, timers, rawChanges,
      async send(bytes) { input.write(bytes); await settle(); },
      async stop(event) { proc.emit(event); await settle(); },
      dispose() { input.destroy(); output.destroy(); timers.clear(); },
    };
  }

  test('interactive launch enables raw input and starts the game', async t => {
    const session = await launch();
    t.after(() => session.dispose());
    assert.equal(session.input.isRaw, true, 'keys must work without pressing Enter');
    assert.ok(session.calls.some(call => call[0] === 'createGame'));
    assert.equal(session.exits.length, 0);
  });

  for (const [label, bytes, expected] of [
    ['left arrow', '\x1b[D', ['move', -1, 0]],
    ['right arrow', '\x1b[C', ['move', 1, 0]],
    ['down arrow', '\x1b[B', ['move', 0, 1]],
    ['up arrow', '\x1b[A', ['rotate']],
  ]) {
    test(`${label} controls the active piece without Enter`, async t => {
      const session = await launch();
      t.after(() => session.dispose());
      session.calls.length = 0;
      await session.send(bytes);
      const actions = session.calls.filter(call => ['move', 'rotate'].includes(call[0]));
      assert.deepEqual(actions, [expected], 'one key must produce exactly one intended action');
      assert.equal(session.exits.length, 0);
    });
  }

  test('unbound text does not move, rotate, or exit', async t => {
    const session = await launch();
    t.after(() => session.dispose());
    session.calls.length = 0;
    await session.send('~');
    assert.deepEqual(session.calls.filter(call => ['move', 'rotate'].includes(call[0])), []);
    assert.equal(session.exits.length, 0);
  });

  for (const reason of ['Ctrl+C', 'SIGINT', 'SIGTERM', 'input end']) {
    test(`${reason} restores cooked input and stops the session`, async t => {
      const session = await launch();
      t.after(() => session.dispose());
      assert.equal(session.input.isRaw, true, 'exercise cleanup after raw mode was entered');
      if (reason === 'Ctrl+C') await session.send('\x03');
      else if (reason === 'input end') {
        session.input.end();
        await new Promise(resolve => setImmediate(resolve));
      } else await session.stop(reason);
      assert.equal(session.input.isRaw, false, 'the shell must not inherit raw mode');
      assert.equal(session.rawChanges.at(-1), false);
      assert.equal(session.timers.size, 0, 'gravity/redraw timers must be cancelled');
      assert.ok(session.exits.length > 0 || session.input.isPaused(),
        'exit or release input so the terminal session can end');
      const before = session.calls.filter(call => ['move', 'rotate'].includes(call[0])).length;
      session.input.emit('data', Buffer.from('\x1b[D'));
      await new Promise(resolve => setImmediate(resolve));
      assert.equal(session.calls.filter(call => ['move', 'rotate'].includes(call[0])).length, before,
        'input after shutdown must not control the game');
    });
  }
}
