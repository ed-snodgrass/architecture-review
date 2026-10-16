import { execFileSync, spawn, spawnSync } from 'node:child_process';
import { appendFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { basename, dirname, resolve } from 'node:path';

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

for (const name of new Set(edges.flatMap(edge => [edge.from, edge.to]))) {
  if (name === 'start' || name === 'finish') continue;

  const directory = resolve(lineDirectory, '.machines', name);
  const hasLogin =
    existsSync(resolve(directory, 'auth.json'))
    || existsSync(resolve(directory, '.credentials.json'));
  const hasApiKey = Boolean(process.env.ANTHROPIC_API_KEY);

  if (!hasLogin && !hasApiKey) {
    fail(`The ${name} cannot sign in`);
  }
}

mkdirSync(runDirectory!, { recursive: true });
if (!saved) writeFileSync(settingsFile!, JSON.stringify({ target, seed, line: lineName }, null, 2) + '\n');
const plan = resolve(runDirectory!, 'plan.md');
const maxAttempts = Number(option('--max-attempts') ?? 3);
mkdirSync(target, { recursive: true });
if (spawnSync('git', ['rev-parse', '--show-toplevel'], { cwd: target }).status !== 0) execFileSync('git', ['init'], { cwd: target });

function machineConfig(name: string): Required<Pick<Config, 'harness'>> & Config {
  const stored = storedConfig(name)!;
  const oldHarness = option(`--${name}-harness`) ?? (name === 'planner' ? option('--harness') : undefined);
  return { ...stored, harness: oldHarness ?? stored.harness ?? 'pi' };
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
  if (name === 'planner') {
    return completingTask
      ? `The plan is at ${JSON.stringify(plan)}.
  The current task's validated work has been committed.
  ${answer}`
      : `The seed is at ${JSON.stringify(seed)}.
  The plan belongs at ${JSON.stringify(plan)}.
  ${answer}`;
  }
  if (name === 'doer') {
    const tests = testFiles();
    const revisionRoute = edges.some(e => e.from === 'doer' && e.to === 'test_author' && e.label === 'tests_need_revision');
    const testContext = hasTestAuthor
      ? `A test author is on the assembly line.${
          revisionRoute
            ? '\nThe result can route on "tests_need_revision".'
            : ''
        }`
      : '';

    const feedback = repairContract
      ? `Repair contract:
    ${JSON.stringify(repairContract)}
    Repair dispositions use the fields "id", "status", "change", and
    "verification".`
      : findings === undefined
        ? ''
        : `Findings:
    ${JSON.stringify(findings)}`;
    return `The seed is at ${JSON.stringify(seed)} and the plan is at ${JSON.stringify(plan)}.
    ${testContext}
    ${tests.length
      ? `The task's tests are:\n${tests.join('\n')}`
      : 'No applicable tests were created.'}
    ${feedback}
    ${answer}`;
  }
  if (name === 'test_author') {
    const previousFindings = findings === undefined
      ? ''
      : `Previous findings about the tests:
  ${JSON.stringify(findings)}`;

    return `The seed is at ${JSON.stringify(seed)}.
  The plan is at ${JSON.stringify(plan)}.
  ${previousFindings}
  ${answer}`;
  }
  if (fanInResults && name === fanInTarget) {
    return `The branch results are:
  ${JSON.stringify(fanInResults)}
  ${answer}`;
  }

  if (name === 'validator') {
    const work = execFileSync(
      'git',
      [
        'status',
        '--porcelain',
        '--untracked-files=all',
        '--',
        '.',
        ':(exclude).assembly-lines',
      ],
      { cwd: target, encoding: 'utf8' },
    );

    return `Read the seed at ${JSON.stringify(seed)} and plan at ${JSON.stringify(plan)}.
  The current task's changed product files are:
  ${work}
  ${answer}`;
  }
  if (name.startsWith('reviewer_')) {
    const work = execFileSync(
      'git',
      [
        'status',
        '--porcelain',
        '--untracked-files=all',
        '--',
        '.',
        ':(exclude).assembly-lines',
      ],
      { cwd: target, encoding: 'utf8' },
    );

    const reviewContext = repairContract
      ? `This is a repair review.
  The previous repair contract was:
  ${JSON.stringify(repairContract)}
  The doer's reported dispositions were:
  ${JSON.stringify(repairDispositions ?? [])}`
      : 'This is an initial review.';

    return `Read the seed at ${JSON.stringify(seed)} and the plan at ${JSON.stringify(plan)}.
  The current task's changed product files are:
  ${work}
  ${reviewContext}
  ${answer}`;
  }
  return answer;
}
function configuredPrompt(name: string): string {
  const instructionsFile = resolve(
    lineDirectory,
    '.machines',
    name,
    'AGENTS.md',
  );
  const instructions = existsSync(instructionsFile)
    ? readFileSync(instructionsFile, 'utf8').trim()
    : '';

  return [instructions, prompt(name)]
    .filter(Boolean)
    .join('\n\n');
}

function harnessArguments(name: string, harness: string): string[] {
  if (basename(harness) === 'codex') {
    return ['exec', '--ephemeral', prompt(name)];
  }
  if (basename(harness) !== 'pi') return [configuredPrompt(name)];

  const machineDirectory = resolve(lineDirectory, '.machines', name);
  const instructionsFile = resolve(machineDirectory, 'AGENTS.md');
  const args = ['-p', '--no-session', '--no-context-files'];
  if (existsSync(instructionsFile)) {
    args.push('--append-system-prompt', instructionsFile);
  }
  args.push(prompt(name));
  return args;
}

function execute(name: string, catalyst: string): Outcome {
  const harness = machineConfig(name).harness;
  const machineDirectory = resolve(lineDirectory, '.machines', name);
  const execution = spawnSync(harness, harnessArguments(name, harness), {
    cwd: target,
    encoding: 'utf8',
    env: {
      ...process.env,
      FACTORY_RUN_NAME: runName!,
      PI_CODING_AGENT_DIR: machineDirectory,
      ...(basename(harness) === 'codex'
        ? { CODEX_HOME: machineDirectory }
        : {}),
    },
  });
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
    const machineDirectory = resolve(lineDirectory, '.machines', name);
    const child = spawn(harness, harnessArguments(name, harness), {
      cwd: target,
      env: {
        ...process.env,
        FACTORY_RUN_NAME: runName!,
        PI_CODING_AGENT_DIR: machineDirectory,
        ...(basename(harness) === 'codex'
          ? { CODEX_HOME: machineDirectory }
          : {}),
      },
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
