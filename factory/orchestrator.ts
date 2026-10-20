import { execFileSync, spawnSync } from 'node:child_process';
import { readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { selectRoute } from './assembly-line';
import type { MachineRunner, Outcome } from './machines';
import type {
  PromptContext,
  PromptState,
  RepairFinding,
} from './prompts';
import type { TaskCompletionNotifier } from './task-completion-notifier';

type RunState = PromptState & {
  reviewFanIn: boolean;
  attempts: number;
};

type OrchestratorOptions = {
  context: PromptContext;
  maxAttempts: number;
  quiet: boolean;
  createMachineRunner: (
    state: PromptState,
    findTestFiles: () => string[],
  ) => MachineRunner;
  appendLog: (entry: string) => void;
  taskCompletionNotifier: TaskCompletionNotifier;
  runName: string;
  now?: () => Date;
  fail: (message: string) => never;
};

export async function orchestrate(options: OrchestratorOptions): Promise<void> {
  const { context } = options;
  const state: RunState = {
    reviewFanIn: false,
    completingTask: false,
    attempts: 0,
  };
  const machineRunner = options.createMachineRunner(
    state,
    () => testFiles(context.target),
  );

  let machine = context.edges.find(edge => edge.from === 'start')?.to
    ?? options.fail('The assembly line has no start');
  let catalyst = 'Seed';
  while (machine !== 'finish') {
    if (machine === 'doer' && ++state.attempts > options.maxAttempts) {
      options.fail('The task hit its limit');
    }
    const testsBefore = machine === 'doer' && context.hasTestAuthor
      ? testSnapshot(context.target)
      : undefined;
    const consumingFanIn = state.fanInResults !== undefined
      && machine === state.fanInTarget;
    const outcome = await machineRunner.execute(machine, catalyst);
    if (machine === 'planner' && state.completingTask) {
      const completedTask = outcome.completedTask;
      if (typeof completedTask !== 'string' || !completedTask.trim()) {
        options.appendLog(
          '[notification] type=task-complete status=skipped reason="missing completedTask"',
        );
      } else {
        try {
          await options.taskCompletionNotifier.notify({
            completedTask,
            runName: options.runName,
            completedAt: (options.now?.() ?? new Date()).toISOString(),
          });
        } catch {
          options.appendLog(
            '[notification] type=task-complete status=failed reason="internal"',
          );
        }
      }
    }
    if (testsBefore && testsChanged(context.target, testsBefore)) {
      options.fail('The doer changed tests');
    }
    if (machine === 'doer' && state.repairContract) {
      state.repairDispositions = outcome.repairs ?? [];
    }
    const consolidatedFindings = consumingFanIn && state.reviewFanIn
      ? validateFanInOutcome(machine, outcome, options.fail)
      : undefined;
    const outgoing = context.edges.filter(edge => edge.from === machine);
    let next: string;
    if (outgoing.length > 1 && outgoing.every(edge => !edge.label)) {
      const branches = outgoing.map(edge => edge.to);
      state.fanInResults = await machineRunner.executeBranches(branches, machine);
      next = context.edges.find(edge => edge.from === branches[0])!.to;
      state.fanInTarget = next;
      state.reviewFanIn = branches.every(branch => branch.startsWith('reviewer_'));
      catalyst = branches.join(', ');
    } else {
      next = route(context, machine, outcome, options.fail);
      catalyst = machine;
    }
    if (consumingFanIn && state.reviewFanIn) {
      state.repairContract = consolidatedFindings;
      state.findings = consolidatedFindings;
      state.repairDispositions = undefined;
    } else if ('findings' in outcome && next !== 'planner') {
      state.findings = outcome.findings;
    }
    if (next === 'planner' && machine !== 'planner') {
      commitWork(machine, options);
      state.completingTask = true;
      state.findings = undefined;
      state.repairContract = undefined;
      state.repairDispositions = undefined;
      state.attempts = 0;
    } else if (machine === 'test_author' && next === 'doer') {
      state.attempts = 0;
      state.completingTask = false;
      state.findings = undefined;
      state.repairContract = undefined;
      state.repairDispositions = undefined;
    } else if (machine === 'planner') {
      state.completingTask = false;
    }
    if (consumingFanIn) {
      state.fanInResults = undefined;
      state.fanInTarget = undefined;
      state.reviewFanIn = false;
    }
    if (!options.quiet && machine === 'doer' && state.attempts > 1) {
      options.appendLog(`[doer] Reattempt ${state.attempts}`);
    }
    machine = next;
  }
  if (!options.quiet) {
    options.appendLog('[exit] status=successful reason="assembly line finished"');
  }
  console.log('factory stopped');
}

function testFiles(target: string): string[] {
  const files: string[] = [];
  function visit(directory: string): void {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === '.git' || entry.name === '.assembly-lines') continue;
      const path = resolve(directory, entry.name);
      if (entry.isDirectory()) visit(path);
      else if (/(^|[\\/])(test|tests)[\\/]|\.(test|spec)\./i.test(path)) files.push(path);
    }
  }
  visit(target);
  return files;
}

function testSnapshot(target: string): Map<string, string> {
  return new Map(
    testFiles(target).map(file => [file, readFileSync(file, 'utf8')]),
  );
}

function testsChanged(target: string, before: Map<string, string>): boolean {
  const after = testSnapshot(target);
  return before.size !== after.size
    || [...before].some(([file, contents]) => after.get(file) !== contents);
}

function route(
  context: PromptContext,
  name: string,
  result: Outcome,
  fail: (message: string) => never,
): string {
  const selection = selectRoute(context.edges, name, result);
  if ('error' in selection) fail(selection.error);
  return selection.next;
}

function validateFanInOutcome(
  name: string,
  outcome: Outcome,
  fail: (message: string) => never,
): RepairFinding[] {
  if (!Array.isArray(outcome.findings)) {
    fail(`The result of ${name} has no findings array`);
  }
  if (!Array.isArray(outcome.advisories)) {
    fail(`The result of ${name} has no advisories array`);
  }
  const satisfied = Boolean(outcome.satisfied);
  if (!satisfied && outcome.findings.length === 0) {
    fail(`The ${name} rejected the work without findings`);
  }
  if (satisfied && outcome.findings.length > 0) {
    fail(`The ${name} accepted the work with findings`);
  }
  for (const finding of outcome.findings) {
    if (
      typeof finding !== 'object'
      || finding === null
      || !['id', 'requirement', 'evidence', 'repair', 'verification'].every(
        field => typeof (finding as Record<string, unknown>)[field] === 'string'
          && Boolean((finding as Record<string, string>)[field].trim()),
      )
    ) {
      fail(`The result of ${name} has an incomplete repair finding`);
    }
  }
  return outcome.findings as RepairFinding[];
}

function commitWork(
  causingMachine: string,
  options: OrchestratorOptions,
): void {
  const paths = ['.', ':(exclude).assembly-lines'];
  execFileSync('git', ['add', '--', ...paths], { cwd: options.context.target });
  if (
    spawnSync('git', ['diff', '--cached', '--quiet', '--', ...paths], {
      cwd: options.context.target,
    }).status === 1
  ) {
    const message = `Factory work: ${causingMachine}`;
    execFileSync('git', ['commit', '--only', '-m', message, '--', ...paths], {
      cwd: options.context.target,
    });
    const hash = execFileSync('git', ['rev-parse', 'HEAD'], {
      cwd: options.context.target,
      encoding: 'utf8',
    }).trim();
    if (!options.quiet) {
      options.appendLog(`[commit] machine=${causingMachine} hash=${hash} message=${JSON.stringify(message)}`);
    }
  }
}
