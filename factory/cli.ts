import { existsSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { execFileSync, spawnSync } from "node:child_process";

const args = process.argv.slice(2);
if (!args.includes('--target')) {
  console.error('A target is required');
  process.exit(1);
}
const target = args[args.indexOf('--target') + 1];
const harness = args.includes('--harness')
  ? args[args.indexOf('--harness') + 1]
  : 'pi';

const doerHarness = args.includes('--doer-harness')
  ? args[args.indexOf('--doer-harness') + 1]
  : harness;

const validatorHarness = args.includes('--validator-harness')
  ? args[args.indexOf('--validator-harness') + 1]
  : harness;

const validatorLens = args.includes('--validator-lens')
  ? args[args.indexOf('--validator-lens') + 1]
  : 'single responsibility';

const maxAttempts = args.includes('--max-attempts')
  ? Number(args[args.indexOf('--max-attempts') + 1])
  : 3;

if (!args.includes('--seed')) {
    console.error('No seed');
    process.exit(1);
}

const seed = resolve(args[args.indexOf('--seed') + 1]);
if (!existsSync(seed)) {
  console.error('No seed');
  process.exit(1);
}

mkdirSync(target, {recursive: true });

const repository = spawnSync('git', ['rev-parse', '--show-toplevel'], {
  cwd: target,
  encoding: 'utf8',
});

if (repository.status !== 0) {
  execFileSync('git', ['init'], { cwd: target });
}

const plan = resolve(target, '.factory', 'plan.md');
const prompt = `Read the seed at ${JSON.stringify(seed)}
If no plan exists at ${JSON.stringify(plan)}, write one there.
Otherwise, do the first unfinished task and mark it done in the plan.
Finish with a single line of JSON containing "complete": true when no
unfinished taks remain, or "complete": false otherwise.
If you performed a task, include its name in the "task" field.`;

function readResult(output: string) {
  for (const line of output.trim().split('\n').reverse()) {
    try {
      return JSON.parse(line);
    } catch {
      // Keep looking for the last JSON line.
    }
  }
}

while(true) {
  const hadPlan = existsSync(plan);
  const result = spawnSync(harness, [prompt], {
    cwd: target,
    encoding: 'utf8',
  });

  if (result.error) {
    console.error('Could not run the agent');
    process.exitCode = 1;
    break;
  }
  process.stdout.write(result.stdout);

  const outcome = readResult(result.stdout);

  if (typeof outcome?.complete !== 'boolean') {
    console.error("Could not read the agent's result");
    process.exitCode = 1;
    break;
  }

  if (hadPlan && !outcome.complete) {
    let doerPrompt = `Read the seed at ${JSON.stringify(seed)}
and the plan at ${JSON.stringify(plan)}.
Implement the first unfinished task. Do not mark it done.
Finish with a single line of JSON describing the task you performed.`;

    let satisfied = false;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const doerResult = spawnSync(doerHarness, [doerPrompt], {
        cwd: target,
        encoding: 'utf8',
      });

      if (doerResult.error) {
        console.error('Could not run the doer');
        process.exit(1);
      }

      const work = execFileSync('git', [
        'status',
        '--porcelain',
        '--untracked-files=all',
        '--',
        '.',
        ':(exclude).factory',
      ], {
        cwd: target,
        encoding: 'utf8',
      });

      const validatorPrompt = `Review the current task's work using
${validatorLens} as your focus.
Read the seed at ${JSON.stringify(seed)} and plan at ${JSON.stringify(plan)}.
The current task's changed product files are:
${work}
Do not change any files.
Finish with one JSON line containing "satisfied" (boolean)
and "findings" (an array of problems).`;

      const validation = spawnSync(validatorHarness, [validatorPrompt], {
        cwd: target,
        encoding: 'utf8',
      });

      if (validation.error) {
        console.error('Could not run the validator');
        process.exit(1);
      }

      const verdict = readResult(validation.stdout);
      if (typeof verdict?.satisfied !== 'boolean') {
        console.error("Could not read the validator's result");
        process.exit(1);
      }

      if (verdict.satisfied) {
        satisfied = true;
        break;
      }
      doerPrompt = `Read the seed at ${JSON.stringify(seed)}
and the plan at ${JSON.stringify(plan)}.
The validator reported these findings:
${JSON.stringify(verdict.findings)}
Record each finding as a subtask of the current task, address it,
and leave the task itself unfinished.
Finish with a single line of JSON describing the task you performed.`;
    }

    if (!satisfied) {
      console.error('The pass hit its limit');
      process.exit(1);
    }
  }

  execFileSync('git', ['add', '--', '.'], { cwd: target });
  const changes = spawnSync(
    'git',
    ['diff', '--cached', '--quiet', '--', '.'],
    { cwd: target },
  );

  if (changes.status === 1) {
    execFileSync('git', [
      'commit', '--only', '-m', 'Factory pass', '--', '.',
    ], { cwd: target });
  }

  if (hadPlan && !outcome.complete) {
    const plannerUpdate = spawnSync(harness, [
    `Read the plan at ${JSON.stringify(plan)}.
The current task's validated work has been committed.
Mark the current task done.
Finish with one JSON line containing "complete".`,
    ], {
      cwd: target,
      encoding: 'utf8',
    });

    if (plannerUpdate.error) {
      console.error('Could not run the planner');
      process.exit(1);
    }

    const updatedOutcome = readResult(plannerUpdate.stdout);
    if (typeof updatedOutcome?.complete !== 'boolean') {
      console.error("Could not read the planner's result");
      process.exit(1);
    }

    execFileSync('git', ['add', '--', '.factory/plan.md'], { cwd: target });
    execFileSync('git', [
      'commit', '--only', '-m', 'Update plan', '--', '.factory/plan.md',
    ], { cwd: target });
  }

  if (!args.includes('--all') || outcome.complete) {
    console.log('factory stopped');
    break;
  }
}
