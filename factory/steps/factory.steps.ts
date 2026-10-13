import { After, Given, When, Then, IWorld } from '@cucumber/cucumber';
import assert from 'node:assert/strict';
import { exec, execFileSync, spawnSync } from 'node:child_process';
import { copyFileSync, cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';

Given('a new target', function() {
  this.target = join(this.workspace, 'target');
  mkdirSync(this.target);
});

Given('a new target, with a seed describing a game of Tetris', function () {
  this.targetNumber = (this.targetNumber ?? 0) + 1;
  this.target = join(this.workspace, this.targetNumber === 1 ? 'target' : `target-${this.targetNumber}`);
  mkdirSync(this.target);
  this.seed = join(this.workspace, this.targetNumber === 1 ? 'seed.md' : `seed-${this.targetNumber}.md`);
  copyFileSync(resolve('../tetris/spec.md'), this.seed);
  this.targets ??= {};
  this.targets.tetris ??= this.target;
});

Given('this assembly line:', function (line: string) {
  this.assemblyLine = line;
  this.lineName = 'assembly-line';
  const directory = join(this.target, '.assembly-lines');
  mkdirSync(directory, { recursive: true });
  writeFileSync(join(directory, this.lineName + '.dot'), line);
});

Given('the target folder does not exist', function () {
  rmSync(this.target, { recursive: true });
});

Given('the target is outside any Git repository', function () {
  const previousTarget = this.target;
  this.standaloneTarget = mkdtempSync(join(tmpdir(), 'factory-target-'));
  cpSync(previousTarget, this.standaloneTarget, { recursive: true });
  this.target = this.standaloneTarget;
  if (this.runName && this.runs?.[this.runName]) this.runs[this.runName].target = this.target;
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
  symlinkSync(resolve('node_modules'), join(this.workspace, 'node_modules'));
  writeFileSync(join(this.workspace, '.gitignore'), '/runs/\n');

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

Given('the target has the machines planner, doer and validator', function () {
  for (const machine of ['planner', 'doer', 'validator']) {
    const directory = join(this.target, '.assembly-lines', '.machines', machine);
    mkdirSync(directory, { recursive: true });
    const configuration = machine === 'validator'
      ? { lens: 'single responsibility' }
      : {};
    writeFileSync(join(directory, 'machine.json'), JSON.stringify(configuration));
  }
});

Given('the target has the three big brains', function () {
  for (const machine of [
    'reviewer_1',
    'reviewer_2',
    'reviewer_3',
    'synthesiser',
  ]) {
    const directory = join(
      this.target,
      '.assembly-lines',
      '.machines',
      machine,
    );
    mkdirSync(directory, { recursive: true });
    writeFileSync(join(directory, 'machine.json'), '{}');
  }
});

Given('the target has the machines planner, test_author, doer and validator', function () {
  for (const machine of ['planner', 'test_author', 'doer', 'validator']) {
    const directory = join(this.target, '.assembly-lines', '.machines', machine);
    mkdirSync(directory, { recursive: true });
    const configuration = machine === 'validator'
      ? { lens: 'single responsibility' }
      : {};
    writeFileSync(join(directory, 'machine.json'), JSON.stringify(configuration));
  }
});

const carefulLine = `digraph assembly_line {
  start -> planner
  planner -> doer [label="not complete"]
  planner -> finish [label="complete"]
  doer -> validator
  validator -> doer [label="not satisfied"]
  validator -> planner [label="satisfied"]
}\n`;

Given(
  'the three big brains has replaced the validator on the {string} line',
  function (name: string) {
    for (const machine of ['reviewer_1', 'reviewer_2', 'reviewer_3', 'synthesiser']) {
      const directory = join(this.target, '.assembly-lines', '.machines', machine);
      mkdirSync(directory, { recursive: true });
      writeFileSync(join(directory, 'machine.json'), '{}');
    }
    const file = join(this.target, '.assembly-lines', name + '.dot');
    writeFileSync(file, `digraph assembly_line {
  start -> planner
  planner -> doer [label="not complete"]
  planner -> finish [label="complete"]
  doer -> reviewer_1
  doer -> reviewer_2
  doer -> reviewer_3
  reviewer_1 -> synthesiser
  reviewer_2 -> synthesiser
  reviewer_3 -> synthesiser
  synthesiser -> doer [label="not satisfied"]
  synthesiser -> planner [label="satisfied"]
}\n`);
  },
);

Given("the target has an assembly line {string} on which the doer's work is validated", function (name: string) {
  const directory = join(this.target, '.assembly-lines');
  mkdirSync(directory, { recursive: true });
  writeFileSync(join(directory, name + '.dot'), carefulLine);
});

Given('the target has an assembly line {string} with a test author before the doer', function (name: string) {
  const directory = join(this.target, '.assembly-lines');
  mkdirSync(directory, { recursive: true });
  writeFileSync(join(directory, name + '.dot'), `digraph assembly_line {
  start -> planner
  planner -> test_author [label="not complete"]
  planner -> finish [label="complete"]
  test_author -> doer
  doer -> validator
  validator -> planner [label="satisfied"]
  validator -> doer [label="not satisfied"]
}\n`);
});

Given('an assembly line where test revision requests return to the test author', function () {
  const file = join(this.target, '.assembly-lines', 'careful.dot');
  const line = readFileSync(file, 'utf8')
    .replace('  doer -> validator', '  doer -> test_author [label="tests_need_revision"]\n  doer -> validator')
    .replace('  test_author -> doer', '  test_author -> doer');
  writeFileSync(file, line);
});

Given('an assembly line where incorrect tests return to the test author', function () {
  const file = join(this.target, '.assembly-lines', 'careful.dot');
  const line = readFileSync(file, 'utf8')
    .replace('validator -> planner [label="satisfied"]', 'validator -> test_author [label="tests incorrect"]\n  validator -> planner [label="satisfied"]');
  writeFileSync(file, line);
});

Given('a run named {string}, on the {string} line, with that seed and target', function (run: string, line: string) {
  this.runs ??= {};
  this.runs[run] = { target: this.target, seed: this.seed, line };
  this.runName = run;
  this.plan = join(this.workspace, 'runs', run, 'plan.md');
  this.env = { ...(this.env ?? process.env), FACTORY_TEST_PLAN: this.plan };
});

Given('a run named {string} on the {string} line, with that seed and target', function (run: string, line: string) {
  this.runs ??= {};
  this.runs[run] = { target: this.target, seed: this.seed, line };
  this.runName = run;
  this.plan = join(this.workspace, 'runs', run, 'plan.md');
  this.env = { ...(this.env ?? process.env), FACTORY_TEST_PLAN: this.plan };
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
  rmSync(this.plan, { force: true });
});

Given('a plan with three tasks, none of them done', function() {
  const planDirectory = dirname(this.plan);
  mkdirSync(planDirectory, {recursive: true });
  writeFileSync(
    this.plan,
    '- [ ] alpha\n- [ ] beta\n- [ ] gamma\n',
  );
});

Given('a plan with one task, not done', function () {
  mkdirSync(dirname(this.plan), { recursive: true });
  writeFileSync(this.plan, '- [ ] alpha\n');
});

Given('a plan whose first task is done', function() {
  const planDirectory = dirname(this.plan);
  mkdirSync(planDirectory, { recursive: true });
  writeFileSync(
    this.plan,
    '- [x] alpha\n- [ ] beta\n- [ ] gamma\n',
  );
});

Given('a plan in which every task is done', function () {
  const planDirectory = dirname(this.plan);
  mkdirSync(planDirectory, { recursive: true });
  writeFileSync(
    this.plan,
    '- [x] alpha\n- [x] beta\n',
  );
});

Given('the validator says {string} before its result', function (message: string) {
  this.env.FACTORY_TEST_VALIDATOR_PREAMBLE = message;
});

Then(
  'the plan has the tasks {string} and {string}, and no others', 
  function (first: string, second: string) {
    const plan = readFileSync(
      this.plan,
      'utf8',
    );
    const tasks = [...plan.matchAll(/^- \[[ x]\] (.+)$/gm)].map(match => match[1]);

    assert.deepEqual(tasks, [first, second]);
  },
);

Then('the plan still has those three tasks', function () {
  const plan = readFileSync(
    this.plan,
    'utf8',
  );
  const tasks = [...plan.matchAll(/^- \[[ x]\] (.+)$/gm)]
    .map(match => match[1]);

  assert.deepEqual(tasks, ['alpha', 'beta', 'gamma']);
});

Then('there is no plan', function() {
  assert.equal(
    existsSync(this.plan),
    false,
    'Expected no plan in the target',
  );
});

Then(
  /^(?:there is a plan|the plan is \.factory\/plan\.md in the target)$/,
  function () {
  assert.ok(
    existsSync(this.plan),
    'Expected a plan in the target',
  );
});

Then("there is no plan in the factory's folder", function () {
  assert.equal(
    existsSync(join(this.target, '.factory', 'plan.md')),
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

Then("it reports the validator's execution details", function () {
  const output = this.result.stdout + this.result.stderr;
  assert.match(output, /machine=validator/);
  assert.match(output, /status=0/);
  assert.ok(output.includes('stdout="The work needs another look.\\n"'));
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

const plan = process.env.FACTORY_TEST_PLAN;
const prompt = process.argv.slice(2).join('\n');
fs.mkdirSync(path.dirname(plan), { recursive: true });

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
    ...(this.env ?? process.env),
    PATH: agentBin + ':' + process.env.PATH,
    FACTORY_TEST_WORKSPACE: this.workspace,
  };
});

Given('the planner plans the task alpha', function () {
  const agentBin = join(this.workspace, 'agents');
  mkdirSync(agentBin, { recursive: true });
  const planner = String.raw`#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const workspace = process.env.FACTORY_TEST_WORKSPACE;
const plan = process.env.FACTORY_TEST_PLAN;
fs.appendFileSync(path.join(workspace, 'agent-calls'), 'fake-planner\n');
fs.mkdirSync(path.dirname(plan), { recursive: true });
if (!fs.existsSync(plan)) fs.writeFileSync(plan, '- [ ] alpha\n');
let text = fs.readFileSync(plan, 'utf8');
if (process.argv.slice(2).join('\n').includes('Mark the current task done')) {
  text = text.replace('- [ ] alpha', '- [x] alpha');
  fs.writeFileSync(plan, text);
}
console.log(JSON.stringify({ complete: !text.includes('- [ ]') }));
`;
  const testAuthor = String.raw`#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const workspace = process.env.FACTORY_TEST_WORKSPACE;
fs.appendFileSync(path.join(workspace, 'agent-calls'), 'test_author\n');
fs.appendFileSync(path.join(workspace, 'test-author-args-log'), JSON.stringify(process.argv.slice(2)) + '\n');
if (process.env.FACTORY_TEST_NO_TESTS !== '1') {
  fs.writeFileSync('alpha.test.js', process.argv.join(' ').includes('validator reported') ? 'module.exports = corrected;\n' : 'module.exports = true;\n');
}
console.log(JSON.stringify({ applicable: process.env.FACTORY_TEST_NO_TESTS !== '1' }));
`;
  const doer = String.raw`#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const workspace = process.env.FACTORY_TEST_WORKSPACE;
fs.appendFileSync(path.join(workspace, 'agent-calls'), 'fake-doer\n');
fs.writeFileSync(path.join(workspace, 'doer-args'), JSON.stringify(process.argv.slice(2)));
fs.appendFileSync(path.join(workspace, 'doer-args-log'), JSON.stringify(process.argv.slice(2)) + '\n');
if (process.env.FACTORY_TEST_DOER_CHANGES_TEST === '1') fs.writeFileSync('alpha.test.js', 'module.exports = false;\n');
fs.writeFileSync('alpha.txt', 'alpha\n');
const revisionMarker = path.join(workspace, 'doer-requested-test-revision');
const requestsRevision = process.env.FACTORY_TEST_DOER_NEEDS_TEST_REVISION === '1'
  && !fs.existsSync(revisionMarker);
if (requestsRevision) {
  fs.writeFileSync(revisionMarker, 'requested\n');
  console.log(JSON.stringify({
    task: 'alpha',
    tests_need_revision: true,
    findings: ['The test does not cover the required behavior.'],
  }));
} else {
  console.log(JSON.stringify({
    task: 'alpha',
    tests_need_revision: false,
    findings: [],
  }));
}
`;
  const validator = String.raw`#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const workspace = process.env.FACTORY_TEST_WORKSPACE;
fs.appendFileSync(path.join(workspace, 'agent-calls'), 'fake-validator\n');
fs.writeFileSync(path.join(workspace, 'validator-args'), JSON.stringify(process.argv.slice(2)));
  const calls = path.join(workspace, 'validator-calls');
  fs.appendFileSync(calls, 'called\n');
  const count = fs.readFileSync(calls, 'utf8').trim().split('\n').length;
  if (process.env.FACTORY_TEST_TESTS_INCORRECT_FIRST === '1' && count === 1) {
    console.log(JSON.stringify({ satisfied: false, 'tests incorrect': true, findings: ['The tests misread the task.'] }));
  } else {
    console.log(JSON.stringify({ satisfied: true, 'tests incorrect': false, findings: [] }));
  }
`;
  for (const [name, script] of [
    ['fake-planner', planner],
    ['fake-test-author', testAuthor],
    ['fake-doer', doer],
    ['fake-validator', validator],
  ] as const) writeFileSync(join(agentBin, name), script, { mode: 0o755 });
  this.harness = join(agentBin, 'fake-planner');
  this.testAuthorHarness = join(agentBin, 'fake-test-author');
  this.doerHarness = join(agentBin, 'fake-doer');
  this.validatorHarness = join(agentBin, 'fake-validator');
  this.env = {
    ...(this.env ?? process.env),
    FACTORY_TEST_WORKSPACE: this.workspace,
  };
});

Given('the test author says no tests are applicable', function () {
  this.env.FACTORY_TEST_NO_TESTS = '1';
});

Given('the test author has written the task\'s tests', function () {
  this.env.FACTORY_TEST_NO_TESTS = undefined;
});

Given('the doer changes a test while implementing the task', function () {
  this.env.FACTORY_TEST_DOER_CHANGES_TEST = '1';
});

Given('the doer says the tests need revision with findings', function () {
  this.env.FACTORY_TEST_DOER_NEEDS_TEST_REVISION = '1';
});

Given('the validator says the tests are incorrect the first time', function () {
  this.env.FACTORY_TEST_TESTS_INCORRECT_FIRST = '1';
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

const plan = fs.readFileSync(process.env.FACTORY_TEST_PLAN, 'utf8');

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
fs.appendFileSync(path.join(workspace, 'validator-runs'), process.env.FACTORY_RUN_NAME + '\n');
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

Given('every reviewer is always satisfied', function () {
  const script = String.raw`#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const workspace = process.env.FACTORY_TEST_WORKSPACE;
const name = path.basename(process.argv[1]).replace('fake-', '');
fs.appendFileSync(path.join(workspace, name + '-calls'), 'called\n');
const argsFile = path.join(workspace, name + '-args');
if (!fs.existsSync(argsFile)) fs.writeFileSync(argsFile, JSON.stringify(process.argv.slice(2)));
if (process.env.FACTORY_TEST_REVIEWERS_WAIT === '1') {
  const begun = path.join(workspace, 'reviewers-begun');
  fs.appendFileSync(begun, name + '\n');
  while (fs.readFileSync(begun, 'utf8').trim().split('\n').length < 3) {
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 10);
  }
}
if (name === 'reviewer_2' && process.env.FACTORY_TEST_REVIEWER_2_PROSE === '1') {
  console.log('This review has no machine-readable result.');
  process.exit(0);
}
const findings = JSON.parse(process.env.FACTORY_TEST_REVIEWER_FINDINGS || '{}')[name];
console.log(JSON.stringify({ satisfied: !findings, findings: findings ? [findings] : [] }));
`;
  for (const reviewer of ['reviewer_1', 'reviewer_2', 'reviewer_3']) {
    const harness = join(this.workspace, 'agents', 'fake-' + reviewer);
    writeFileSync(harness, script, { mode: 0o755 });
    writeFileSync(
      join(this.target, '.assembly-lines', '.machines', reviewer, 'machine.json'),
      JSON.stringify({ harness, lens: 'single responsibility' }),
    );
  }
});

Given('the synthesiser is always satisfied', function () {
  const harness = join(this.workspace, 'agents', 'fake-synthesiser');
  const script = String.raw`#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const workspace = process.env.FACTORY_TEST_WORKSPACE;
const calls = path.join(workspace, 'synthesiser-calls');
fs.appendFileSync(calls, 'called\n');
fs.writeFileSync(path.join(workspace, 'synthesiser-args'), JSON.stringify(process.argv.slice(2)));
const count = fs.readFileSync(calls, 'utf8').trim().split('\n').length;
const reject = process.env.FACTORY_TEST_SYNTHESISER_REJECT_ALWAYS === '1'
  || (process.env.FACTORY_TEST_SYNTHESISER_REJECT_FIRST === '1' && count === 1);
console.log(JSON.stringify({
  satisfied: !reject,
  findings: reject ? ['The combined review found a problem.'] : [],
}));
`;
  writeFileSync(harness, script, { mode: 0o755 });
  writeFileSync(
    join(this.target, '.assembly-lines', '.machines', 'synthesiser', 'machine.json'),
    JSON.stringify({ harness }),
  );
});

Given('no reviewer finishes until all three have begun', function () {
  this.env.FACTORY_TEST_REVIEWERS_WAIT = '1';
});

Given('every reviewer is not satisfied, with a finding of its own: {string}, {string} or {string}', function (first: string, second: string, third: string) {
  this.env.FACTORY_TEST_REVIEWER_FINDINGS = JSON.stringify({ reviewer_1: first, reviewer_2: second, reviewer_3: third });
});

Given('the second reviewer is not satisfied, with the finding {string}', function (finding: string) {
  this.env.FACTORY_TEST_REVIEWER_FINDINGS = JSON.stringify({ reviewer_2: finding });
});

Given('the synthesiser is never satisfied', function () {
  this.env.FACTORY_TEST_SYNTHESISER_REJECT_ALWAYS = '1';
});

Given('the synthesiser is not satisfied the first time', function () {
  this.env.FACTORY_TEST_SYNTHESISER_REJECT_FIRST = '1';
});

Given('the second reviewer answers in prose, with no result', function () {
  this.env.FACTORY_TEST_REVIEWER_2_PROSE = '1';
});

Given('the second reviewer cannot be run', function () {
  writeFileSync(
    join(this.target, '.assembly-lines', '.machines', 'reviewer_2', 'machine.json'),
    JSON.stringify({ harness: join(this.workspace, 'missing-reviewer') }),
  );
});

Given("the reviewers' lens is testability", function () {
  for (const reviewer of ['reviewer_1', 'reviewer_2', 'reviewer_3']) {
    const file = join(this.target, '.assembly-lines', '.machines', reviewer, 'machine.json');
    const configuration = JSON.parse(readFileSync(file, 'utf8'));
    writeFileSync(file, JSON.stringify({ ...configuration, lens: 'testability' }));
  }
});

Given('the factory allows at most two attempts at a task', function () {
  this.maxAttempts = 2;
});

Given('the factory allows at most one attempt at a task', function () {
  this.maxAttempts = 1;
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

const plan = process.env.FACTORY_TEST_PLAN;
fs.mkdirSync(path.dirname(plan), { recursive: true });

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
    ...(this.env ?? process.env),
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

function runFactory(this: IWorld, run = this.runName, onlyName = false, target = undefined, quiet = false) {
  const args = [join(this.workspace, 'run'), '--run', run];
  const settings = this.runs?.[run];
  if (!onlyName && settings) {
    if (!this.omitTarget) args.push('--target', target ?? settings.target);
    args.push('--line', settings.line, '--seed', settings.seed);
  }

  if (this.harness !== undefined) {
    args.push('--harness', this.harness);
  }

  if (this.doerHarness !== undefined) {
    args.push('--doer-harness', this.doerHarness);
  }

  if (this.testAuthorHarness !== undefined) {
    args.push('--test_author-harness', this.testAuthorHarness);
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

  if (quiet) args.push('--quiet');

  this.result = spawnSync('bash', args, {
    cwd: this.workspace,
    env: this.env ?? process.env,
    encoding: 'utf8',
    timeout: 3000,
    killSignal: 'SIGKILL',
  });
}

When('the factory runs', function () {
  runFactory.call(this);
});

When('the factory runs with {string}', function (argument: string) {
  this.result = spawnSync('bash', [join(this.workspace, 'run'), argument], {
    cwd: this.workspace,
    env: this.env ?? process.env,
    encoding: 'utf8',
  });
});

When('the factory runs the {string} run', function (run: string) {
  this.runName = run;
  this.plan = join(this.workspace, 'runs', run, 'plan.md');
  this.env = { ...(this.env ?? process.env), FACTORY_TEST_PLAN: this.plan };
  runFactory.call(this, run);
});

When('the factory runs the {string} run quietly', function (run: string) {
  this.runName = run;
  this.plan = join(this.workspace, 'runs', run, 'plan.md');
  this.env = { ...(this.env ?? process.env), FACTORY_TEST_PLAN: this.plan };
  runFactory.call(this, run, false, undefined, true);
});

When('the factory reads the assembly line', function () {
  this.result = spawnSync('bash', [join(this.workspace, 'run'), '--check-assembly-line', '--target', this.target, '--line', this.lineName], {
    cwd: this.workspace,
    env: this.env ?? process.env,
    encoding: 'utf8',
  });
});

When(/^the factory runs (one pass|to completion)$/, function () { runFactory.call(this); });

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
    prompt.includes(this.plan),
    'Expected the plan path',
  );
});

Then('the test author has been called before the doer', function () {
  const calls = readFileSync(join(this.workspace, 'agent-calls'), 'utf8').trim().split('\n');
  assert.ok(calls.indexOf('test_author') < calls.indexOf('fake-doer'));
});

Then("the doer was given the task's tests", function () {
  const prompt = JSON.parse(readFileSync(join(this.workspace, 'doer-args'), 'utf8')).join('\n');
  assert.match(prompt, /alpha\.test\.js/);
});

Then('the doer has been called', function () {
  const calls = readFileSync(join(this.workspace, 'agent-calls'), 'utf8').trim().split('\n');
  assert.ok(calls.includes('fake-doer'));
});

Then('the run continues without tests', function () {
  assert.equal(existsSync(join(this.target, 'alpha.test.js')), false);
});

Then("the test author has been called again with the validator's findings", function () {
  const calls = readFileSync(join(this.workspace, 'agent-calls'), 'utf8').trim().split('\n');
  assert.equal(calls.filter(call => call === 'test_author').length, 2);
  const prompts = readFileSync(join(this.workspace, 'test-author-args-log'), 'utf8');
  assert.match(prompts, /tests misread the task/i);
});

Then("the test author has been called again with the doer's findings", function () {
  const calls = readFileSync(join(this.workspace, 'agent-calls'), 'utf8').trim().split('\n');
  assert.equal(calls.filter(call => call === 'test_author').length, 2);
  const prompts = readFileSync(join(this.workspace, 'test-author-args-log'), 'utf8');
  assert.match(prompts, /test does not cover the required behavior/i);
});

Then('the doer attempt count starts over after the revised tests', function () {
  const calls = readFileSync(join(this.workspace, 'doer-args-log'), 'utf8').trim().split('\n');
  assert.ok(calls.length >= 2);
  assert.equal(this.result.status, 0, this.result.stderr);
});
Then('the run finishes after the corrected tests pass', function () {
  assert.equal(this.result.status, 0, this.result.stderr);
});

Then('the factory reports that the doer changed tests', function () {
  assert.match(this.result.stdout + this.result.stderr, /doer changed tests/i);
});

Then("the doer's work has not been committed", function () {
  const commits = execFileSync('git', ['log', '--format=%H', this.initialCommit + '..HEAD'], {
    cwd: this.target,
    encoding: 'utf8',
  }).trim();
  assert.equal(commits, '');
});

Then("the validator was told to run the task's tests first", function () {
  assert.ok(
    existsSync(join(this.workspace, 'validator-args')),
    `${this.result.stdout}\n${this.result.stderr}`,
  );
  const prompt = JSON.parse(readFileSync(join(this.workspace, 'validator-args'), 'utf8')).join('\n');
  assert.match(prompt, /Run the current task's tests first/);
});

Then('the validator was given the lens {string}', function (lens: string) {
  const prompt = JSON.parse(readFileSync(join(this.workspace, 'validator-args'), 'utf8')).join('\n');
  assert.match(prompt, new RegExp(`\\b${lens}\\b`));
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
  const argsFile = existsSync(join(this.workspace, 'synthesiser-args'))
    ? join(this.workspace, 'synthesiser-args')
    : join(this.workspace, 'validator-args');
  const args: string[] = JSON.parse(readFileSync(
    argsFile,
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

Then("the doer was given the synthesiser's findings", function () {
  const prompt = readFileSync(join(this.workspace, 'doer-args-log'), 'utf8');
  assert.match(prompt, /combined review found a problem/i);
});

Then('every reviewer has been called once', function () {
  for (const reviewer of ['reviewer_1', 'reviewer_2', 'reviewer_3']) {
    const calls = readFileSync(join(this.workspace, reviewer + '-calls'), 'utf8').trim().split('\n');
    assert.equal(calls.length, 1);
  }
});

Then('the synthesiser has been called once', function () {
  const calls = readFileSync(join(this.workspace, 'synthesiser-calls'), 'utf8').trim().split('\n');
  assert.equal(calls.length, 1);
});

Then('the synthesiser has not been called', function () {
  assert.equal(existsSync(join(this.workspace, 'synthesiser-calls')), false);
});

Then('every reviewer was asked for a result', function () {
  for (const reviewer of ['reviewer_1', 'reviewer_2', 'reviewer_3']) {
    const prompt = JSON.parse(readFileSync(join(this.workspace, reviewer + '-args'), 'utf8')).join('\n');
    assert.match(prompt, /JSON line/i);
  }
});

Then('the synthesiser was given {string}, {string} and {string}', function (first: string, second: string, third: string) {
  const prompt = JSON.parse(readFileSync(join(this.workspace, 'synthesiser-args'), 'utf8')).join('\n');
  for (const finding of [first, second, third]) assert.match(prompt, new RegExp(finding));
});

Then('the synthesiser was given {string}', function (finding: string) {
  const prompt = JSON.parse(readFileSync(join(this.workspace, 'synthesiser-args'), 'utf8')).join('\n');
  assert.match(prompt, new RegExp(finding));
});

Then('it was not given {string}', function (finding: string) {
  const prompt = readFileSync(join(this.workspace, 'doer-args-log'), 'utf8');
  assert.doesNotMatch(prompt, new RegExp(finding));
});

Then("it reports that it could not read reviewer_2's result", function () {
  assert.match(this.result.stdout + this.result.stderr, /could not read reviewer_2's result/i);
});

Then('it reports that it could not run reviewer_2', function () {
  assert.match(this.result.stdout + this.result.stderr, /could not run reviewer_2/i);
});

Then('every reviewer was given the work for the second task', function () {
  for (const reviewer of ['reviewer_1', 'reviewer_2', 'reviewer_3']) {
    const prompt = JSON.parse(readFileSync(join(this.workspace, reviewer + '-args'), 'utf8')).join('\n');
    assert.match(prompt, /beta\.txt/);
  }
});

Then('every reviewer was given the same prompt', function () {
  const prompts = ['reviewer_1', 'reviewer_2', 'reviewer_3'].map(reviewer =>
    JSON.parse(readFileSync(join(this.workspace, reviewer + '-args'), 'utf8')).join('\n'),
  );
  assert.equal(new Set(prompts).size, 1);
});

Then('every reviewer was given {string}', function (lens: string) {
  for (const reviewer of ['reviewer_1', 'reviewer_2', 'reviewer_3']) {
    const prompt = JSON.parse(readFileSync(join(this.workspace, reviewer + '-args'), 'utf8')).join('\n');
    assert.match(prompt, new RegExp(lens, 'i'));
  }
});

Then('the plan shows the first task as done', function () {
  const plan = readFileSync(
    this.plan,
    'utf8',
  );
  assert.match(plan, /^- \[x\] alpha$/m);
});

Then('the plan shows the first two tasks as done', function () {
  const plan = readFileSync(
    this.plan,
    'utf8',
  );

  assert.match(plan, /^- \[x\] alpha$/m);
  assert.match(plan, /^- \[x\] beta$/m);
});

Then('the plan shows the other two as not done', function () {
  const plan = readFileSync(
    this.plan,
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

Then('the factory exits successfully', function () {
  assert.equal(this.result.status, 0, this.result.stderr);
});

Then('the help output describes the factory command', function () {
  assert.match(this.result.stdout, /Factory command/);
});

Then('the help output describes {string}', function (argument: string) {
  assert.match(this.result.stdout, new RegExp(argument.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
});

Then('the help output says those settings are required for a new run', function () {
  assert.match(this.result.stdout, /New runs require --run, --target, --line, and --seed/i);
});

Then('the help output says the default harness is {string}', function (harness: string) {
  assert.match(this.result.stdout, new RegExp(`default: ${harness}`));
});

Then('the help output describes machine-specific harness overrides', function () {
  assert.match(this.result.stdout, /Machine-specific harness override/);
});

Then('the help output says the default maximum attempts is {string}', function (attempts: string) {
  assert.match(this.result.stdout, new RegExp(`Maximum doer attempts; default: ${attempts}`));
});

Then('the help output says logging is enabled by default', function () {
  assert.match(this.result.stdout, /logging is enabled by default/i);
});

Then(
  /^the plan shows every task as (done|not done)$/,
  function (state: string) {
    const plan = readFileSync(
      this.plan,
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
  const file = join(this.target, '.assembly-lines', this.lineName + '.dot');
  const line = readFileSync(file, 'utf8')
    .replace(/^\s*doer -> validator.*$/m, '  doer -> planner')
    .replace(/^\s*validator -> .*$(?:\n)?/gm, '');
  writeFileSync(file, line);
});

Given('{string} is misspelt {string} throughout the assembly line', function (from: string, to: string) {
  const file = join(this.target, '.assembly-lines', this.lineName + '.dot');
  writeFileSync(file, readFileSync(file, 'utf8').replaceAll(from, to));
});

Given('the edge from validator to planner has been taken out', function () {
  const file = join(this.target, '.assembly-lines', this.lineName + '.dot');
  writeFileSync(file, readFileSync(file, 'utf8').replace(/^\s*validator -> planner.*$(?:\n)?/m, ''));
});

Then('it reports that it has no machine called {string}', function (name: string) {
  assert.match(this.result.stdout + this.result.stderr, new RegExp(`no machine called ["']?${name}`, 'i'));
});

Then('it reports that finish cannot be reached from validator', function () {
  assert.match(this.result.stdout + this.result.stderr, /finish cannot be reached from validator/i);
});

Then('it reports that the branches from doer do not meet', function () {
  assert.match(
    this.result.stdout + this.result.stderr,
    /branches from doer do not meet/i,
  );
});

Given('no harness is chosen for the validator', function () {
  this.validatorHarness = undefined;
});

Given('the factory allows at most three attempts at a task', function () {
  this.maxAttempts = 3;
});

Given('the edges from validator are labelled {string} and {string}', function (positive: string, negative: string) {
  const file = join(this.target, '.assembly-lines', this.runs[this.runName].line + '.dot');
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

Then('the work commits name the machine that caused each commit', function () {
  const messages = execFileSync('git', ['log', '--format=%s', this.initialCommit + '..HEAD'], {
    cwd: this.target,
    encoding: 'utf8',
  }).trim().split('\n').filter(Boolean);
  assert.ok(messages.length > 0);
  assert.ok(messages.every(message => /^Factory work: (doer|validator)$/.test(message)));
});

Then('the run log records each work commit', function () {
  const log = readFileSync(join(this.workspace, 'runs', this.runName, 'log.md'), 'utf8');
  const commits = execFileSync('git', ['log', '--format=%H', this.initialCommit + '..HEAD'], {
    cwd: this.target,
    encoding: 'utf8',
  }).trim().split('\n').filter(Boolean);
  for (const hash of commits) assert.match(log, new RegExp(`\\[commit\\].*hash=${hash}\\b`));
});

Then('every work commit message starts with {string}', function (prefix: string) {
  const messages = execFileSync('git', ['log', '--format=%s', this.initialCommit + '..HEAD'], {
    cwd: this.target,
    encoding: 'utf8',
  }).trim().split('\n').filter(Boolean);
  assert.ok(messages.length > 0);
  assert.ok(messages.every(message => message.startsWith(prefix)));
});

Then('every work commit is recorded in the run log with its hash', function () {
  const log = readFileSync(join(this.workspace, 'runs', this.runName, 'log.md'), 'utf8');
  const commits = execFileSync('git', ['log', '--format=%H', this.initialCommit + '..HEAD'], {
    cwd: this.target,
    encoding: 'utf8',
  }).trim().split('\n').filter(Boolean);
  assert.ok(commits.length > 0);
  for (const hash of commits) assert.match(log, new RegExp(`\\[commit\\].*hash=${hash}\\b`));
});

Then('the run log records no work commit', function () {
  const log = existsSync(join(this.workspace, 'runs', this.runName, 'log.md'))
    ? readFileSync(join(this.workspace, 'runs', this.runName, 'log.md'), 'utf8')
    : '';
  assert.doesNotMatch(log, /^\S+ \[commit\]/m);
});

Then('the run log records no work commit for the handoff', function () {
  const log = readFileSync(join(this.workspace, 'runs', this.runName, 'log.md'), 'utf8');
  assert.doesNotMatch(log, /machine=doer/);
});

Then('it reports that the result of validator has no field {string}', function (field: string) {
  assert.match(this.result.stdout + this.result.stderr, new RegExp(`result of validator has no field ["']${field}`, 'i'));
});

Then('the planner was called before the doer', function () {
  const calls = readFileSync(join(this.workspace, 'agent-calls'), 'utf8').trim().split('\n');
  assert.ok(calls.indexOf(this.harness) < calls.indexOf('fake-doer'));
});

Given('the validator has been taken out of the {string} line, so the doer goes straight to the planner', function (name: string) {
  const file = join(this.target, '.assembly-lines', name + '.dot');
  const line = readFileSync(file, 'utf8')
    .replace(/^\s*doer -> validator.*$/m, '  doer -> planner')
    .replace(/^\s*validator -> .*$(?:\n)?/gm, '');
  writeFileSync(file, line);
});

Given("the target has an assembly line {string} on which the doer goes straight to the planner", function (name: string) {
  const directory = join(this.target, '.assembly-lines');
  mkdirSync(directory, { recursive: true });
  writeFileSync(join(directory, name + '.dot'), carefulLine
    .replace(/^\s*doer -> validator.*$/m, '  doer -> planner')
    .replace(/^\s*validator -> .*$(?:\n)?/gm, ''));
});

Given('a plan for each run with three tasks of its own, none of them done', function () {
  for (const name of Object.keys(this.runs)) {
    const plan = join(this.workspace, 'runs', name, 'plan.md');
    mkdirSync(dirname(plan), { recursive: true });
    writeFileSync(plan, `- [ ] ${name}-alpha\n- [ ] ${name}-beta\n- [ ] ${name}-gamma\n`);
  }
});

Then('the validator was called for the {string} run', function (name: string) {
  const runs = readFileSync(join(this.workspace, 'validator-runs'), 'utf8').trim().split('\n');
  assert.ok(runs.includes(name));
});

Then('the validator was not called for the {string} run', function (name: string) {
  const file = join(this.workspace, 'validator-runs');
  const runs = existsSync(file) ? readFileSync(file, 'utf8').trim().split('\n') : [];
  assert.equal(runs.includes(name), false);
});

Then('the run log contains a doer action prompted by {string}', function (catalyst: string) {
  const log = readFileSync(join(this.workspace, 'runs', this.runName, 'log.md'), 'utf8');
  assert.match(log, new RegExp(`^\\S+ \\[doer\\] Catalyst: ${catalyst}\\. .+$`, 'm'));
});

Then('the run log contains a date, machine name, catalyst, and summary on every line', function () {
  const lines = readFileSync(join(this.workspace, 'runs', this.runName, 'log.md'), 'utf8').trim().split('\n');
  assert.ok(lines.length > 0);
  assert.ok(lines.every(line => /^\d{4}-\d{2}-\d{2}T[^ ]+ (?:\[(planner|doer|validator)\] Catalyst: .+\. .+|\[commit\] machine=(?:doer|validator) hash=\S+ message="[^"]+"|\[exit\] status=(?:successful|failed) .+|\[doer\] Reattempt \d+)$/.test(line)));
});

Then('the run log uses exact machine names for catalysts', function () {
  const log = readFileSync(join(this.workspace, 'runs', this.runName, 'log.md'), 'utf8');
  assert.match(log, /\[doer\] Catalyst: planner\./);
  assert.doesNotMatch(log, /Catalyst: Planner|Catalyst: Validator Feedback/);
});

Then('the run log records the run execution timestamp', function () {
  const lines = readFileSync(join(this.workspace, 'runs', this.runName, 'log.md'), 'utf8').trim().split('\n');
  assert.ok(lines.every(line => /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z /.test(line)));
});

Then('the run log records the successful exit', function () {
  const log = readFileSync(join(this.workspace, 'runs', this.runName, 'log.md'), 'utf8');
  assert.match(log, /\[exit\] status=successful reason="assembly line finished"/);
});

Then('the run log records the doer reattempt', function () {
  const log = readFileSync(join(this.workspace, 'runs', this.runName, 'log.md'), 'utf8');
  assert.match(log, /\[doer\] Reattempt 2/);
});

Then('the run log records the failed exit and reason', function () {
  const log = readFileSync(join(this.workspace, 'runs', this.runName, 'log.md'), 'utf8');
  assert.match(log, /\[exit\] status=failed reason=.*task hit its limit/);
});

Then('the run log does not exist', function () {
  assert.equal(existsSync(join(this.workspace, 'runs', this.runName, 'log.md')), false);
});

Given('a new target, with a seed describing a game of Snake', function () {
  this.target = join(this.workspace, 'snake-target');
  mkdirSync(this.target);
  this.seed = join(this.workspace, 'snake-seed.md');
  writeFileSync(this.seed, '# Snake\n\nBuild a game of Snake.\n');
  this.targets ??= {};
  this.targets.snake = this.target;
});

Given('the {string} line has been copied into the target', function (name: string) {
  const source = join(this.targets.tetris, '.assembly-lines', name + '.dot');
  const directory = join(this.target, '.assembly-lines');
  mkdirSync(directory, { recursive: true });
  copyFileSync(source, join(directory, name + '.dot'));
});

Then("each target holds only its own run's work", function () {
  for (const [name, target] of Object.entries(this.targets) as [string, string][]) {
    assert.ok(existsSync(join(target, `${name}-alpha.txt`)) || existsSync(join(target, 'alpha.txt')));
    for (const [other, otherTarget] of Object.entries(this.targets) as [string, string][]) {
      if (other !== name) assert.equal(existsSync(join(target, `${other}-alpha.txt`)), false, `${target} contains ${other}'s work`);
    }
  }
});

Given('{string} is misspelt {string} throughout the {string} line', function (from: string, to: string, name: string) {
  const file = join(this.target, '.assembly-lines', name + '.dot');
  writeFileSync(file, readFileSync(file, 'utf8').replaceAll(from, to));
});

Then("the plan is plan.md in the factory's runs folder, under tetris", function () {
  assert.ok(existsSync(join(this.workspace, 'runs', 'tetris', 'plan.md')));
});

Then('there is no plan in the target', function () {
  assert.equal(existsSync(join(this.target, '.factory', 'plan.md')), false);
});

Given('the {string} run has been started', function (name: string) {
  const settings = this.runs[name];
  const directory = join(this.workspace, 'runs', name);
  mkdirSync(directory, { recursive: true });
  writeFileSync(join(directory, 'run.json'), JSON.stringify(settings, null, 2) + '\n');
});

When('the factory runs the {string} run, given only its name', function (name: string) {
  this.runName = name;
  this.plan = join(this.workspace, 'runs', name, 'plan.md');
  this.env = { ...(this.env ?? process.env), FACTORY_TEST_PLAN: this.plan };
  runFactory.call(this, name, true);
});

Then('the validator has been called twice', function () {
  const calls = readFileSync(join(this.workspace, 'validator-calls'), 'utf8').trim().split('\n');
  assert.equal(calls.length, 2);
});

When('the factory runs the {string} run with that target', function (name: string) {
  this.result = spawnSync('bash', [join(this.workspace, 'run'), '--run', name, '--target', this.target], {
    cwd: this.workspace, env: this.env ?? process.env, encoding: 'utf8',
  });
});

Then('the factory refuses', function () {
  assert.notEqual(this.result.status, 0);
});

Then('it says the {string} run already has a target', function (name: string) {
  assert.match(this.result.stdout + this.result.stderr, new RegExp(`${name} run already has a target`, 'i'));
});

Then('each run has its own plan', function () {
  for (const name of Object.keys(this.runs)) assert.ok(existsSync(join(this.workspace, 'runs', name, 'plan.md')));
});

After(function () {
  if (this.workspace) {
    rmSync(this.workspace, { recursive: true, force: true });
  }
  if (this.standaloneTarget) {
  rmSync(this.standaloneTarget, { recursive: true, force: true });
}
});
