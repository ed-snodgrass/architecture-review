import { execFileSync } from 'node:child_process';
import { outputFields, type Edge } from './assembly-line';

export type RepairFinding = {
  id: string;
  requirement: string;
  evidence: string;
  repair: string;
  verification: string;
  source?: string;
};

export type PromptContext = {
  target: string;
  seed: string;
  plan: string;
  edges: Edge[];
  hasTestAuthor: boolean;
};

export type PromptState = {
  findings?: unknown;
  fanInResults?: Record<string, unknown>[];
  fanInTarget?: string;
  repairContract?: RepairFinding[];
  repairDispositions?: unknown;
  completingTask: boolean;
};

export function buildPrompt(
  name: string,
  context: PromptContext,
  state: PromptState,
  findTestFiles: () => string[],
): string {
  const wanted = outputFields(context.edges, name);
  const answer = wanted.length
    ? `Finish with one JSON line containing ${wanted.map(field => `"${field}"`).join(' and ')}${name === 'validator' || (name === 'doer' && wanted.includes('findings')) ? ' and "findings"' : ''}.`
    : 'Finish with one JSON line describing the work.';
  if (name === 'planner') {
    return state.completingTask
      ? `The plan is at ${JSON.stringify(context.plan)}.
  The current task's validated work has been committed.
  Update that task in the plan and include its text as "completedTask" in the result.
  ${answer}`
      : `The seed is at ${JSON.stringify(context.seed)}.
  The plan belongs at ${JSON.stringify(context.plan)}.
  ${answer}`;
  }
  if (name === 'doer') {
    const tests = findTestFiles();
    const revisionRoute = context.edges.some(edge =>
      edge.from === 'doer'
      && edge.to === 'test_author'
      && edge.label === 'tests_need_revision',
    );
    const testContext = context.hasTestAuthor
      ? `A test author is on the assembly line.${
          revisionRoute
            ? '\nThe result can route on "tests_need_revision".'
            : ''
        }`
      : '';

    const feedback = state.repairContract
      ? `Repair contract:
    ${JSON.stringify(state.repairContract)}
    Repair dispositions use the fields "id", "status", "change", and
    "verification".`
      : state.findings === undefined
        ? ''
        : `Findings:
    ${JSON.stringify(state.findings)}`;
    return `The seed is at ${JSON.stringify(context.seed)} and the plan is at ${JSON.stringify(context.plan)}.
    ${testContext}
    ${tests.length
      ? `The task's tests are:\n${tests.join('\n')}`
      : 'No applicable tests were created.'}
    ${feedback}
    ${answer}`;
  }
  if (name === 'test_author') {
    const previousFindings = state.findings === undefined
      ? ''
      : `Previous findings about the tests:
  ${JSON.stringify(state.findings)}`;

    return `The seed is at ${JSON.stringify(context.seed)}.
  The plan is at ${JSON.stringify(context.plan)}.
  ${previousFindings}
  ${answer}`;
  }
  if (state.fanInResults && name === state.fanInTarget) {
    return `The branch results are:
  ${JSON.stringify(state.fanInResults)}
  ${answer}`;
  }

  if (name === 'validator') {
    const work = changedProductFiles(context.target);
    return `Read the seed at ${JSON.stringify(context.seed)} and plan at ${JSON.stringify(context.plan)}.
  The current task's changed product files are:
  ${work}
  ${answer}`;
  }
  if (name.startsWith('reviewer_')) {
    const work = changedProductFiles(context.target);
    const reviewContext = state.repairContract
      ? `This is a repair review.
  The previous repair contract was:
  ${JSON.stringify(state.repairContract)}
  The doer's reported dispositions were:
  ${JSON.stringify(state.repairDispositions ?? [])}`
      : 'This is an initial review.';

    return `Read the seed at ${JSON.stringify(context.seed)} and the plan at ${JSON.stringify(context.plan)}.
  The current task's changed product files are:
  ${work}
  ${reviewContext}
  ${answer}`;
  }
  return answer;
}

function changedProductFiles(target: string): string {
  return execFileSync(
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
}
