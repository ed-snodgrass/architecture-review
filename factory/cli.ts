import { execFileSync, spawnSync } from 'node:child_process';
import { appendFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

type Edge = { from: string; to: string; label?: string };
type Outcome = Record<string, unknown>;
type Config = { harness?: string; lens?: string };
type Settings = { target: string; seed: string; line: string };
let activeLogFile: string | undefined;
const args = process.argv.slice(2);
const factory = dirname(resolve(process.argv[1]));
const option = (name: string) => { const i = args.indexOf(name); return i < 0 ? undefined : args[i + 1]; };
function timestamp(): string { return new Date().toISOString(); }
function appendLog(entry: string): void {
  if (!activeLogFile) return;
  mkdirSync(dirname(activeLogFile), { recursive: true });
  appendFileSync(activeLogFile, `${timestamp()} ${entry}\n`);
}
function fail(message: string): never {
  appendLog(`[exit] status=failed reason=${JSON.stringify(message)}`);
  console.error(message);
  process.exit(1);
}
function printHelp(): void {
  console.log(`Factory command

Usage:
  bin/factory --run <name> --target <path> --line <name> --seed <path>
  bin/factory --run <name>

New runs require --run, --target, --line, and --seed. Saved runs can be
resumed with --run alone.

Arguments:
  --run <name>                 Named run to start or resume.
  --target <path>              Target folder; required for a new run.
  --seed <path>                Seed file; required for a new run.
  --line <name>                Target assembly line; required for a new run.
  --harness <command>          Planner harness; default: pi.
  --<machine>-harness <command> Machine-specific harness override; default: pi
                               unless the machine configuration names one.
  --validator-lens <lens>      Validator lens; default: configured lens.
  --max-attempts <number>      Maximum doer attempts; default: 3.
  --quiet                      Disable run logging; logging is enabled by default.
  --check-assembly-line        Validate an assembly line without running it.
  --help                       Show this help and exit successfully.`);
}

if (args.includes('--help')) { printHelp(); process.exit(0); }

const runName = option('--run');
const checking = args.includes('--check-assembly-line');
const quiet = args.includes('--quiet');
const runDirectory = runName ? resolve(factory, 'runs', runName) : undefined;
const settingsFile = runDirectory && resolve(runDirectory, 'run.json');
const logFile = runDirectory && resolve(runDirectory, 'log.md');
activeLogFile = runName && !checking && !quiet ? logFile : undefined;
const saved = settingsFile && existsSync(settingsFile)
  ? JSON.parse(readFileSync(settingsFile, 'utf8')) as Settings
  : undefined;
const supplied = {
  target: option('--target') ? resolve(option('--target')!) : undefined,
  seed: option('--seed') ? resolve(option('--seed')!) : undefined,
  line: option('--line'),
};

if (!checking && !runName) fail('A run is required');
if (saved) {
  for (const key of ['target', 'seed', 'line'] as const) {
    if (supplied[key] && supplied[key] !== saved[key]) fail(`The ${runName} run already has a ${key}`);
  }
}
const target = supplied.target ?? saved?.target;
if (!target) fail('A target is required');
const seed = supplied.seed ?? saved?.seed;
if (!checking && (!seed || !existsSync(seed))) fail('No seed');
const lineName = supplied.line ?? saved?.line;
if (!lineName) fail('An assembly line is required');

const lineDirectory = resolve(target, '.assembly-lines');
const lineFile = resolve(lineDirectory, `${lineName}.dot`);
const line = readFileSync(lineFile, 'utf8');
const edges: Edge[] = [...line.matchAll(/\b([A-Za-z][\w-]*)\s*->\s*([A-Za-z][\w-]*)(?:\s*\[\s*label\s*=\s*"([^"]+)"\s*\])?/g)]
  .map(m => ({ from: m[1], to: m[2], label: m[3] }));
function storedConfig(name: string): Config | undefined {
  const file = resolve(lineDirectory, '.machines', name, 'machine.json');
  return existsSync(file) ? JSON.parse(readFileSync(file, 'utf8')) as Config : undefined;
}
for (const name of new Set(edges.flatMap(e => [e.from, e.to]))) {
  if (!['start', 'finish'].includes(name) && !storedConfig(name)) fail(`The factory has no machine called "${name}"`);
}
function reachesFinish(node: string, seen = new Set<string>()): boolean {
  if (node === 'finish') return true;
  if (seen.has(node)) return false;
  seen.add(node);
  return edges.some(e => e.from === node && reachesFinish(e.to, new Set(seen)));
}
for (const name of [...new Set(edges.map(e => e.from))].reverse()) {
  if (!reachesFinish(name)) fail(`finish cannot be reached from ${name}`);
}
if (checking) { console.log('Assembly line accepted'); process.exit(0); }

mkdirSync(runDirectory!, { recursive: true });
if (!saved) writeFileSync(settingsFile!, JSON.stringify({ target, seed, line: lineName }, null, 2) + '\n');
const plan = resolve(runDirectory!, 'plan.md');
const maxAttempts = Number(option('--max-attempts') ?? 3);
mkdirSync(target, { recursive: true });
if (spawnSync('git', ['rev-parse', '--show-toplevel'], { cwd: target }).status !== 0) execFileSync('git', ['init'], { cwd: target });

function machineConfig(name: string): Required<Pick<Config, 'harness'>> & Config {
  const stored = storedConfig(name)!;
  const oldHarness = option(`--${name}-harness`) ?? (name === 'planner' ? option('--harness') : undefined);
  const oldLens = name === 'validator' ? option('--validator-lens') : undefined;
  return { ...stored, harness: oldHarness ?? stored.harness ?? 'pi', lens: oldLens ?? stored.lens };
}
function parseResult(output: string): Outcome | undefined {
  for (const text of output.trim().split('\n').reverse()) { try { return JSON.parse(text) as Outcome; } catch {} }
}
function agentFailure(name: string, harness: string, execution: ReturnType<typeof spawnSync>): string {
  const details = [
    `machine=${name}`,
    `harness=${JSON.stringify(harness)}`,
    `status=${execution.status === null ? 'null' : execution.status}`,
    `signal=${JSON.stringify(execution.signal)}`,
    `error=${JSON.stringify(execution.error?.message ?? '')}`,
    `stderr=${JSON.stringify(execution.stderr ?? '')}`,
    `stdout=${JSON.stringify(execution.stdout ?? '')}`,
  ].join(' ');
  return `Could not read the ${name === 'planner' ? "agent's" : `${name}'s`} result: ${details}`;
}
function fields(name: string): string[] {
  return [...new Set(edges.filter(e => e.from === name && e.label).map(e => e.label!.replace(/^not /, '')))];
}
function testFiles(): string[] {
  const files: string[] = [];
  function visit(directory: string): void {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === '.git' || entry.name === '.assembly-lines') continue;
      const path = resolve(directory, entry.name);
      if (entry.isDirectory()) visit(path);
      else if (/(^|[\\/])(test|tests)[\\/]|\.(test|spec)\./i.test(path)) files.push(path);
    }
  }
  visit(target!);
  return files;
}
function testSnapshot(): Map<string, string> {
  return new Map(testFiles().map(file => [file, readFileSync(file, 'utf8')]));
}
function testsChanged(before: Map<string, string>): boolean {
  const after = testSnapshot();
  return before.size !== after.size || [...before].some(([file, contents]) => after.get(file) !== contents);
}
function route(name: string, result: Outcome): string {
  const outgoing = edges.filter(e => e.from === name);
  for (const edge of outgoing) {
    if (!edge.label) continue;
    const negative = edge.label!.startsWith('not ');
    const field = edge.label!.replace(/^not /, '');
    if (!(field in result)) fail(`The result of ${name} has no field "${field}"`);
    if (Boolean(result[field]) !== negative) return edge.to;
  }
  const direct = outgoing.find(e => !e.label);
  if (direct) return direct.to;
  fail(`The result of ${name} did not select an edge`);
}
let findings: unknown;
let completingTask = false;
let attempts = 0;
function prompt(name: string): string {
  const wanted = fields(name);
  const answer = wanted.length
    ? `Finish with one JSON line containing ${wanted.map(f => `"${f}"`).join(' and ')}${name === 'validator' || (name === 'doer' && wanted.includes('findings')) ? ' and "findings"' : ''}.`
    : 'Finish with one JSON line describing the work.';
  if (name === 'planner') return completingTask
    ? `Read the plan at ${JSON.stringify(plan)}.\nThe current task's validated work has been committed.\nMark the current task done, and mark only that task. Inspect the updated plan. Set "complete" to false when any task remains unfinished, and true only when every task is finished.\n${answer}`
    : `Read the seed at ${JSON.stringify(seed)}.\nIf no plan exists at ${JSON.stringify(plan)}, write one there.\nInspect the plan after any write. Set "complete" to false whenever the plan has any unfinished task, and true only when every task is finished. Do not perform a task.\n${answer}`;
  if (name === 'doer') {
    const tests = testFiles();
    const revisionRoute = edges.some(e => e.from === 'doer' && e.to === 'test_author' && e.label === 'tests_need_revision');
    return `Read the seed at ${JSON.stringify(seed)} and the plan at ${JSON.stringify(plan)}.\nImplement the first unfinished task. Do not mark it done. Do not modify test files.${revisionRoute ? '\nIf the tests are missing or insufficient, leave them unchanged and return "tests_need_revision": true with the reason in "findings"; do not implement around a faulty test.' : ''}${tests.length ? `\nThe task's tests are:\n${tests.join('\n')}` : '\nNo applicable tests were created.'}${findings === undefined ? '' : `\nThe validator reported these findings:\n${JSON.stringify(findings)}\nRecord each finding as a subtask of the current task and address it.`}\n${answer}`;
  }
  if (name === 'test_author') return `Read the seed at ${JSON.stringify(seed)} and the plan at ${JSON.stringify(plan)}.\nCreate objective tests for the first unfinished task when tests are applicable. If no tests are applicable, say so in your result. Do not implement the task.${findings === undefined ? '' : `\nThe previous machine reported these findings about the tests:\n${JSON.stringify(findings)}\nCorrect the tests and address each finding.`}\n${answer}`;
  if (name === 'validator') {
    const work = execFileSync('git', ['status', '--porcelain', '--untracked-files=all', '--', '.', ':(exclude).assembly-lines'], { cwd: target, encoding: 'utf8' });
    return `Run the current task's tests first. Confirm they pass, then review the current task's work using ${machineConfig(name).lens ?? ''} as your focus.\nRead the seed at ${JSON.stringify(seed)} and plan at ${JSON.stringify(plan)}.\nThe current task's changed product files are:\n${work}\nDo not change any files.\n${answer}`;
  }
  return answer;
}
function execute(name: string, catalyst: string): Outcome {
  const harness = machineConfig(name).harness;
  const execution = spawnSync(harness, [prompt(name)], { cwd: target, encoding: 'utf8', env: { ...process.env, FACTORY_RUN_NAME: runName! } });
  if (execution.error) {
    const message = `Could not run the ${name === 'planner' ? 'agent' : name}: machine=${name} harness=${JSON.stringify(harness)} error=${JSON.stringify(execution.error.message)}`;
    appendLog(`[agent-error] ${message}`);
    fail(message);
  }
  process.stdout.write(execution.stdout);
  if (execution.stderr) process.stderr.write(execution.stderr);
  const outcome = parseResult(execution.stdout) ?? fail(agentFailure(name, harness, execution));
  if (!quiet) appendLog(`[${name}] Catalyst: ${catalyst}. ${JSON.stringify(outcome)}`);
  return outcome;
}
function commitWork(causingMachine: string): void {
  const paths = ['.', ':(exclude).assembly-lines'];
  execFileSync('git', ['add', '--', ...paths], { cwd: target });
  if (spawnSync('git', ['diff', '--cached', '--quiet', '--', ...paths], { cwd: target }).status === 1) {
    const message = `Factory work: ${causingMachine}`;
    execFileSync('git', ['commit', '--only', '-m', message, '--', ...paths], { cwd: target });
    const hash = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: target, encoding: 'utf8' }).trim();
    if (!quiet) appendLog(`[commit] machine=${causingMachine} hash=${hash} message=${JSON.stringify(message)}`);
  }
}
let machine = edges.find(e => e.from === 'start')?.to ?? fail('The assembly line has no start');
let catalyst = 'Seed';
while (machine !== 'finish') {
  if (machine === 'doer' && ++attempts > maxAttempts) fail('The task hit its limit');
  const testsBefore = machine === 'doer' ? testSnapshot() : undefined;
  const outcome = execute(machine, catalyst);
  if (machine === 'doer' && testsChanged(testsBefore!)) fail('The doer changed tests');
  const next = route(machine, outcome);
  if (machine === 'validator') findings = outcome.findings;
  if (machine === 'doer' && next === 'test_author') findings = outcome.findings;
  if ((machine === 'doer' || machine === 'validator') && next === 'planner') {
    commitWork(machine); completingTask = true; findings = undefined; attempts = 0;
  } else if (machine === 'test_author' && next === 'doer') {
    attempts = 0;
    completingTask = false;
  } else if (machine === 'planner') completingTask = false;
  if (machine === 'test_author' && next === 'doer') findings = undefined;
  catalyst = machine;
  if (!quiet && machine === 'doer' && attempts > 1) appendLog(`[doer] Reattempt ${attempts}`);
  machine = next;
}
if (!quiet) appendLog('[exit] status=successful reason="assembly line finished"');
console.log('factory stopped');
