import { execFileSync, spawn, spawnSync } from 'node:child_process';
import { appendFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
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

if (args[0] === 'stop' && args[1]) {
  const name = args[1];
  const activeRunFile = resolve(factory, 'active-run.json');
  if (!existsSync(activeRunFile)) fail(`Run ${name} is not running`);

  const active = JSON.parse(readFileSync(activeRunFile, 'utf8')) as {
    name: string;
    pid: number;
  };
  if (active.name !== name) fail(`Run ${name} is not running`);

  appendFileSync(
    resolve(factory, 'runs', name, 'log.md'),
    `${timestamp()} [run] name=${name} status=stopped\n`,
  );

  try {
    process.kill(-active.pid, 'SIGTERM');
  } catch {
    try { process.kill(active.pid, 'SIGTERM'); } catch {}
  }
  rmSync(activeRunFile, { force: true });
  console.log(`stopped run ${name}`);
  process.exit(0);
}

if (args[0] === 'stop') {
  const activeRunFile = resolve(factory, 'active-run.json');
  if (existsSync(activeRunFile)) {
    const active = JSON.parse(readFileSync(activeRunFile, 'utf8')) as {
      name: string;
      pid: number;
    };
    appendFileSync(
      resolve(factory, 'runs', active.name, 'log.md'),
      `${timestamp()} [run] name=${active.name} status=stopped\n`,
    );
    try { process.kill(-active.pid, 'SIGTERM'); } catch {}
    rmSync(activeRunFile, { force: true });
  }

  const factoryPidFile = resolve(factory, 'factory.pid');
  if (existsSync(factoryPidFile)) {
    const pid = Number(readFileSync(factoryPidFile, 'utf8'));
    try { process.kill(pid, 'SIGTERM'); } catch {}
    rmSync(factoryPidFile, { force: true });
  }
  console.log('stopped factory');
  process.exit(0);
}

if (args[0] === 'watch') {
  const name = args[1];
  const record = resolve(factory, 'runs', name, 'log.md');

  if (!existsSync(record)) fail(`No run called ${name}`);

  const entries = readFileSync(record, 'utf8');
  for (const entry of entries.split('\n')) {
    const generated = entry.match(/\[output\] machine=(\S+) text=(.*)$/);

    if (generated) {
      const [, machine, encoded] = generated;
      console.log(`${machine.padEnd(10)} | ${JSON.parse(encoded) as string}`);
    }
  }
  const usage = new Map<string, { input: number; output: number }>();
  for (const match of entries.matchAll(/\[tokens\] machine=(\S+) inputTokens=(\d+) outputTokens=(\d+)/g)) {
    const current = usage.get(match[1]) ?? { input: 0, output: 0 };
    current.input += Number(match[2]);
    current.output += Number(match[3]);
    usage.set(match[1], current);
  }
  for (const [machine, tokens] of usage) {
    console.log(`tokens     ${machine} ${tokens.input} in / ${tokens.output} out`);
  }
  const settings = JSON.parse(
    readFileSync(resolve(factory, 'runs', name, 'run.json'), 'utf8'),
  ) as Settings;

  const providerTotals = new Map<string, number>();

  for (const [machine, tokens] of usage) {
    const configurationFile = resolve(
      settings.target,
      '.assembly-lines',
      '.machines',
      machine,
      'machine.json',
    );

    if (!existsSync(configurationFile)) continue;

    const configuration = JSON.parse(
      readFileSync(configurationFile, 'utf8'),
    ) as { provider?: string };

    if (configuration.provider) {
      providerTotals.set(
        configuration.provider,
        (providerTotals.get(configuration.provider) ?? 0) + tokens.input + tokens.output,
      );
    }
  }

  console.log([
    'totals',
    ...[...providerTotals].map(([provider, total]) => `${provider} ${total}`),
    `run ${[...usage.values()].reduce((total, tokens) => total + tokens.input + tokens.output, 0)}`,
  ].join('   '));

  const running = new Map<string, boolean>();
  for (const match of entries.matchAll(/\[status\] machine=(\S+) running=(true|false)/g)) {
    running.set(match[1], match[2] === 'true');
  }
  for (const [machine, isRunning] of running) {
    if (isRunning) console.log(`running    ${machine}`);
  }
  if (/\[run\].*status=stopped/.test(entries)) console.log(`run ${name} stopped`);

  const activeRunFile = resolve(factory, 'active-run.json');
  const active = existsSync(activeRunFile)
    ? JSON.parse(readFileSync(activeRunFile, 'utf8')) as { name: string }
    : undefined;
  if (args.includes('--once') || active?.name !== name) process.exit(0);

  let previous = entries;
  const interval = setInterval(() => {
    const current = readFileSync(record, 'utf8');
    if (current !== previous) {
      const snapshot = spawnSync(
        'bash',
        [resolve(factory, 'run'), 'watch', name, '--once'],
        { cwd: factory, encoding: 'utf8' },
      );
      process.stdout.write(snapshot.stdout);
      previous = current;
    }
    if (!existsSync(activeRunFile)) {
      clearInterval(interval);
      process.exit(0);
    }
  }, 100);
}

function printHelp(): void {
  console.log(`Factory command

Usage:
  bin/factory --run <name> --target <path> --line <name> --seed <path>
  bin/factory --run <name>
  bin/factory watch <name>
  bin/factory stop <name>
  bin/factory stop

New runs require --run, --target, --line, and --seed. Saved runs can be
resumed with --run alone.

Arguments:
  --run <name>                 Named run to start or resume.
  --target <path>              Target folder; required for a new run.
  --seed <path>                Seed file; required for a new run.
  --line <name>                Target assembly line; required for a new run.
  --harness <command>          Planner ACP agent; default: pi through pi-rpc-acp.
  --<machine>-harness <command> Machine-specific ACP agent override; default: pi
                               through pi-rpc-acp unless configured otherwise.
  --max-attempts <number>      Maximum doer attempts; default: 3.
  --quiet                      Disable run logging; logging is enabled by default.
  --check-assembly-line        Validate an assembly line without running it.
  watch <name>                 Read a run's generated output and token usage.
  stop <name>                  Stop a run while leaving the factory running.
  stop                         Stop the factory and its active run.
  --help                       Show this help and exit successfully.`);
}

if (args.includes('--help')) { printHelp(); process.exit(0); }

const runName = option('--run');
const worker = args.includes('--worker');
const wait = args.includes('--wait');

if (runName && !worker && !wait) {
  const activeRunFile = resolve(factory, 'active-run.json');

  if (existsSync(activeRunFile)) {
    const active = JSON.parse(
      readFileSync(activeRunFile, 'utf8'),
    ) as { name: string; pid: number };

    try {
      process.kill(active.pid, 0);
      fail(`Refused: run ${active.name} is running`);
    } catch (error) {
      if (
        error instanceof Error
        && !('code' in error && error.code === 'ESRCH')
      ) {
        throw error;
      }
    }
  }

  const factoryPidFile = resolve(factory, 'factory.pid');
  let factoryRunning = false;
  if (existsSync(factoryPidFile)) {
    const pid = Number(readFileSync(factoryPidFile, 'utf8'));
    try {
      process.kill(pid, 0);
      factoryRunning = true;
    } catch {}
  }

  if (!factoryRunning) {
    const daemon = spawn(
      process.execPath,
      ['-e', 'setInterval(() => {}, 60_000)'],
      { detached: true, stdio: 'ignore' },
    );
    if (!daemon.pid) fail('Could not start the factory');
    writeFileSync(factoryPidFile, `${daemon.pid}\n`);
    daemon.unref();
  }

  const child = spawn(
    'bash',
    [resolve(factory, 'run'), '--worker', ...args],
    {
      cwd: factory,
      env: process.env,
      detached: true,
      stdio: 'ignore',
    },
  );

  if (!child.pid) fail(`Could not start run ${runName}`);

  writeFileSync(
    activeRunFile,
    JSON.stringify({ name: runName, pid: child.pid }) + '\n',
  );
  child.unref();

  console.log(`started run ${runName}`);
  process.exit(0);
}
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
}).then(() => {
  if (!worker) return;
  const activeRunFile = resolve(factory, 'active-run.json');
  if (!existsSync(activeRunFile)) return;
  const active = JSON.parse(readFileSync(activeRunFile, 'utf8')) as { name: string };
  if (active.name === runName) rmSync(activeRunFile, { force: true });
});
