import { spawn, spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { basename, resolve } from 'node:path';

export type Outcome = Record<string, unknown>;
export type MachineConfig = { harness?: string; lens?: string };

type MachineRunnerOptions = {
  target: string;
  lineDirectory: string;
  runName: string;
  quiet: boolean;
  harnessOverride: (name: string) => string | undefined;
  prompt: (name: string) => string;
  appendLog: (entry: string) => void;
  fail: (message: string) => never;
};

export type MachineRunner = {
  execute: (name: string, catalyst: string) => Outcome;
  executeBranches: (names: string[], catalyst: string) => Promise<Outcome[]>;
};

export function readMachineConfig(
  lineDirectory: string,
  name: string,
): MachineConfig | undefined {
  const file = resolve(lineDirectory, '.machines', name, 'machine.json');
  return existsSync(file)
    ? JSON.parse(readFileSync(file, 'utf8')) as MachineConfig
    : undefined;
}

export function createMachineRunner(options: MachineRunnerOptions): MachineRunner {
  function machineConfig(name: string): Required<Pick<MachineConfig, 'harness'>> & MachineConfig {
    const stored = readMachineConfig(options.lineDirectory, name)!;
    return {
      ...stored,
      harness: options.harnessOverride(name) ?? stored.harness ?? 'pi',
    };
  }

  function configuredPrompt(name: string): string {
    const instructionsFile = resolve(
      options.lineDirectory,
      '.machines',
      name,
      'AGENTS.md',
    );
    const instructions = existsSync(instructionsFile)
      ? readFileSync(instructionsFile, 'utf8').trim()
      : '';

    return [instructions, options.prompt(name)]
      .filter(Boolean)
      .join('\n\n');
  }

  function harnessArguments(name: string, harness: string): string[] {
    if (basename(harness) === 'codex') {
      return ['exec', '--ephemeral', options.prompt(name)];
    }
    if (basename(harness) !== 'pi') return [configuredPrompt(name)];

    const machineDirectory = resolve(options.lineDirectory, '.machines', name);
    const instructionsFile = resolve(machineDirectory, 'AGENTS.md');
    const args = ['-p', '--no-session', '--no-context-files'];
    if (existsSync(instructionsFile)) {
      args.push('--append-system-prompt', instructionsFile);
    }
    args.push(options.prompt(name));
    return args;
  }

  function machineEnvironment(name: string, harness: string): NodeJS.ProcessEnv {
    const machineDirectory = resolve(options.lineDirectory, '.machines', name);
    return {
      ...process.env,
      FACTORY_RUN_NAME: options.runName,
      PI_CODING_AGENT_DIR: machineDirectory,
      ...(basename(harness) === 'codex'
        ? { CODEX_HOME: machineDirectory }
        : {}),
    };
  }

  function execute(name: string, catalyst: string): Outcome {
    const harness = machineConfig(name).harness;
    const execution = spawnSync(harness, harnessArguments(name, harness), {
      cwd: options.target,
      encoding: 'utf8',
      env: machineEnvironment(name, harness),
    });
    if (execution.error) {
      const message = `Could not run the ${name === 'planner' ? 'agent' : name}: machine=${name} harness=${JSON.stringify(harness)} error=${JSON.stringify(execution.error.message)}`;
      options.appendLog(`[agent-error] ${message}`);
      options.fail(message);
    }
    process.stdout.write(execution.stdout);
    if (execution.stderr) process.stderr.write(execution.stderr);
    const outcome = parseResult(execution.stdout)
      ?? options.fail(agentFailure(name, harness, execution));
    if (!options.quiet) {
      options.appendLog(`[${name}] Catalyst: ${catalyst}. ${JSON.stringify(outcome)}`);
    }
    return outcome;
  }

  async function executeBranches(
    names: string[],
    catalyst: string,
  ): Promise<Outcome[]> {
    const children: ReturnType<typeof spawn>[] = [];
    const runs = names.map(name => new Promise<Outcome>((resolveRun, rejectRun) => {
      const harness = machineConfig(name).harness;
      const child = spawn(harness, harnessArguments(name, harness), {
        cwd: options.target,
        env: machineEnvironment(name, harness),
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
        if (!options.quiet) {
          options.appendLog(`[${name}] Catalyst: ${catalyst}. ${JSON.stringify(outcome)}`);
        }
        resolveRun(outcome);
      });
    }));
    try {
      return await Promise.all(runs);
    } catch (error) {
      for (const child of children) child.kill();
      options.fail(String(error));
    }
  }

  return { execute, executeBranches };
}

function parseResult(output: string): Outcome | undefined {
  for (const text of output.trim().split('\n').reverse()) {
    try {
      return JSON.parse(text) as Outcome;
    } catch {}
  }
}

function agentFailure(
  name: string,
  harness: string,
  execution: ReturnType<typeof spawnSync>,
): string {
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
