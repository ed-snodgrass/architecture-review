const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { spawn, spawnSync } = require('node:child_process');
const path = require('node:path');

const root = path.resolve(__dirname, '..');

// Run independently of the package configuration under test:
// node --test test/start.test.cjs
// These tests cover launch configuration only, not gameplay or rendering.
test('package.json explicitly configures an npm start command', () => {
  const pkg = JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8'));
  assert.equal(typeof pkg.scripts?.start, 'string', 'scripts.start must be a string');
  assert.ok(pkg.scripts.start.trim(), 'scripts.start must not be empty');
});

const hasPty = process.platform === 'linux' &&
  spawnSync('script', ['--version'], { encoding: 'utf8' }).status === 0;

test('npm start launches and stays running in a terminal', {
  skip: hasPty ? false : 'Requires Linux util-linux script for a real pseudo-terminal',
  timeout: 10000,
}, async () => {
  // A PTY allows implementations that correctly require interactive stdin.
  // A separate process group ensures the npm process and game are cleaned up.
  const child = spawn('script', ['-q', '-e', '-c', 'npm start', '/dev/null'], {
    cwd: root,
    detached: true,
    env: { ...process.env, TERM: 'xterm', COLUMNS: '80', LINES: '24' },
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  let output = '';
  child.stdout.on('data', chunk => { output += chunk; });
  child.stderr.on('data', chunk => { output += chunk; });
  let exited = false;
  let exitDescription = '';
  const closed = new Promise(resolve => {
    child.once('close', (code, signal) => {
      exited = true;
      exitDescription = `code=${code}, signal=${signal}`;
      resolve();
    });
  });
  let launchError;
  child.once('error', error => { launchError = error; });
  try {
    await Promise.race([
      closed,
      new Promise(resolve => setTimeout(resolve, 2000)),
    ]);
    assert.ifError(launchError);
    assert.equal(exited, false,
      `npm start exited instead of running the terminal game (${exitDescription}):\n${output}`);
  } finally {
    if (child.pid) {
      try { process.kill(-child.pid, 'SIGKILL'); } catch (error) {
        if (error.code !== 'ESRCH') throw error;
      }
    }
    child.stdin.destroy();
    await closed;
  }
});
