const { test } = require('node:test');
const assert = require('node:assert/strict');
const { spawn, spawnSync } = require('node:child_process');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const hasPty = process.platform === 'linux' &&
  spawnSync('script', ['--version'], { encoding: 'utf8' }).status === 0;

const FRAME_START = '\x1b[H\x1b[2J';
const CURSOR_RESTORED = '\x1b[?25h';

// A new frame or cursor restoration bounds the previous display. Only the
// final, still-streaming frame may be incomplete; never truncate or filter a
// bounded malformed frame out of the acceptance checks.
function parseFrames(output, closed = false) {
  const chunks = output.split(FRAME_START).slice(1);
  const frames = [];
  for (let i = 0; i < chunks.length; i++) {
    const end = chunks[i].indexOf(CURSOR_RESTORED);
    const bounded = i < chunks.length - 1 || end !== -1 || closed;
    const text = end === -1 ? chunks[i] : chunks[i].slice(0, end);
    const lines = text.replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, '')
      .replace(/\r/g, '').split('\n');
    assert.ok(lines.length <= 24, 'frame must not exceed 24 rows');
    assert.ok(lines.every(line => line.length <= 80), 'frame must not exceed 80 columns');
    if (!bounded && (lines.length < 24 || !lines[23].endsWith('exit'))) continue;
    assert.equal(lines.length, 24, 'complete frame must contain exactly 24 rows');
    assert.match(lines[23], /exit$/, 'complete frame must include all controls');
    frames.push(lines);
  }
  return frames;
}

const sampleFrame = Array.from({ length: 24 }, (_, i) =>
  i === 23 ? 'Arrows: move; Up: rotate; Q/Ctrl+C: exit' : `row ${i}`).join('\n');

test('frame validation preserves all rows and excludes shutdown output', () => {
  const output = FRAME_START + sampleFrame + FRAME_START + sampleFrame +
    CURSOR_RESTORED + '\x1b[?1049l\r\nTTY_RESTORED:0\r\n';
  assert.equal(parseFrames(output, true).length, 2);
});

test('frame validation defers only an incomplete streaming frame', () => {
  const output = FRAME_START + sampleFrame + FRAME_START + 'Tetris';
  assert.equal(parseFrames(output).length, 1);
  assert.throws(() => parseFrames(output, true), /exactly 24 rows/);
  assert.throws(() => parseFrames(output + FRAME_START), /exactly 24 rows/);
  const partialControls = FRAME_START + sampleFrame.slice(0, -2);
  assert.equal(parseFrames(partialControls).length, 0);
  assert.throws(() => parseFrames(partialControls, true), /all controls/);
});

test('frame validation rejects extra rows between displays and before shutdown', () => {
  assert.throws(() => parseFrames(FRAME_START + sampleFrame + '\nextra' +
    FRAME_START + sampleFrame), /24 rows/);
  assert.throws(() => parseFrames(FRAME_START + sampleFrame + '\n' +
    CURSOR_RESTORED), /24 rows/);
});

test('frame validation rejects overwide rows in later frames', () => {
  const wideFrame = sampleFrame.replace('row 10', 'X'.repeat(81));
  assert.throws(() => parseFrames(FRAME_START + sampleFrame + FRAME_START +
    wideFrame + CURSOR_RESTORED, true), /80 columns/);
});

// End-to-end acceptance: real npm entry point, terminal input, mechanics, and
// rendering. Unlike the VM control tests, no game or timer is stubbed.
test('npm start is playable in a 24-row terminal and restores it on quit', {
  skip: hasPty ? false : 'Requires Linux util-linux script for a real pseudo-terminal',
  timeout: 15000,
}, async () => {
  const command = 'stty rows 24 cols 80; before=$(stty -g); npm start; result=$?; ' +
    'after=$(stty -g); if [ "$before" = "$after" ]; then ' +
    'printf "\\nTTY_RESTORED:%s\\n" "$result"; else printf "\\nTTY_CHANGED\\n"; fi';
  const child = spawn('script', ['-q', '-e', '-c', command, '/dev/null'], {
    cwd: root, detached: true,
    env: { ...process.env, TERM: 'xterm', COLUMNS: '80', LINES: '24' },
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  let output = '';
  let launchError;
  let closed = false;
  let exitCode;
  child.on('error', error => { launchError = error; });
  child.stdout.on('data', chunk => { output += chunk; });
  child.stderr.on('data', chunk => { output += chunk; });
  const done = new Promise(resolve => child.on('close', code => {
    closed = true;
    exitCode = code;
    resolve();
  }));

  function frames() {
    return parseFrames(output, closed);
  }
  function piece(lines) {
    const cells = [];
    for (let y = 0; y < 20; y++) {
      const row = lines[y + 2];
      for (let x = 0; x < 10; x++) {
        if (row.slice(1 + x * 2, 3 + x * 2) === '[]') cells.push({ x, y });
      }
    }
    assert.equal(cells.length, 4, 'opening board must show a tetromino');
    return cells;
  }
  async function waitFor(predicate, label, timeout = 4000) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      assert.ifError(launchError);
      if (predicate()) return;
      assert.equal(closed, false, `game exited while waiting for ${label}:\n${output}`);
      await new Promise(resolve => setTimeout(resolve, 10));
    }
    assert.fail(`timed out waiting for ${label}:\n${output}`);
  }
  function translated(before, after, dx, minDy) {
    const dy = after[0].y - before[0].y;
    return dy >= minDy && before.every((cell, i) =>
      after[i].x === cell.x + dx && after[i].y === cell.y + dy);
  }
  async function press(bytes, dx, minDy, label) {
    const before = piece(frames().at(-1));
    const count = frames().length;
    child.stdin.write(bytes); // Deliberately no Enter: input must be immediate.
    await waitFor(() => frames().slice(count).some(frame =>
      translated(before, piece(frame), dx, minDy)), label);
  }

  try {
    await waitFor(() => frames().length > 0, 'initial game display');
    const first = frames()[0];
    assert.match(first[0], /Tetris.*Score:\s*0/);
    assert.equal(first[1], '+--------------------+');
    assert.equal(first[22], '+--------------------+');
    assert.ok(first.every(line => line.length <= 80), 'display must not wrap past 24 rows');
    assert.equal(closed, false);
    piece(first);

    await press('\x1b[D', -1, 0, 'left movement');
    await press('\x1b[C', 1, 0, 'right movement');
    await press('\x1b[B', 0, 1, 'down movement');
    const beforeGravity = piece(frames().at(-1));
    const count = frames().length;
    await waitFor(() => frames().slice(count).some(frame =>
      translated(beforeGravity, piece(frame), 0, 1)), 'automatic falling');

    child.stdin.write('q');
    await Promise.race([done, new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Q did not end the terminal session')), 4000).unref())]);
    assert.equal(exitCode, 0, output);
    assert.ok(frames().length > 0, 'revalidate every complete frame after shutdown');
    assert.match(output, /TTY_RESTORED:0/, 'quit must restore the original terminal settings');
    assert.ok(output.includes('\x1b[?25h'), 'quit must show the cursor');
    assert.ok(output.includes('\x1b[?1049l'), 'quit must restore the shell screen');
  } finally {
    if (child.pid && !closed) {
      try { process.kill(-child.pid, 'SIGKILL'); } catch (error) {
        if (error.code !== 'ESRCH') throw error;
      }
    }
    child.stdin.destroy();
    await done;
  }
});
