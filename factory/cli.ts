import { execFileSync, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

type Edge = { from: string; to: string; label?: string };
type Outcome = Record<string, unknown>;
type Config = { harness?: string; lens?: string };
const args = process.argv.slice(2);
const factory = dirname(resolve(process.argv[1]));
const option = (name: string) => { const i = args.indexOf(name); return i < 0 ? undefined : args[i + 1]; };
function fail(message: string): never { console.error(message); process.exit(1); }

function config(name: string): Config | undefined {
  const file = resolve(factory, name, 'machine.json');
  return existsSync(file) ? JSON.parse(readFileSync(file, 'utf8')) as Config : undefined;
}
const line = readFileSync(resolve(factory, 'assembly-line.dot'), 'utf8');
const edges: Edge[] = [...line.matchAll(/\b([A-Za-z][\w-]*)\s*->\s*([A-Za-z][\w-]*)(?:\s*\[\s*label\s*=\s*"([^"]+)"\s*\])?/g)]
  .map(m => ({ from: m[1], to: m[2], label: m[3] }));

for (const name of new Set(edges.flatMap(e => [e.from, e.to]))) {
  if (!['start', 'finish'].includes(name) && !config(name)) fail(`The factory has no machine called "${name}"`);
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
if (args.includes('--check-assembly-line')) { console.log('Assembly line accepted'); process.exit(0); }

const targetArg = option('--target');
if (!targetArg) fail('A target is required');
const seedArg = option('--seed');
if (!seedArg) fail('No seed');
const seed = resolve(seedArg);
if (!existsSync(seed)) fail('No seed');
const target = resolve(targetArg);
const plan = resolve(target, '.factory', 'plan.md');
const maxAttempts = Number(option('--max-attempts') ?? 3);
mkdirSync(target, { recursive: true });
if (spawnSync('git', ['rev-parse', '--show-toplevel'], { cwd: target }).status !== 0) execFileSync('git', ['init'], { cwd: target });

function machineConfig(name: string): Required<Pick<Config, 'harness'>> & Config {
  const stored = config(name)!;
  const oldHarness = option(`--${name}-harness`) ?? (name === 'planner' ? option('--harness') : undefined);
  const oldLens = name === 'validator' ? option('--validator-lens') : undefined;
  return { ...stored, harness: oldHarness ?? stored.harness ?? 'pi', lens: oldLens ?? stored.lens };
}
function parseResult(output: string): Outcome | undefined {
  for (const text of output.trim().split('\n').reverse()) { try { return JSON.parse(text) as Outcome; } catch {} }
}
function fields(name: string): string[] {
  return [...new Set(edges.filter(e => e.from === name && e.label).map(e => e.label!.replace(/^not /, '')))];
}
function route(name: string, result: Outcome): string {
  const outgoing = edges.filter(e => e.from === name);
  const direct = outgoing.find(e => !e.label);
  if (direct) return direct.to;
  for (const edge of outgoing) {
    const negative = edge.label!.startsWith('not ');
    const field = edge.label!.replace(/^not /, '');
    if (!(field in result)) fail(`The result of ${name} has no field "${field}"`);
    if (Boolean(result[field]) !== negative) return edge.to;
  }
  fail(`The result of ${name} did not select an edge`);
}

let findings: unknown;
let completingTask = false;
let attempts = 0;
function prompt(name: string): string {
  const wanted = fields(name);
  const answer = wanted.length
    ? `Finish with one JSON line containing ${wanted.map(f => `"${f}"`).join(' and ')}${name === 'validator' ? ' and "findings"' : ''}.`
    : 'Finish with one JSON line describing the work.';
  if (name === 'planner') return completingTask
    ? `Read the plan at ${JSON.stringify(plan)}.\nThe current task's validated work has been committed.\nMark the current task done, and mark only that task. Inspect the updated plan. Set "complete" to false when any task remains unfinished, and true only when every task is finished.\n${answer}`
    : `Read the seed at ${JSON.stringify(seed)}.\nIf no plan exists at ${JSON.stringify(plan)}, write one there.\nInspect the plan after any write. Set "complete" to false whenever the plan has any unfinished task, and true only when every task is finished. Do not perform a task.\n${answer}`;
  if (name === 'doer') return `Read the seed at ${JSON.stringify(seed)} and the plan at ${JSON.stringify(plan)}.\nImplement the first unfinished task. Do not mark it done.${findings === undefined ? '' : `\nThe validator reported these findings:\n${JSON.stringify(findings)}\nRecord each finding as a subtask of the current task and address it.`}\n${answer}`;
  if (name === 'validator') {
    const work = execFileSync('git', ['status', '--porcelain', '--untracked-files=all', '--', '.', ':(exclude).factory'], { cwd: target, encoding: 'utf8' });
    return `Review the current task's work using ${machineConfig(name).lens ?? ''} as your focus.\nRead the seed at ${JSON.stringify(seed)} and plan at ${JSON.stringify(plan)}.\nThe current task's changed product files are:\n${work}\nDo not change any files.\n${answer}`;
  }
  return answer;
}
function run(name: string): Outcome {
  const execution = spawnSync(machineConfig(name).harness, [prompt(name)], { cwd: target, encoding: 'utf8' });
  if (execution.error) fail(`Could not run the ${name === 'planner' ? 'agent' : name}`);
  process.stdout.write(execution.stdout);
  return parseResult(execution.stdout) ?? fail(`Could not read the ${name === 'planner' ? "agent's" : `${name}'s`} result`);
}
function commit(paths: string[], message: string): void {
  execFileSync('git', ['add', '--', ...paths], { cwd: target });
  if (spawnSync('git', ['diff', '--cached', '--quiet', '--', ...paths], { cwd: target }).status === 1) {
    execFileSync('git', ['commit', '--only', '-m', message, '--', ...paths], { cwd: target });
  }
}

let machine = edges.find(e => e.from === 'start')?.to ?? fail('The assembly line has no start');
while (machine !== 'finish') {
  if (machine === 'doer' && ++attempts > maxAttempts) fail('The task hit its limit');
  const outcome = run(machine);
  const next = route(machine, outcome);
  if (machine === 'validator') findings = outcome.findings;
  if ((machine === 'doer' || machine === 'validator') && next === 'planner') {
    commit(['.', ':(exclude).factory'], 'Factory work');
    completingTask = true; findings = undefined; attempts = 0;
  } else if (machine === 'planner') {
    if (completingTask) commit(['.factory/plan.md'], 'Update plan');
    completingTask = false;
  }
  machine = next;
}
commit(['.factory/plan.md'], 'Update plan');
console.log('factory stopped');
