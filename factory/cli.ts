import { execFileSync, spawnSync } from 'node:child_process';
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import {
  assemblyLineError,
  machineNames,
  parseAssemblyLine,
} from './assembly-line';
import {
  buildPrompt,
  type PromptContext,
} from './prompts';
import {
  createMachineRunner,
  readMachineConfig,
} from './machines';
import { orchestrate } from './orchestrator';

type Settings = { target: string; seed: string; line: string };
type RunContext = PromptContext & {
  lineDirectory: string;
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
const edges = parseAssemblyLine(line);
const hasTestAuthor = edges.some(edge => edge.from === 'test_author' || edge.to === 'test_author');
for (const name of machineNames(edges)) {
  if (!['start', 'finish'].includes(name) && !readMachineConfig(lineDirectory, name)) fail(`The factory has no machine called "${name}"`);
}
const lineError = assemblyLineError(edges);
if (lineError) fail(lineError);
if (checking) { console.log('Assembly line accepted'); process.exit(0); }

for (const name of machineNames(edges)) {
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
const context: RunContext = {
  target,
  seed: seed!,
  plan,
  lineDirectory,
  edges,
  hasTestAuthor,
};
mkdirSync(target, { recursive: true });
if (spawnSync('git', ['rev-parse', '--show-toplevel'], { cwd: target }).status !== 0) execFileSync('git', ['init'], { cwd: target });

void orchestrate({
  context,
  maxAttempts,
  quiet,
  createMachineRunner: (state, findTestFiles) => createMachineRunner({
    target: context.target,
    lineDirectory: context.lineDirectory,
    runName: runName!,
    quiet,
    harnessOverride: name =>
      option(`--${name}-harness`)
      ?? (name === 'planner' ? option('--harness') : undefined),
    prompt: name => buildPrompt(name, context, state, findTestFiles),
    appendLog,
    fail,
  }),
  appendLog,
  fail,
});
