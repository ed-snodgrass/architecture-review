import { spawn, spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { basename, resolve } from 'node:path';
import { Readable, Writable } from 'node:stream';
import * as acp from '@agentclientprotocol/sdk';

export type Outcome = Record<string, unknown>;
export type MachineConfig = {
  harness?: string;
  lens?: string;
  provider?: string;
  protocol?: 'acp' | 'legacy';
};

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
  execute: (name: string, catalyst: string) => Promise<Outcome>;
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
      harness: options.harnessOverride(name)
        ?? stored.harness
        ?? (stored.protocol === 'legacy' ? 'pi' : 'pi-rpc-acp'),
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

  function acpArguments(name: string, harness: string): string[] {
    if (basename(harness) !== 'pi-rpc-acp') return [];
    const machineDirectory = resolve(options.lineDirectory, '.machines', name);
    const instructionsFile = resolve(machineDirectory, 'AGENTS.md');
    const args = ['--no-context-files'];
    if (existsSync(instructionsFile)) {
      args.push('--append-system-prompt', instructionsFile);
    }
    return args;
  }

  function machineEnvironment(name: string, harness: string): NodeJS.ProcessEnv {
    const machineDirectory = resolve(options.lineDirectory, '.machines', name);
    return {
      ...process.env,
      FACTORY_RUN_NAME: options.runName,
      PI_CODING_AGENT_DIR: machineDirectory,
      ...(basename(harness) === 'codex' || basename(harness) === 'codex-acp'
        ? { CODEX_HOME: machineDirectory }
        : {}),
      ...(basename(harness) === 'claude-agent-acp'
        ? { CLAUDE_CONFIG_DIR: machineDirectory }
        : {}),
    };
  }

  async function executeAcp(name: string, catalyst: string): Promise<Outcome> {
    const config = machineConfig(name);
    const harness = config.harness;
    const child = spawn(harness, acpArguments(name, harness), {
      cwd: options.target,
      env: machineEnvironment(name, harness),
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stderr = '';
    child.stderr?.on('data', chunk => { stderr += chunk.toString(); });
    if (!options.quiet) options.appendLog(`[status] machine=${name} running=true`);

    try {
      const stream = acp.ndJsonStream(
        Writable.toWeb(child.stdin!) as WritableStream<Uint8Array>,
        Readable.toWeb(child.stdout!) as ReadableStream<Uint8Array>,
      );
      const turn = await acp.client({ name: 'factory' })
        .onRequest(acp.methods.client.session.requestPermission, ctx => ({
          outcome: {
            outcome: 'selected' as const,
            optionId: ctx.params.options.find(option => option.kind.startsWith('allow'))?.optionId
              ?? ctx.params.options[0].optionId,
          },
        }))
        .connectWith(stream, async ctx => {
          await ctx.request(acp.methods.agent.initialize, {
            protocolVersion: acp.PROTOCOL_VERSION,
            clientCapabilities: {},
          });
          const claude = basename(harness) === 'claude-agent-acp';
          return ctx.buildSession({
            cwd: options.target,
            mcpServers: [],
            ...(claude ? {
              _meta: { claudeCode: { options: { settingSources: ['user'] } } },
            } : {}),
          }).withSession(async session => {
            let output = '';
            void session.prompt(configuredPrompt(name));
            for (;;) {
              const message = await session.nextUpdate();
              if (message.kind === 'stop') {
                return { output, response: message.response };
              }
              const update = message.update;
              if (
                update.sessionUpdate === 'agent_message_chunk'
                && update.content.type === 'text'
              ) {
                output += update.content.text;
                process.stdout.write(update.content.text);
                if (!options.quiet) {
                  options.appendLog(`[output] machine=${name} text=${JSON.stringify(update.content.text)}`);
                }
              }
            }
          });
        });
      const outcome = parseResult(turn.output)
        ?? options.fail(`Could not read ${name}'s result: machine=${name} harness=${JSON.stringify(harness)} stderr=${JSON.stringify(stderr)} stdout=${JSON.stringify(turn.output)}`);
      if (!options.quiet) {
        options.appendLog(`[${name}] Catalyst: ${catalyst}. ${JSON.stringify(outcome)}`);
        options.appendLog(`[tokens] machine=${name} inputTokens=${turn.response.usage?.inputTokens ?? 0} outputTokens=${turn.response.usage?.outputTokens ?? 0}`);
        options.appendLog(`[status] machine=${name} running=false`);
      }
      return outcome;
    } catch (error) {
      options.fail(`Could not run ${name}: machine=${name} harness=${JSON.stringify(harness)} error=${JSON.stringify(String(error))} stderr=${JSON.stringify(stderr)}`);
    } finally {
      child.kill();
    }
  }

  function execute(name: string, catalyst: string): Promise<Outcome> {
    if (machineConfig(name).protocol !== 'legacy') {
      return executeAcp(name, catalyst);
    }
    const harness = machineConfig(name).harness;
    return new Promise<Outcome>((resolveRun, rejectRun) => {
      const child = spawn(harness, harnessArguments(name, harness), {
        cwd: options.target,
        env: machineEnvironment(name, harness),
        stdio: ['ignore', 'pipe', 'pipe'],
      });
      let stdout = '';
      let stderr = '';
      let pending = '';
      if (!options.quiet) options.appendLog(`[status] machine=${name} running=true`);
      child.stdout?.on('data', chunk => {
        const text = chunk.toString();
        stdout += text;
        pending += text;
        const lines = pending.split('\n');
        pending = lines.pop() ?? '';
        if (!options.quiet) {
          for (const line of lines) {
            options.appendLog(`[output] machine=${name} text=${JSON.stringify(line)}`);
          }
        }
      });
      child.stderr?.on('data', chunk => { stderr += chunk.toString(); });
      child.on('error', error => rejectRun(`Could not run the ${name === 'planner' ? 'agent' : name}: machine=${name} harness=${JSON.stringify(harness)} error=${JSON.stringify(error.message)}`));
      child.on('close', () => {
        if (pending && !options.quiet) {
          options.appendLog(`[output] machine=${name} text=${JSON.stringify(pending)}`);
        }
        process.stdout.write(stdout);
        if (stderr) process.stderr.write(stderr);
        const outcome = parseResult(stdout);
        if (!outcome) {
          rejectRun(`Could not read the ${name === 'planner' ? "agent's" : `${name}'s`} result: machine=${name} harness=${JSON.stringify(harness)} stderr=${JSON.stringify(stderr)} stdout=${JSON.stringify(stdout)}`);
          return;
        }
        if (!options.quiet) {
          options.appendLog(`[${name}] Catalyst: ${catalyst}. ${JSON.stringify(outcome)}`);
          options.appendLog(`[tokens] machine=${name} inputTokens=${configuredPrompt(name).length} outputTokens=${stdout.length}`);
          options.appendLog(`[status] machine=${name} running=false`);
        }
        resolveRun(outcome);
      });
    }).catch(error => options.fail(String(error)));
  }

  async function executeBranches(
    names: string[],
    catalyst: string,
  ): Promise<Outcome[]> {
    if (names.every(name => machineConfig(name).protocol !== 'legacy')) {
      return Promise.all(names.map(name => executeAcp(name, catalyst)));
    }
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
      let pending = '';
      if (!options.quiet) options.appendLog(`[status] machine=${name} running=true`);
      child.stdout?.on('data', chunk => {
        const text = chunk.toString();
        stdout += text;
        pending += text;
        const lines = pending.split('\n');
        pending = lines.pop() ?? '';
        if (!options.quiet) {
          for (const line of lines) options.appendLog(`[output] machine=${name} text=${JSON.stringify(line)}`);
        }
      });
      child.stderr?.on('data', chunk => { stderr += chunk.toString(); });
      child.on('error', error => rejectRun(`Could not run ${name}: machine=${name} harness=${JSON.stringify(harness)} error=${JSON.stringify(error.message)}`));
      child.on('close', () => {
        if (pending && !options.quiet) options.appendLog(`[output] machine=${name} text=${JSON.stringify(pending)}`);
        process.stdout.write(stdout);
        if (stderr) process.stderr.write(stderr);
        const outcome = parseResult(stdout);
        if (!outcome) {
          rejectRun(`Could not read ${name}'s result: machine=${name} harness=${JSON.stringify(harness)} stderr=${JSON.stringify(stderr)} stdout=${JSON.stringify(stdout)}`);
          return;
        }
        if (!options.quiet) {
          options.appendLog(`[${name}] Catalyst: ${catalyst}. ${JSON.stringify(outcome)}`);
          options.appendLog(`[tokens] machine=${name} inputTokens=${configuredPrompt(name).length} outputTokens=${stdout.length}`);
          options.appendLog(`[status] machine=${name} running=false`);
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
