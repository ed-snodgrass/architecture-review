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

while(true) {
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

  let outcome;
  for (const line of result.stdout.trim().split('\n').reverse()) {
    try {
      outcome = JSON.parse(line);
      break;
    } catch {
      // Keep looking for the last JSON line.
    }
  }

  if (typeof outcome?.complete !== 'boolean') {
    console.error("Could not read the agent's result");
    process.exitCode = 1;
    break;
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

  if (!args.includes('--all') || outcome.complete) {
    console.log('factory stopped');
    break;
  }
}
