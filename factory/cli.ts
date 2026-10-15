import { execFileSync, spawn, spawnSync } from 'node:child_process';
import { appendFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

type Edge = { from: string; to: string; label?: string };
type Outcome = Record<string, unknown>;
type Config = { harness?: string; lens?: string };
type Settings = { target: string; seed: string; line: string };
type RepairFinding = {
  id: string;
  requirement: string;
  evidence: string;
  repair: string;
  verification: string;
  source?: string;
};
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
const hasTestAuthor = edges.some(edge => edge.from === 'test_author' || edge.to === 'test_author');
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
for (const name of new Set(edges.map(edge => edge.from))) {
  const outgoing = edges.filter(edge => edge.from === name);
  if (outgoing.length < 2 || outgoing.some(edge => edge.label)) continue;

  const branchEdges = outgoing.map(edge =>
    edges.filter(candidate => candidate.from === edge.to),
  );
  const meetingPoints = branchEdges.map(branch => branch[0]?.to);

  if (
    branchEdges.some(
      branch => branch.length !== 1 || branch[0].label !== undefined,
    )
    || new Set(meetingPoints).size !== 1
  ) {
    fail(`The branches from ${name} do not meet`);
  }
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
let fanInResults: Outcome[] | undefined;
let fanInTarget: string | undefined;
let reviewFanIn = false;
let repairContract: RepairFinding[] | undefined;
let repairDispositions: unknown;
let completingTask = false;
let attempts = 0;
function validateFanInOutcome(name: string, outcome: Outcome): RepairFinding[] {
  if (!Array.isArray(outcome.findings)) fail(`The result of ${name} has no findings array`);
  if (!Array.isArray(outcome.advisories)) fail(`The result of ${name} has no advisories array`);
  const satisfied = Boolean(outcome.satisfied);
  if (!satisfied && outcome.findings.length === 0) fail(`The ${name} rejected the work without findings`);
  if (satisfied && outcome.findings.length > 0) fail(`The ${name} accepted the work with findings`);
  for (const finding of outcome.findings) {
    if (
      typeof finding !== 'object'
      || finding === null
      || !['id', 'requirement', 'evidence', 'repair', 'verification'].every(
        field => typeof (finding as Record<string, unknown>)[field] === 'string'
          && Boolean((finding as Record<string, string>)[field].trim()),
      )
    ) fail(`The result of ${name} has an incomplete repair finding`);
  }
  return outcome.findings as RepairFinding[];
}
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
    const testPolicy = hasTestAuthor
      ? ` Do not modify test files.${revisionRoute ? '\nIf the tests are missing or insufficient, leave them unchanged and return "tests_need_revision": true with the reason in "findings"; do not implement around a faulty test.' : ''}`
      : '';
    const feedback = repairContract
      ? `\nThe fan-in review produced this repair contract:\n${JSON.stringify(repairContract)}\nAddress every finding together. In your final JSON, include a "repairs" array with one disposition for every finding id. Each disposition must contain "id", "status", "change", and "verification". Do not add these attempt-local findings to the plan.`
      : findings === undefined ? '' : `\nThe validator reported these findings:\n${JSON.stringify(findings)}\nAddress each finding.`;
    return `Read the seed at ${JSON.stringify(seed)} and the plan at ${JSON.stringify(plan)}.\nImplement the first unfinished task. Do not mark it done.${testPolicy}${tests.length ? `\nThe task's tests are:\n${tests.join('\n')}` : '\nNo applicable tests were created.'}${feedback}\n${answer}`;
  }
  if (name === 'test_author') return `Read the seed at ${JSON.stringify(seed)} and the plan at ${JSON.stringify(plan)}.\nCreate objective tests for the first unfinished task when tests are applicable. If no tests are applicable, say so in your result. Do not implement the task.${findings === undefined ? '' : `\nThe previous machine reported these findings about the tests:\n${JSON.stringify(findings)}\nCorrect the tests and address each finding.`}\n${answer}`;
  if (fanInResults && name === fanInTarget) return reviewFanIn
    ? `Consider only these branch results and decide what happens next:\n${JSON.stringify(fanInResults)}\nConsolidate overlapping blocking findings into one repair contract. Preserve the strongest concrete evidence. Keep only explicit current-task violations, relevant test failures, and regressions in "findings"; put later-task work, speculative improvements, and preference-only refactors in "advisories".\nSet "satisfied" to false exactly when "findings" is non-empty. Each finding must contain "id", "requirement", "evidence", "repair", and "verification".\nFinish with one JSON line containing "satisfied", "findings", and "advisories".`
    : `Consider only these branch results and decide what happens next:\n${JSON.stringify(fanInResults)}\n${answer}`;
  if (name === 'validator') {
    const work = execFileSync('git', ['status', '--porcelain', '--untracked-files=all', '--', '.', ':(exclude).assembly-lines'], { cwd: target, encoding: 'utf8' });
    return `Run the current task's tests first. Confirm they pass, then review the current task's work using ${machineConfig(name).lens ?? ''} as your focus.\nRead the seed at ${JSON.stringify(seed)} and plan at ${JSON.stringify(plan)}.\nThe current task's changed product files are:\n${work}\nDo not change any files.\n${answer}`;
  }
  if (name.startsWith('reviewer_')) {
    const work = execFileSync('git', ['status', '--porcelain', '--untracked-files=all', '--', '.', ':(exclude).assembly-lines'], { cwd: target, encoding: 'utf8' });
    const repairReview = repairContract
      ? `\nThis is a repair review. The previous repair contract was:\n${JSON.stringify(repairContract)}\nThe doer's reported dispositions were:\n${JSON.stringify(repairDispositions ?? [])}\nFor every previous finding id, return a verification with "resolved" or "unresolved" and concrete evidence. Then inspect the repaired work and relevant surrounding code for regressions and newly exposed violations of the current task. New blocking findings are allowed when they identify such a regression or an explicit current-task requirement.`
      : '\nThis is the initial review, so return an empty "verification" array.';
    return `Read the seed at ${JSON.stringify(seed)} and the plan at ${JSON.stringify(plan)}.\nReview only the first unfinished task using ${machineConfig(name).lens ?? ''} as your focus. The lens guides the review but is not an acceptance criterion by itself.\nA blocking finding must identify an explicit requirement of the current task, a relevant test failure, or a regression. Treat later plan tasks, speculative improvements, and preference-only refactors as advisories.\nThe current task's changed product files are:\n${work}${repairReview}\nDo not change any files.\nFinish with one JSON line containing "satisfied", "verification", "findings", and "advisories". Every blocking finding must contain "id", "requirement", "evidence", "repair", and "verification".`;
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

async function executeBranches(names: string[], catalyst: string): Promise<Outcome[]> {
  const children: ReturnType<typeof spawn>[] = [];
  const runs = names.map(name => new Promise<Outcome>((resolveRun, rejectRun) => {
    const harness = machineConfig(name).harness;
    const child = spawn(harness, [prompt(name)], {
      cwd: target,
      env: { ...process.env, FACTORY_RUN_NAME: runName! },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    children.push(child);
    let stdout = '';
    let stderr = '';
    child.stdout?.on('data', chunk => { stdout += chunk.toString(); });
    child.stderr?.on('data', chunk => { stderr += chunk.toString(); });
    child.on('error', error => rejectRun(`Could not run ${name}: machine=${name} harness=${JSON.stringify(harness)} error=${JSON.stringify(error.message)}`));
    child.on('close', () => {
      process.stdout.write(stdout);
      if (stderr) process.stderr.write(stderr);
      const outcome = parseResult(stdout);
      if (!outcome) {
        rejectRun(`Could not read ${name}'s result: machine=${name} harness=${JSON.stringify(harness)} stderr=${JSON.stringify(stderr)} stdout=${JSON.stringify(stdout)}`);
        return;
      }
      if (!quiet) appendLog(`[${name}] Catalyst: ${catalyst}. ${JSON.stringify(outcome)}`);
      resolveRun(outcome);
    });
  }));
  try {
    return await Promise.all(runs);
  } catch (error) {
    for (const child of children) child.kill();
    fail(String(error));
  }
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
async function orchestrate(): Promise<void> {
  let machine = edges.find(e => e.from === 'start')?.to ?? fail('The assembly line has no start');
  let catalyst = 'Seed';
  while (machine !== 'finish') {
    if (machine === 'doer' && ++attempts > maxAttempts) fail('The task hit its limit');
    const testsBefore = machine === 'doer' && hasTestAuthor ? testSnapshot() : undefined;
    const consumingFanIn = fanInResults !== undefined && machine === fanInTarget;
    const outcome = execute(machine, catalyst);
    if (testsBefore && testsChanged(testsBefore)) fail('The doer changed tests');
    if (machine === 'doer' && repairContract) repairDispositions = outcome.repairs ?? [];
    const consolidatedFindings = consumingFanIn && reviewFanIn
      ? validateFanInOutcome(machine, outcome)
      : undefined;
    const outgoing = edges.filter(edge => edge.from === machine);
    let next: string;
    if (outgoing.length > 1 && outgoing.every(edge => !edge.label)) {
      const branches = outgoing.map(edge => edge.to);
      fanInResults = await executeBranches(branches, machine);
      next = edges.find(edge => edge.from === branches[0])!.to;
      fanInTarget = next;
      reviewFanIn = branches.every(branch => branch.startsWith('reviewer_'));
      catalyst = branches.join(', ');
    } else {
      next = route(machine, outcome);
      catalyst = machine;
    }
    if (consumingFanIn && reviewFanIn) {
      repairContract = consolidatedFindings;
      findings = consolidatedFindings;
      repairDispositions = undefined;
    } else if ('findings' in outcome && next !== 'planner') findings = outcome.findings;
    if (next === 'planner' && machine !== 'planner') {
      commitWork(machine); completingTask = true; findings = undefined; repairContract = undefined; repairDispositions = undefined; attempts = 0;
    } else if (machine === 'test_author' && next === 'doer') {
      attempts = 0;
      completingTask = false;
      findings = undefined;
      repairContract = undefined;
      repairDispositions = undefined;
    } else if (machine === 'planner') completingTask = false;
    if (consumingFanIn) { fanInResults = undefined; fanInTarget = undefined; reviewFanIn = false; }
    if (!quiet && machine === 'doer' && attempts > 1) appendLog(`[doer] Reattempt ${attempts}`);
    machine = next;
  }
  if (!quiet) appendLog('[exit] status=successful reason="assembly line finished"');
  console.log('factory stopped');
}

void orchestrate();
