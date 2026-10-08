import { After, Given, When, Then, IWorld } from '@cucumber/cucumber';
import assert from 'node:assert/strict';
import { exec, execFileSync, spawnSync } from 'node:child_process';
import { copyFileSync, cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

Given('a new target', function() {
  this.target = join(this.workspace, 'target');
  mkdirSync(this.target);
});

Given('this assembly line:', function (line: string) {
  this.assemblyLine = line;
  writeFileSync(join(this.workspace, 'assembly-line.dot'), line);
});

Given('the target folder does not exist', function () {
  rmSync(this.target, { recursive: true });
});

Given('the target is outside any Git repository', function () {
  this.standaloneTarget = mkdtempSync(join(tmpdir(), 'factory-target-'));
  this.target = this.standaloneTarget;
});

Then('the target uses the containing repository', function () {
  assert.ok(existsSync(this.target), 'Expected the target folder');

  const repository = execFileSync('git', [
    'rev-parse', '--show-toplevel',
  ], {
    cwd: this.target,
    encoding: 'utf8',
  }).trim();

  assert.equal(repository, this.workspace);
});

Then('the target is a Git repository', function () {
  const repository = execFileSync('git', [
    'rev-parse', '--show-toplevel',
  ], {
    cwd: this.target,
    encoding: 'utf8',
  }).trim();

  assert.equal(repository, this.target);
});

Given('a copy of the factory', function () {
  this.workspace = mkdtempSync(join(tmpdir(), 'factory-'));

  for (const file of ['cli.ts', 'run', 'package.json']) {
    copyFileSync(resolve(file), join(this.workspace, file));
  }
  copyFileSync(resolve('assembly-line.dot'), join(this.workspace, 'assembly-line.dot'));
  for (const machine of ['planner', 'doer', 'validator']) {
    cpSync(resolve(machine), join(this.workspace, machine), { recursive: true });
  }

  symlinkSync(resolve('node_modules'), join(this.workspace, 'node_modules'));

  const git = (args: string[]) => 
    execFileSync('git', args, {
      cwd: this.workspace,
      encoding: 'utf8'
    });

  git(['init']);
  git(['config', 'user.name', 'Factory Test']);
  git(['config', 'user.email', 'factory@example.test']);
  git(['commit', '--allow-empty', '-m', 'Initial test commit']);
  this.initialCommit = git(['rev-parse', 'HEAD']).trim();
});

Given('the factory has staged and unstaged changes', function () {
  const git = (args: string[]) =>
    execFileSync('git', args, {
      cwd: this.workspace,
      encoding: 'utf8',
    });

  const notes = join(this.workspace, 'notes.txt');
  writeFileSync(notes, 'Original notes\n');
  git(['add', '--', 'cli.ts', 'run', 'package.json', 'notes.txt']);
  git(['commit', '-m', 'Factory and notes']);
  this.initialCommit = git(['rev-parse', 'HEAD']).trim();

  writeFileSync(notes, 'Staged notes\n');
  git(['add', '--', 'notes.txt']);
  writeFileSync(notes, 'Staged notes\nUnstaged addition\n');

  const cli = join(this.workspace, 'cli.ts');
  writeFileSync(cli, readFileSync(cli, 'utf8') + '\n// Local edit\n');

  this.snapshotUnrelated = () =>
  ['cli.ts', 'run', 'package.json', 'notes.txt'].map(file => ({
    file,
    committed: git(['show', 'HEAD:' + file]),
    staged: git(['show', ':' + file]),
    onDisk: readFileSync(join(this.workspace, file), 'utf8'),
  }));

  this.unrelatedBefore = this.snapshotUnrelated();
});

Then(
  "the factory's own files and unrelated uncommitted changes are as they were",
  function () {
    assert.deepEqual(this.snapshotUnrelated(), this.unrelatedBefore);
  },
);

Given('a seed describing a game of Tetris', function() {
  this.seed = join(this.workspace, 'seed.md');
  copyFileSync(resolve('../tetris/spec.md'), this.seed);
});

Given('no seed is chosen', function () {
  this.seed = undefined;
});

Given('no target is chosen', function () {
  this.omitTarget = true;
});

Given('the seed has been deleted', function () {
  rmSync(this.seed);
});

Given('no harness is chosen', function() {
  this.harness = undefined;
  this.doerHarness = undefined;
  this.validatorHarness = undefined;
});

Given('the agent cannot be run', function () {
  this.harness = join(this.workspace, 'missing-agent');
});

Given('the doer cannot be run', function () {
  this.doerHarness = join(this.workspace, 'missing-doer');
});

Given('no plan', function () {
  rmSync(join(this.target, '.factory', 'plan.md'), { force: true });
});

Given('a plan with three tasks, none of them done', function() {
  const planDirectory = join(this.target, '.factory');
  mkdirSync(planDirectory, {recursive: true });
  writeFileSync(
    join(planDirectory, 'plan.md'),
    '- [ ] alpha\n- [ ] beta\n- [ ] gamma\n',
  );
});

Given('a plan whose first task is done', function() {
  const planDirectory = join(this.target, '.factory');
  mkdirSync(planDirectory, { recursive: true });
  writeFileSync(
    join(planDirectory, 'plan.md'),
    '- [x] alpha\n- [ ] beta\n- [ ] gamma\n',
  );
});

Given('a plan in which every task is done', function () {
  const planDirectory = join(this.target, '.factory');
  mkdirSync(planDirectory, { recursive: true });
  writeFileSync(
    join(planDirectory, 'plan.md'),
    '- [x] alpha\n- [x] beta\n',
  );
  execFileSync('git', ['add', '--', '.factory/plan.md'], {
    cwd: this.target,
  });
  execFileSync('git', [
    'commit', '--only', '-m', 'Completed plan', '--', '.factory/plan.md',
  ], {
    cwd: this.target,
  });
  this.initialCommit = execFileSync('git', ['rev-parse', 'HEAD'], {
    cwd: this.target,
    encoding: 'utf8',
  }).trim();
});

Given('the validator says {string} before its result', function (message: string) {
  this.env.FACTORY_TEST_VALIDATOR_PREAMBLE = message;
});

Then(
  'the plan has the tasks {string} and {string}, and no others', 
  function (first: string, second: string) {
    const plan = readFileSync(
      join(this.target, '.factory', 'plan.md'),
      'utf8',
    );
    const tasks = [...plan.matchAll(/^- \[[ x]\] (.+)$/gm)].map(match => match[1]);

    assert.deepEqual(tasks, [first, second]);
  },
);

Then('the plan still has those three tasks', function () {
  const plan = readFileSync(
    join(this.target, '.factory', 'plan.md'),
    'utf8',
  );
  const tasks = [...plan.matchAll(/^- \[[ x]\] (.+)$/gm)]
    .map(match => match[1]);

  assert.deepEqual(tasks, ['alpha', 'beta', 'gamma']);
});

Then('there is no plan', function() {
  assert.equal(
    existsSync(join(this.target, '.factory', 'plan.md')),
    false,
    'Expected no plan in the target',
  );
});

Then(
  /^(?:there is a plan|the plan is \.factory\/plan\.md in the target)$/,
  function () {
  assert.ok(
    existsSync(join(this.target, '.factory', 'plan.md')),
    'Expected a plan in the target',
  );
});

Then("there is no plan in the factory's folder", function () {
  assert.equal(
    existsSync(join(this.workspace, '.factory', 'plan.md')),
    false,
    "Expected no plan in the factory's folder",
  );
});

Then('the committed plan matches the plan on disk', function () {
  const committed = execFileSync('git', [
    'show', 'HEAD:./.factory/plan.md',
  ], {
    cwd: this.target,
    encoding: 'utf8',
  });
  const onDisk = readFileSync(
    join(this.target, '.factory', 'plan.md'),
    'utf8',
  );

  assert.equal(committed, onDisk);
});

Then('the target has no uncommitted changes', function () {
  const status = execFileSync('git', [
    'status', '--porcelain', '--untracked-files=all', '--', '.',
  ], {
    cwd: this.target,
    encoding: 'utf8',
  });

  assert.equal(status, '', 'Expected no uncommitted changes in the target');
});

Then('it reports that it could not run the agent', function () {
  const output = this.result.stdout + this.result.stderr;
  assert.match(output, /could not run the agent/i);
});

Then('it reports that it could not run the doer', function () {
  const output = this.result.stdout + this.result.stderr;
  assert.match(output, /could not run the doer/i);
});

Then('it reports that the pass hit its limit', function () {
  const output = this.result.stdout + this.result.stderr;
  assert.match(output, /pass hit its limit/i);
});

Then("it reports that it could not read the agent's result", function () {
  const output = this.result.stdout + this.result.stderr;
  assert.match(output, /could not read the agent's result/i);
});

Then('it reports that there is no seed', function () {
  const output = this.result.stdout + this.result.stderr;
  assert.match(output, /no seed/i);
});

Then('it reports that a target is required', function () {
  const output = this.result.stdout + this.result.stderr;
  assert.match(output, /target is required/i);
});

Then("it reports that it could not read the validator's result", function () {
  const output = this.result.stdout + this.result.stderr;
  assert.match(output, /could not read the validator's result/i);
});

Then('no agent has been called', function () {
  assert.equal(
    existsSync(join(this.workspace, 'agent-calls')),
    false,
    'Expected no agent calls',
  );
});

Then('there are no new commits', function () {
  const currentCommit = execFileSync('git', ['rev-parse', 'HEAD'], {
    cwd: this.workspace,
    encoding: 'utf8',
  }).trim();

  assert.equal(currentCommit, this.initialCommit);
});

Then(
  /^there (?:is|are) (no|one|two|three) new work commits?$/,
  function (count: string) {
  const output = execFileSync('git', [
    'log',
    '--format=%H',
    this.initialCommit + '..HEAD',
    '--',
    '.',
    ':(exclude).factory',
  ], {
    cwd: this.target,
    encoding: 'utf8'
  });

  const commits = output.trim().split('\n').filter(Boolean);
  const expected = count === 'no' ? 0 : count === 'one' ? 1 : count === 'two' ? 2 : 3;
  assert.equal(commits.length, expected, `Expected ${expected} new work commits`);
  this.workCommit = commits[0];
});

Then(
  /^it contains the work for the (first|second) task$/,
  function (position: string) {
    const task = position === 'first' ? 'alpha' : 'beta';
    const contents = execFileSync('git', [
      'show',
      this.workCommit + ':./' + task + '.txt',
    ], {
      cwd: this.target,
      encoding: 'utf8',
    });

    assert.equal(contents, task + '\n');
  },
);
Then('the work for alpha and beta has been committed', function () {
  for (const task of ['alpha', 'beta']) {
    const contents = execFileSync('git', [
      'show', 'HEAD:./' + task + '.txt',
    ], {
      cwd: this.target,
      encoding: 'utf8',
    });

    assert.equal(contents, task + '\n');
  }
});

Then('its only product file is SENTINEL', function () {
  const output = execFileSync('git', [
    'diff-tree',
    '--no-commit-id',
    '--name-only',
    '--relative',
    '-r',
    this.workCommit,
    '--',
    '.',
    ':(exclude).factory',
  ], {
    cwd: this.target,
    encoding: 'utf8',
  });

  const files = output.trim().split('\n').filter(Boolean);
  assert.deepEqual(files, ['SENTINEL']);
});

Given('the planner plans the tasks alpha and beta', function () {
  const agentBin = join(this.workspace, 'agents');
  mkdirSync(agentBin);

  const script = String.raw`#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');

const name = path.basename(process.argv[1]);
const workspace = process.env.FACTORY_TEST_WORKSPACE;
fs.writeFileSync(
  path.join(workspace, name + '-called'),
  JSON.stringify(process.argv.slice(2))
);
fs.appendFileSync(path.join(workspace, 'agent-calls'), name + '\n');

const plan = '.factory/plan.md';
const prompt = process.argv.slice(2).join('\n');
fs.mkdirSync('.factory', { recursive: true });

if (process.env.FACTORY_TEST_PLANNER_PROSE === '1') {
  if (!fs.existsSync(plan)) {
    fs.writeFileSync(plan, 'First do alpha, then do beta.');
  } else if (prompt.includes('Mark the current task done')) {
    const text = fs.readFileSync(plan, 'utf8');
    fs.writeFileSync(
      plan,
      text === 'First do alpha, then do beta.'
        ? 'Alpha is finished. Next do beta.'
        : 'Both tasks are finished.',
    );
  }

  const text = fs.readFileSync(plan, 'utf8');
  console.log(JSON.stringify({
    complete: text === 'Both tasks are finished.',
  }));
  process.exit(0);
}

if (!fs.existsSync(plan)) {
  fs.writeFileSync(plan, '- [ ] alpha\n- [ ] beta\n');
}

let text = fs.readFileSync(plan, 'utf8');
if (prompt.includes('Mark the current task done')) {
  text = text.replace(/^- \[ \] (.+)$/m, '- [x] $1');
  fs.writeFileSync(plan, text);
}

console.log(JSON.stringify({ complete: !text.includes('- [ ]') }));
`;

  for (const name of ['pi', 'fake-agent']) {
    writeFileSync(join(agentBin, name), script, { mode: 0o755 });
  }

  this.harness = 'fake-agent';
  this.env = {
    ...process.env,
    PATH: agentBin + ':' + process.env.PATH,
    FACTORY_TEST_WORKSPACE: this.workspace,
  };
});

Given('the doer does the next task in the plan', function () {
  this.doerHarness = join(this.workspace, 'agents', 'fake-doer');

  const script = String.raw`#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');

const workspace = process.env.FACTORY_TEST_WORKSPACE;
fs.appendFileSync(path.join(workspace, 'agent-calls'), 'fake-doer\n');
fs.appendFileSync(path.join(workspace, 'doer-calls'), 'called\n');
fs.writeFileSync(path.join(workspace, 'doer-args'), JSON.stringify(process.argv.slice(2)));
fs.appendFileSync(path.join(workspace, 'doer-args-log'), JSON.stringify(process.argv.slice(2)) + '\n');

const plan = fs.readFileSync('.factory/plan.md', 'utf8');

let task;
if (process.env.FACTORY_TEST_DOER_PROSE === '1') {
  task = plan === 'First do alpha, then do beta.'
    ? 'alpha'
    : plan === 'Alpha is finished. Next do beta.' ? 'beta' : undefined;
} else {
  task = plan.match(/^- \[ \] (.+)$/m)?.[1];
}

if (task) {
  const productFile = process.env.FACTORY_TEST_PRODUCT_FILE || task + '.txt';
  fs.writeFileSync(productFile, task + '\n');
  console.log(JSON.stringify({ task }));
}
`;

  writeFileSync(this.doerHarness, script, { mode: 0o755 });
});

Given('the validator is always satisfied', function () {
  this.validatorHarness = join(this.workspace, 'agents', 'fake-validator');

  const script = String.raw`#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');

const workspace = process.env.FACTORY_TEST_WORKSPACE;
fs.appendFileSync(path.join(workspace, 'agent-calls'), 'fake-validator\n');
fs.appendFileSync(path.join(workspace, 'validator-calls'), 'called\n');
const validatorArgs = path.join(workspace, 'validator-args');
if (!fs.existsSync(validatorArgs)) fs.writeFileSync(validatorArgs, JSON.stringify(process.argv.slice(2)));
if (process.env.FACTORY_TEST_VALIDATOR_PREAMBLE) {
  console.log(process.env.FACTORY_TEST_VALIDATOR_PREAMBLE);
}
const callCount = fs.readFileSync(
  path.join(workspace, 'validator-calls'),
  'utf8',
).trim().split('\n').length;

if (process.env.FACTORY_TEST_VALIDATOR_PROSE_ONLY === '1') {
  console.log('The work needs another look.');
  process.exit(0);
}

const rejectFirst =
  process.env.FACTORY_TEST_REJECT_FIRST === '1' && callCount === 1;
const satisfied =
  process.env.FACTORY_TEST_REJECT_ALWAYS !== '1' && !rejectFirst;
console.log(JSON.stringify({
  satisfied,
  findings: satisfied ? [] : ['The task mixes unrelated responsibilities.'],
}));
`;

  writeFileSync(this.validatorHarness, script, { mode: 0o755 });
});

Given('the validator is never satisfied', function () {
  this.env.FACTORY_TEST_REJECT_ALWAYS = '1';
});

Given('the validator is not satisfied the first time', function () {
  this.env.FACTORY_TEST_REJECT_FIRST = '1';
});

Given('the agent plans the tasks alpha and beta, and does one task a pass', function() {
  const agentBin = join(this.workspace, 'agents');
  mkdirSync(agentBin);

  const script = String.raw`#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');

const name = path.basename(process.argv[1]);
fs.writeFileSync(
 path.join(process.env.FACTORY_TEST_WORKSPACE, name + '-called'),
 JSON.stringify(process.argv.slice(2))
);

fs.appendFileSync(
 path.join(process.env.FACTORY_TEST_WORKSPACE, 'agent-calls'),
 name + '\n'
);

if (process.env.FACTORY_TEST_PREAMBLE) {
  console.log(process.env.FACTORY_TEST_PREAMBLE);
}

if (process.env.FACTORY_TEST_PROSE_ONLY) {
  console.log('I could not finish the task.');
  process.exit(0);
}

const plan = '.factory/plan.md';
fs.mkdirSync('.factory', { recursive: true });

if (process.env.FACTORY_TEST_PROSE_PLAN) {
  if (!fs.existsSync(plan)) {
    fs.writeFileSync(plan, 'First do alpha, then do beta.');
    console.log(JSON.stringify({ complete: false }));
  } else {
    const text = fs.readFileSync(plan, 'utf8');
    const task = text === 'First do alpha, then do beta.'
      ? 'alpha'
      : text === 'Alpha is finished. Next do beta.' ? 'beta' : null;

    if (task) {
      fs.writeFileSync(task + '.txt', task + '\n');
      fs.writeFileSync(plan, task === 'alpha'
        ? 'Alpha is finished. Next do beta.'
        : 'Both tasks are finished.');
    }

    console.log(JSON.stringify({ complete: task === null, task }));
  }
  process.exit(0);
}

if (!fs.existsSync(plan)) {
  fs.writeFileSync(plan, '- [ ] alpha\n- [ ] beta\n');
  console.log(JSON.stringify({ complete: false }));
} else {
  const text = fs.readFileSync(plan, 'utf8');   
  const next = text.match(/^- \[ \] (.+)$/m);

  if (next) {
    const task = next[1];
    const productFile = process.env.FACTORY_TEST_PRODUCT_FILE || task + '.txt';
    fs.writeFileSync(productFile, task + '\n');
    fs.writeFileSync(plan, text.replace(next[0], '- [x] ' + task));
    console.log(JSON.stringify({ complete: false, task }));
  } else {
    console.log(JSON.stringify({ complete: true }));  
  }
}
`;
  for( const name of ['pi', 'fake-agent']) {
    writeFileSync(join(agentBin, name), script, { mode: 0o755 });
  }
  
  this.harness = 'fake-agent';
  this.env = {
    ...process.env,
    PATH: agentBin + ':' + process.env.PATH,
    FACTORY_TEST_WORKSPACE: this.workspace,
  }
});

Given('the doer keeps its plan in prose', function () {
  this.env.FACTORY_TEST_DOER_PROSE = '1';
});

Given('the planner keeps its plan in prose', function () {
  this.env.FACTORY_TEST_PLANNER_PROSE = '1';
});

Given('the doer writes a file called SENTINEL', function () {
  this.env.FACTORY_TEST_PRODUCT_FILE = 'SENTINEL';
});

Given('the agent answers in prose, with no result', function () {
  this.env.FACTORY_TEST_PROSE_ONLY = '1';
});

Given('the validator answers in prose, with no result', function () {
  this.env.FACTORY_TEST_VALIDATOR_PROSE_ONLY = '1';
});

Given('the factory allows at most three attempts per pass', function () {
  this.maxAttempts = 3;
});

Given("the validator's lens is {word}", function (lens: string) {
  this.validatorLens = lens;
});

function runFactory(this: IWorld, mode: string) {
  const args = [join(this.workspace, 'run')];

  if (!this.omitTarget) {
    args.push('--target', this.targetArgument ?? this.target);
  }

  if (this.seed !== undefined) {
    args.push('--seed', this.seed);
  }

  if (mode === 'to completion') {
    args.push('--all');
  }

  if (this.harness !== undefined) {
    args.push('--harness', this.harness);
  }

  if (this.doerHarness !== undefined) {
    args.push('--doer-harness', this.doerHarness);
  }

  if (this.validatorHarness !== undefined) {
    args.push('--validator-harness', this.validatorHarness);
  }

  if (this.validatorLens !== undefined) {
    args.push('--validator-lens', this.validatorLens);
  }

  if (this.maxAttempts !== undefined) {
    args.push('--max-attempts', String(this.maxAttempts));
  }

  this.result = spawnSync('bash', args, {
    cwd: this.workspace,
    env: this.env ?? process.env,
    encoding: 'utf8',
    timeout: 3000,
    killSignal: 'SIGKILL',
  });
}

When('the factory runs', function () {
  runFactory.call(this, 'to completion');
});

When('the factory reads the assembly line', function () {
  this.result = spawnSync('bash', [join(this.workspace, 'run'), '--check-assembly-line'], {
    cwd: this.workspace,
    env: this.env ?? process.env,
    encoding: 'utf8',
  });
});

When(/^the factory runs (one pass|to completion)$/, runFactory);

When('the factory builds the target {string} to completion', function (name: string) {
  this.target = resolve(this.workspace, name);
  this.targetArgument = name;

  this.initialCommit = execFileSync('git', ['rev-parse', 'HEAD'], {
    cwd: this.workspace,
    encoding: 'utf8',
  }).trim();
  
  runFactory.call(this, 'to completion');

  assert.equal(this.result.status, 0, this.result.stderr);

  this.targetTrees ??= {};
  this.targetTrees[name] ??= execFileSync('git', [
    'rev-parse', 'HEAD:./' + name,
  ], {
    cwd: this.workspace,
    encoding: 'utf8',
  }).trim();
});

Then('the target {string} is unchanged', function (name: string) {
  const tree = execFileSync('git', [
    'rev-parse', 'HEAD:./' + name,
  ], {
    cwd: this.workspace,
    encoding: 'utf8',
  }).trim();

  assert.equal(tree, this.targetTrees[name]);

  const status = execFileSync('git', [
    'status', '--porcelain', '--untracked-files=all', '--', name,
  ], {
    cwd: this.workspace,
    encoding: 'utf8',
  });

  assert.equal(status, '', 'Expected no uncommitted target changes');
});

Then(
  'the targets {string} and {string} each have their own completed plan and committed work',
  function (first: string, second: string) {
    for (const name of [first, second]) {
      const target = resolve(this.workspace, name);
      const committed = (file: string) =>
        execFileSync('git', ['show', 'HEAD:./' + file], {
          cwd: target,
          encoding: 'utf8',
        });

      const plan = readFileSync(
        join(target, '.factory', 'plan.md'),
        'utf8',
      );
      assert.equal(plan, '- [x] alpha\n- [x] beta\n');
      assert.equal(committed('.factory/plan.md'), plan);

      for (const task of ['alpha', 'beta']) {
        assert.equal(committed(task + '.txt'), task + '\n');
      }
    }
  },
);

When('the factory builds the same target using its absolute path', function () {
  this.initialCommit = execFileSync('git', ['rev-parse', 'HEAD'], {
    cwd: this.workspace,
    encoding: 'utf8',
  }).trim();

  this.targetArgument = this.target;
  runFactory.call(this, 'to completion');

  assert.equal(this.result.status, 0, this.result.stderr);
});

Then('pi has been called', function() {
  assert.ok(
    existsSync(join(this.workspace, 'pi-called')),
    'Expected the factory to call pi',
  );
});

Then('the chosen agent has been called', function() {
  assert.ok(
    existsSync(join(this.workspace, this.harness + '-called')),
    'Expected the factory to call the chosen agent',
  );
});

Then("the doer's chosen harness has been called", function () {
  assert.ok(
    existsSync(join(this.workspace, 'doer-calls')),
    'Expected the factory to call the chosen doer',
  );
});

Then('pi has not been called', function() {
  assert.equal(
    existsSync(join(this.workspace, 'pi-called')),
    false,
    'Expected the factory not to call pi',
  );
});

Then('the doer was pointed at the plan and at the seed', function () {
  const args: string[] = JSON.parse(readFileSync(
    join(this.workspace, 'doer-args'),
    'utf8',
  ));
  const prompt = args.join('\n');

  assert.ok(prompt.includes(this.seed), 'Expected the seed path');
  assert.ok(
    prompt.includes(join(this.target, '.factory', 'plan.md')),
    'Expected the plan path',
  );
});

Then('the planner was asked for a result with the field "complete"', function () {
  const args: string[] = JSON.parse(readFileSync(
    join(this.workspace, this.harness + '-called'),
    'utf8',
  ));
  const prompt = args.join('\n');

  assert.match(prompt, /JSON/i);
  assert.match(prompt, /\bcomplete\b/);
});

Then('the validator was given {string}', function (lens: string) {
  const args: string[] = JSON.parse(readFileSync(
    join(this.workspace, 'validator-args'),
    'utf8',
  ));
  const prompt = args.join('\n');

  assert.match(prompt, new RegExp(`\\b${lens}\\b`, 'i'));
});

Then('the validator was given the work for the second task', function () {
  const args: string[] = JSON.parse(readFileSync(
    join(this.workspace, 'validator-args'),
    'utf8',
  ));
  const prompt = args.join('\n');

  assert.match(prompt, /\bbeta\.txt\b/);
});

Then('it was not given the work for the first task', function () {
  const args: string[] = JSON.parse(readFileSync(
    join(this.workspace, 'validator-args'),
    'utf8',
  ));
  const prompt = args.join('\n');

  assert.doesNotMatch(prompt, /\balpha\.txt\b/);
});

Then('the agent has been called once', function () {
  const calls = readFileSync(
    join(this.workspace, 'agent-calls'),
    'utf8',
  ).trim().split('\n');

  assert.equal(calls.length, 1);
});

Then(
  /^the doer has been called (once|twice|three times|four times)$/,
  function (count: string) {
    const calls = readFileSync(
      join(this.workspace, 'doer-calls'),
      'utf8',
    ).trim().split('\n');

    const expected = count === 'once' ? 1 : count === 'twice' ? 2 : count === 'three times' ? 3 : 4;
    assert.equal(calls.length, expected);
  },
);

Then('the doer has not been called', function () {
  assert.equal(
    existsSync(join(this.workspace, 'doer-calls')),
    false,
    'Expected no doer calls',
  );
});

Then("the doer was given the validator's findings", function () {
  const prompt = readFileSync(join(this.workspace, 'doer-args-log'), 'utf8');

  assert.match(prompt, /mixes unrelated responsibilities/i);
});

Then('the plan shows the first task as done', function () {
  const plan = readFileSync(
    join(this.target, '.factory', 'plan.md'),
    'utf8',
  );
  assert.match(plan, /^- \[x\] alpha$/m);
});

Then('the plan shows the first two tasks as done', function () {
  const plan = readFileSync(
    join(this.target, '.factory', 'plan.md'),
    'utf8',
  );

  assert.match(plan, /^- \[x\] alpha$/m);
  assert.match(plan, /^- \[x\] beta$/m);
});

Then('the plan shows the other two as not done', function () {
  const plan = readFileSync(
    join(this.target, '.factory', 'plan.md'),
    'utf8',
  );
  assert.match(plan, /^- \[ \] beta$/m);
  assert.match(plan, /^- \[ \] gamma$/m)
});

Then('the factory has stopped', function () {
  assert.equal(this.result.error, undefined);
  assert.equal(this.result.signal, null);
  assert.notEqual(this.result.status, null);
});

Then(
  /^the plan shows every task as (done|not done)$/,
  function (state: string) {
    const plan = readFileSync(
      join(this.target, '.factory', 'plan.md'),
      'utf8',
    );
    const tasks = [...plan.matchAll(/^- \[([ x])\] (.+)$/gm)];
    const marker = state === 'done' ? 'x' : ' ';

    assert.ok(tasks.length > 0, 'Expected tasks in the plan');
    assert.ok(
      tasks.every(task => task[1] === marker),
      `Expected every task to be ${state}`,
    );
  },
);

Then('it accepts it', function () {
  assert.equal(this.result.status, 0, this.result.stderr);
});

Then('it refuses it', function () {
  assert.notEqual(this.result.status, 0);
});

Given('the validator has been taken out, so the doer goes straight to the planner', function () {
  const file = join(this.workspace, 'assembly-line.dot');
  const line = readFileSync(file, 'utf8')
    .replace(/^\s*doer -> validator.*$/m, '  doer -> planner')
    .replace(/^\s*validator -> .*$(?:\n)?/gm, '');
  writeFileSync(file, line);
});

Given('{string} is misspelt {string} throughout the assembly line', function (from: string, to: string) {
  const file = join(this.workspace, 'assembly-line.dot');
  writeFileSync(file, readFileSync(file, 'utf8').replaceAll(from, to));
});

Given('the edge from validator to planner has been taken out', function () {
  const file = join(this.workspace, 'assembly-line.dot');
  writeFileSync(file, readFileSync(file, 'utf8').replace(/^\s*validator -> planner.*$(?:\n)?/m, ''));
});

Then('it reports that it has no machine called {string}', function (name: string) {
  assert.match(this.result.stdout + this.result.stderr, new RegExp(`no machine called ["']?${name}`, 'i'));
});

Then('it reports that finish cannot be reached from validator', function () {
  assert.match(this.result.stdout + this.result.stderr, /finish cannot be reached from validator/i);
});

Given('no harness is chosen for the validator', function () {
  this.validatorHarness = undefined;
});

Given('the factory allows at most three attempts at a task', function () {
  this.maxAttempts = 3;
});

Given('the edges from validator are labelled {string} and {string}', function (positive: string, negative: string) {
  const file = join(this.workspace, 'assembly-line.dot');
  let line = readFileSync(file, 'utf8');
  line = line.replace('label="not satisfied"', `label="${negative}"`)
    .replace('label="satisfied"', `label="${positive}"`);
  writeFileSync(file, line);
});

Then('the validator was asked for a result with the fields {string} and {string}', function (field: string, other: string) {
  const prompt = JSON.parse(readFileSync(join(this.workspace, 'validator-args'), 'utf8')).join('\n');
  assert.match(prompt, new RegExp(`\\b${field}\\b`));
  assert.match(prompt, new RegExp(`\\b${other}\\b`));
});

Then('the validator has not been called', function () {
  assert.equal(existsSync(join(this.workspace, 'validator-calls')), false);
});

Then('it reports that a task hit its limit', function () {
  assert.match(this.result.stdout + this.result.stderr, /task hit its limit/i);
});

Then('each new work commit contains the work for one task', function () {
  const commits = execFileSync('git', ['log', '--format=%H', this.initialCommit + '..HEAD', '--', '.', ':(exclude).factory'], { cwd: this.target, encoding: 'utf8' }).trim().split('\n').filter(Boolean);
  for (const commit of commits) {
    const files = execFileSync('git', ['diff-tree', '--no-commit-id', '--name-only', '-r', commit, '--', '.', ':(exclude).factory'], { cwd: this.target, encoding: 'utf8' }).trim().split('\n').filter(Boolean);
    assert.equal(files.length, 1);
  }
});

Then('no new commit contains the work for the first task', function () {
  const files = execFileSync('git', ['log', '--name-only', '--format=', this.initialCommit + '..HEAD'], { cwd: this.target, encoding: 'utf8' });
  assert.doesNotMatch(files, /(^|\/)alpha\.txt$/m);
});

Then('it reports that the result of validator has no field {string}', function (field: string) {
  assert.match(this.result.stdout + this.result.stderr, new RegExp(`result of validator has no field ["']${field}`, 'i'));
});

Then('the planner was called before the doer', function () {
  const calls = readFileSync(join(this.workspace, 'agent-calls'), 'utf8').trim().split('\n');
  assert.ok(calls.indexOf(this.harness) < calls.indexOf('fake-doer'));
});

After(function () {
  if (this.workspace) {
    rmSync(this.workspace, { recursive: true, force: true });
  }
  if (this.standaloneTarget) {
  rmSync(this.standaloneTarget, { recursive: true, force: true });
}
});
