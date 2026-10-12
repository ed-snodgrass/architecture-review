const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { spawnSync } = require('node:child_process');
const { EventEmitter } = require('node:events');
const { PassThrough } = require('node:stream');
const { createRequire } = require('node:module');
const path = require('node:path');
const vm = require('node:vm');

// Black-box rendering contract through the existing terminal entry point.
// No renderer export, block glyph, colour, border style, or score formula is
// required. Compare visible screens for controlled states, not ANSI byte counts.
if (!vm.SourceTextModule) {
  test('24-row terminal rendering contract in an isolated VM', () => {
    const result = spawnSync(process.execPath,
      ['--experimental-vm-modules', '--test', __filename], {
        encoding: 'utf8', timeout: 20000,
      });
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stdout + result.stderr);
  });
} else {
  const root = path.resolve(__dirname, '..');
  const requireFromRoot = createRequire(path.join(root, 'package.json'));

  // Small fixed-size terminal model: common cursor, erase, SGR and OSC commands.
  // Reject unsupported control sequences rather than silently miscounting rows.
  class Screen {
    constructor(columns = 80, rows = 24) {
      this.columns = columns;
      this.rows = rows;
      this.cells = Array.from({ length: rows }, () => Array(columns).fill(' '));
      this.x = this.y = this.maxRow = this.scrolls = 0;
      this.pending = '';
      this.saved = [0, 0];
    }
    write(chunk) {
      this.pending += chunk.toString();
      while (this.pending.length) {
        let match;
        if (this.pending.startsWith('\x1b[')) {
          match = /^\x1b\[([0-9;?]*)([ -/]*)([@-~])/.exec(this.pending);
          if (!match) break;
          this.pending = this.pending.slice(match[0].length);
          const args = match[1].replace(/^\?/, '').split(';').map(n => Number(n));
          const n = args[0] || 1;
          switch (match[3]) {
            case 'H': case 'f': this.y = (args[0] || 1) - 1; this.x = (args[1] || 1) - 1; break;
            case 'A': this.y = Math.max(0, this.y - n); break;
            case 'B': this.y += n; break;
            case 'C': this.x += n; break;
            case 'D': this.x = Math.max(0, this.x - n); break;
            case 'E': this.y += n; this.x = 0; break;
            case 'F': this.y = Math.max(0, this.y - n); this.x = 0; break;
            case 'G': this.x = n - 1; break;
            case 'd': this.y = n - 1; break;
            case 'J': {
              const mode = args[0];
              for (let y = 0; y < this.rows; y++) for (let x = 0; x < this.columns; x++) {
                if (mode === 2 || mode === 3 ||
                    (mode === 0 && (y > this.y || (y === this.y && x >= this.x))) ||
                    (mode === 1 && (y < this.y || (y === this.y && x <= this.x)))) {
                  this.cells[y][x] = ' ';
                }
              }
              break;
            }
            case 'K':
              for (let x = 0; x < this.columns; x++) {
                if (args[0] === 2 || (args[0] === 0 && x >= this.x) ||
                    (args[0] === 1 && x <= this.x)) this.cells[this.y][x] = ' ';
              }
              break;
            case 's': this.saved = [this.x, this.y]; break;
            case 'u': [this.x, this.y] = this.saved; break;
            case 'm': case 'h': case 'l': break;
            default: throw new Error(`Unsupported terminal sequence ${JSON.stringify(match[0])}`);
          }
          continue;
        }
        if (this.pending.startsWith('\x1b]')) {
          match = /^\x1b\][\s\S]*?(?:\x07|\x1b\\)/.exec(this.pending);
          if (!match) break;
          this.pending = this.pending.slice(match[0].length);
          continue;
        }
        const char = [...this.pending][0];
        this.pending = this.pending.slice(char.length);
        if (char === '\r') this.x = 0;
        else if (char === '\n') { this.y++; this.x = 0; }
        else if (char === '\b') this.x = Math.max(0, this.x - 1);
        else if (char === '\x07') continue;
        else {
          assert.notEqual(char, '\x1b', 'unsupported escape sequence');
          if (this.x >= this.columns) { this.x = 0; this.y++; }
          this.maxRow = Math.max(this.maxRow, this.y + 1);
          while (this.y >= this.rows) {
            this.cells.shift(); this.cells.push(Array(this.columns).fill(' '));
            this.y--; this.scrolls++;
          }
          this.cells[this.y][this.x++] = char;
        }
      }
    }
    lines() { return this.cells.map(row => row.join('').trimEnd()); }
  }

  async function launch(configure = () => {}, dimensions = { columns: 80, rows: 24 }) {
    const api = await import('../src/game.js');
    const game = api.createGame({ pieceSequence: ['O', 'T'] });
    configure(game, api);
    const screen = new Screen(dimensions.columns, dimensions.rows);
    const input = new PassThrough();
    Object.assign(input, { isTTY: true, isRaw: false });
    input.setRawMode = value => { input.isRaw = value; return input; };
    const output = new PassThrough();
    Object.assign(output, { isTTY: true, ...dimensions });
    output.on('data', chunk => screen.write(chunk));
    const proc = new EventEmitter();
    const exits = [];
    Object.assign(proc, {
      stdin: input, stdout: output, stderr: output,
      env: { TERM: 'xterm', COLUMNS: '80', LINES: '24' },
      argv: [process.execPath, 'src/main.js'], cwd: () => root,
      exit: code => exits.push(code ?? 0),
    });
    const timers = new Map();
    let now = 0;
    class Clock extends Date { static now() { return now; } }
    const context = vm.createContext({
      process: proc, console: { log: (...args) => output.write(args.join(' ') + '\n'), error() {} },
      Buffer, Date: Clock, performance,
      setInterval: fn => { const token = {}; timers.set(token, fn); return token; },
      clearInterval: token => timers.delete(token),
      setTimeout: fn => { const token = {}; timers.set(token, fn); return token; },
      clearTimeout: token => timers.delete(token), setImmediate, clearImmediate,
    });
    const cache = new Map();
    async function link(specifier, parent) {
      const file = specifier.startsWith('.')
        ? path.resolve(path.dirname(parent.identifier), specifier) : specifier;
      if (cache.has(file)) return cache.get(file);
      let module;
      if (file === path.join(root, 'src/game.js')) {
        const exports = { ...api, createGame: () => game };
        module = new vm.SyntheticModule(Object.keys(exports), function () {
          for (const [name, value] of Object.entries(exports)) this.setExport(name, value);
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
    const entry = await link('./src/main.js', { identifier: path.join(root, 'entry.js') });
    await entry.evaluate();
    await new Promise(resolve => setImmediate(resolve));
    return {
      game, screen, input, exits, timers,
      async resize(columns, rows) {
        screen.cells = Array.from({ length: rows }, (_, y) =>
          Array.from({ length: columns }, (_, x) => screen.cells[y]?.[x] ?? ' '));
        screen.columns = columns;
        screen.rows = rows;
        screen.x = Math.min(screen.x, columns - 1);
        screen.y = Math.min(screen.y, rows - 1);
        Object.assign(output, { columns, rows });
        output.emit('resize');
        await new Promise(resolve => setImmediate(resolve));
      },
      async send(bytes) {
        input.write(bytes);
        await new Promise(resolve => setImmediate(resolve));
      },
      // Elapse time without firing gravity: catches stale clock baselines on resize.
      elapse(ms) { now += ms; },
      async advance(ms = 50) {
        now += ms;
        for (const fn of [...timers.values()]) fn();
        await new Promise(resolve => setImmediate(resolve));
      },
      dispose() { proc.emit('SIGTERM'); input.destroy(); output.destroy(); timers.clear(); },
    };
  }

  function fits(screen) {
    assert.equal(screen.pending, '', 'complete terminal escape sequences');
    assert.ok(screen.maxRow <= 24, `display writes to row ${screen.maxRow}, exceeding 24`);
    assert.equal(screen.scrolls, 0, 'redrawing must not scroll the board off screen');
  }
  async function snapshot(configure, dimensions) {
    const session = await launch(configure, dimensions);
    try { await session.advance(); fits(session.screen); return session.screen.lines(); }
    finally { session.dispose(); }
  }
  const blank = game => { game.active.cells = []; };
  const state = game => JSON.parse(JSON.stringify({
    board: game.board, active: game.active, score: game.score,
    gameOver: game.gameOver, pieceIndex: game.pieceIndex,
  }));

  for (const [label, columns, rows] of [
    ['narrow', 39, 24], ['short', 80, 23],
  ]) {
    test(`${label} terminal pauses gravity from launch and after resize`, async t => {
      const session = await launch(undefined, { columns, rows });
      t.after(() => session.dispose());
      const initial = state(session.game);
      assert.match(session.screen.lines().join('\n'), /resize|needs/i, 'display a size warning');
      await session.advance(10000);
      assert.deepEqual(state(session.game), initial, 'no unseen falling at startup');
      await session.resize(80, 24);
      await session.advance(session.game.fallIntervalMs);
      assert.equal(session.game.active.y, initial.active.y + 1, 'gravity works when visible');
      await session.resize(columns, rows);
      const paused = state(session.game);
      await session.advance(10000);
      assert.deepEqual(state(session.game), paused, 'no unseen falling after shrinking');
    });

    test(`${label} terminal blocks movement and rotation until resized`, async t => {
      const session = await launch(game => {
        game.active = { type: 'T', x: 3, y: 4,
          cells: [{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 2, y: 0 }, { x: 1, y: 1 }] };
      });
      t.after(() => session.dispose());
      await session.resize(columns, rows);
      for (const key of ['\x1b[D', '\x1b[C', '\x1b[B', '\x1b[A']) {
        const before = state(session.game);
        await session.send(key);
        assert.deepEqual(state(session.game), before, 'each arrow is ignored behind the warning');
      }
      await session.resize(80, 24);
      const before = state(session.game);
      await session.send('\x1b[B');
      assert.equal(session.game.active.y, before.active.y + 1, 'controls resume');
      await session.send('\x1b[A');
      assert.notDeepEqual(session.game.active.cells, before.active.cells, 'rotation resumes');
    });

    test(`${label} terminal resumes with a full gravity interval, without catch-up`, async t => {
      const session = await launch();
      t.after(() => session.dispose());
      const interval = session.game.fallIntervalMs;
      await session.advance(interval - 1);
      await session.resize(columns, rows);
      await session.advance(interval * 10);
      session.elapse(interval * 10);
      const before = state(session.game);
      await session.resize(80, 24);
      await session.advance(interval - 1);
      assert.deepEqual(state(session.game), before, 'discard pre-pause remainder and hidden time');
      await session.advance(1);
      assert.equal(session.game.active.y, before.active.y + 1, 'one full interval falls exactly once');
      assert.deepEqual(session.game.board, before.board);
    });

    test(`${label} terminal cannot invisibly lock a piece or reach blocked-spawn game over`, async t => {
      const session = await launch((game, api) => {
        while (api.move(game, 0, 1)) {}
        const probe = api.createGame({ pieceSequence: ['T'] });
        const blocker = api.getActiveCells(probe)[0];
        game.board[blocker.y][blocker.x] = 'T';
      });
      t.after(() => session.dispose());
      assert.equal(session.game.gameOver, false);
      await session.resize(columns, rows);
      const before = state(session.game);
      await session.advance(session.game.fallIntervalMs * 100);
      assert.deepEqual(state(session.game), before, 'no locking, spawning, scoring, or game over while hidden');
      await session.resize(80, 24);
      await session.advance(session.game.fallIntervalMs);
      assert.equal(session.game.gameOver, true, 'fixture actually reaches game over when gravity resumes');
      assert.notDeepEqual(session.game.board, before.board, 'visible gravity locks the floor piece');
    });
  }

  for (const [label, key] of [['Q', 'q'], ['Ctrl+C', '\x03']]) {
    test(`${label} still exits while the terminal is undersized`, async t => {
      const session = await launch(undefined, { columns: 39, rows: 23 });
      t.after(() => session.dispose());
      await session.send(key);
      assert.deepEqual(session.exits, [0]);
      assert.equal(session.input.isRaw, false, 'restore terminal input');
      assert.equal(session.timers.size, 0, 'stop gravity timers');
    });
  }

  // Count physical rows after autowrap at the reported boundary, not just
  // newline-delimited rows in an 80-column terminal.
  for (const columns of [40, 80]) {
    const dimensions = { columns, rows: 24 };
    test(`${columns} columns: all 20 board rows are visible with borders within 24 rows`, async () => {
    const empty = await snapshot(blank, dimensions);
    const displayedRows = [];
    for (let y = 0; y < 20; y++) {
      const marked = await snapshot(game => { blank(game); game.board[y][0] = 'O'; }, dimensions);
      const changed = marked.flatMap((line, index) => line !== empty[index] ? [index] : []);
      assert.equal(changed.length, 1, `board row ${y} must change one visible row`);
      const row = changed[0];
      displayedRows.push(row);
      const changedColumns = [...marked[row]].flatMap((char, x) => char !== (empty[row][x] || ' ') ? [x] : []);
      assert.ok(empty[row].slice(0, Math.min(...changedColumns)).trim(), 'left border remains visible');
      assert.ok(empty[row].slice(Math.max(...changedColumns) + 1).trim(), 'right border remains visible');
    }
    assert.equal(new Set(displayedRows).size, 20, 'no board rows may be omitted or overlap');
    assert.deepEqual(displayedRows, Array.from({ length: 20 }, (_, i) => displayedRows[0] + i));
    assert.ok(empty.slice(0, displayedRows[0]).some(line => /[+\-_=─━┌┐╔╗]/u.test(line)), 'top border is visible');
    assert.ok(empty.slice(displayedRows.at(-1) + 1).some(line => /[+\-_=─━└┘╚╝]/u.test(line)), 'bottom border is visible');
  });

  test(`${columns} columns: the falling piece is displayed, not only settled cells`, async () => {
    const empty = await snapshot(blank, dimensions);
    const active = await snapshot(undefined, dimensions);
    const changes = active.filter((line, i) => line !== empty[i]);
    assert.equal(changes.length, 2, 'the initial O piece occupies two visible board rows');
  });

  test(`${columns} columns: score and keyboard instructions are readable within the same 24-row frame`, async () => {
    const lines = await snapshot(game => { game.score = 123456; }, dimensions);
    const text = lines.join('\n');
    assert.match(text, /score\s*[:=]?\s*123456/i);
    assert.match(text, /(?:arrow|←|→|↑|↓)/i, 'show the movement keys');
    assert.match(text, /rotat/i, 'show rotation instructions');
    assert.match(text, /(?:exit|quit)/i, 'show how to leave the game');
  });

  test(`${columns} columns: gravity redraws in place rather than appending overflowing frames`, async t => {
    const session = await launch(undefined, dimensions);
    t.after(() => session.dispose());
    await session.advance();
    const initial = session.screen.lines();
    for (let n = 0; n < 6; n++) { await session.advance(1000); fits(session.screen); }
    assert.notDeepEqual(session.screen.lines(), initial, 'falling must be visible');
  });

  test(`${columns} columns: blocked spawning renders game over, board, final score and exit controls within 24 rows`, async t => {
    const session = await launch((game, api) => {
      while (api.move(game, 0, 1)) {}
      const probe = api.createGame({ pieceSequence: ['T'] });
      const blocker = api.getActiveCells(probe)[0];
      game.board[blocker.y][blocker.x] = 'T';
      game.score = 98765;
    }, dimensions);
    t.after(() => session.dispose());
    await session.advance(1000);
    assert.equal(session.game.gameOver, true, 'fixture must reach actual game over');
    fits(session.screen);
    const ended = session.screen.lines();
    assert.match(ended.join('\n'), /game\s*over/i);
    assert.match(ended.join('\n'), /score\s*[:=]?\s*98765/i);
    assert.match(ended.join('\n'), /(?:exit|quit)/i);
    assert.ok(ended.filter(line => line.trim()).length >= 22, 'retain the board and borders at game over');
    for (let n = 0; n < 5; n++) await session.advance(1000);
    fits(session.screen);
    assert.deepEqual(session.screen.lines(), ended, 'game-over display remains stable');
  });
  }

  for (const columns of [1, 20, 39]) {
    test(`${columns} columns: undersized warning stays within physical screen bounds`, async t => {
      const session = await launch(undefined, { columns, rows: 24 });
      t.after(() => session.dispose());
      await session.advance(10000);
      fits(session.screen);
      assert.ok(session.screen.lines().some(line => line.trim()), 'show a bounded warning');
      if (columns >= 20) {
        assert.match(session.screen.lines().join('\n'), /resize|needs/i);
      }
    });
  }

  for (const gameOver of [false, true]) {
    test(`40 columns: unusually long score does not wrap (${gameOver ? 'game over' : 'playing'})`, async t => {
      const session = await launch(game => {
        game.score = Number.MAX_VALUE;
        game.gameOver = gameOver;
      }, { columns: 40, rows: 24 });
      t.after(() => session.dispose());
      fits(session.screen);
      const text = session.screen.lines().join('\n');
      assert.match(text, /score/i);
      assert.match(text, /exit|quit/i);
      if (gameOver) assert.match(text, /game\s*over/i);
    });
  }
}
