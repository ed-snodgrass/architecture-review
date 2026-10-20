# Fan-out Proposal Test Repair Plan

## Goal

Make the failing fan-out proposal scenarios pass by completing each reviewer
machine's `AGENTS.md`, not by embedding stable reviewer behavior in the
factory's runtime prompt builder.

Preserve the factory boundary established by the machine specification:

- `AGENTS.md` defines what a machine is for and how it does its job.
- `prompts.ts` supplies facts that change during a run.
- The factory does not read or interpret `plan.md`.

The fan-out orchestration, repair-state transfer, routing, attempt limits, and
synthesiser consistency checks already work and are outside this repair.

## Corrected diagnosis

The proposal failures revealed unrealistic reviewer fixtures. The fake
reviewers had harness and lens metadata but no representative `AGENTS.md`, so
their configured prompts lacked the behavior a real reviewer machine should
own.

The previous approach incorrectly compensated by adding reviewer policy and
lens text to `prompts.ts` and passing `MachineConfig.lens` through `cli.ts`.
That violated the explicit course rule that machine instructions live with the
machine and can change without changing the factory.

The rollback removes:

- reviewer-lens plumbing from `cli.ts`;
- `PromptMachineContext` from `prompts.ts`;
- stable reviewer scope, acceptance policy, result schema, and repair policy
  from runtime prompt construction.

Keep the `@fan-out-convergence` feature tag and the assertion that the selected
lens reaches every reviewer. Those are valid acceptance coverage; the source
of the guidance must change.

## Instruction and runtime boundaries

### Reviewer `AGENTS.md`

Every reviewer machine owns these stable instructions:

- review only the first unfinished task;
- do not change the plan or product files;
- use its named lens to focus review;
- treat the lens as guidance, not an acceptance criterion by itself;
- require a blocking finding to identify an explicit current-task
  requirement, relevant test failure, or regression;
- treat later plan tasks, speculative or optional improvements, and
  preference-only refactors as advisories;
- on an initial review, return an empty `verification` array;
- on a repair review, return a verification for every previous finding ID,
  marking it `resolved` or `unresolved` with concrete evidence;
- inspect repaired work for regressions and newly exposed current-task
  violations;
- return `satisfied`, `verification`, `findings`, and `advisories`;
- give every blocking finding non-empty `id`, `requirement`, `evidence`,
  `repair`, and `verification` fields.

Each reviewer keeps its own lens description. Shared policy may be generated
by a test helper, but production machine files remain independently editable.

### `prompts.ts`

The runtime reviewer prompt supplies only changing execution context:

- seed and plan paths;
- changed product files;
- whether this is an initial or repair review;
- the previous synthesised repair contract;
- the doer's latest repair dispositions;
- fields required dynamically by assembly-line routing, when applicable.

It must not contain a review lens, acceptance threshold, advisory policy, or
stable reviewer result schema.

The phrase "first unfinished task" belongs in `AGENTS.md`. The reviewer reads
the plan and identifies that task; the factory merely provides the plan path.

## Test-fixture changes

### Reviewer instruction helper

Add a test helper that writes a complete reviewer `AGENTS.md` given a target
machine name and lens description. Use it for all three reviewers in fan-out
proposal setup.

The helper should produce the same shared convergence contract while allowing
different lens text per reviewer. It must write into:

```text
<target>/.assembly-lines/.machines/<reviewer>/AGENTS.md
```

Do not place these instructions in environment variables, fake harness code,
or factory source.

### Scenario setup

Make the proposal background install realistic general reviewer instructions
before the factory runs. The `reviewers' lens is single responsibility` step
must update each reviewer's `AGENTS.md` with that lens and retain the shared
policy.

If `machine.json` keeps a `lens` field for metadata, do not rely on that field
as the machine's instruction source. The behavior asserted by the scenario
must be present in `AGENTS.md`.

Retain these feature expectations:

- reviewers receive seed and plan paths from runtime context;
- reviewers receive changed product files from runtime context;
- reviewers receive their lens and stable review policy from `AGENTS.md`;
- repair reviewers receive contract and disposition data from runtime context;
- the combined configured prompt contains both instruction and runtime parts.

### Harness coverage

The deterministic fake harness receives the configured prompt assembled by
the machine runner, so it can assert the combined result. Keep existing course
coverage proving that ACP and supported legacy harnesses use only the
machine-specific instruction file.

Do not add an alternate test-only path for loading `AGENTS.md`.

## Maintained machine files

After the fixture is green, update tracked reviewer machine instructions that
are intended to use convergent fan-out review.

For each maintained reviewer:

1. preserve its existing lens-specific questions and examples;
2. add the shared task boundary and blocking/advisory policy;
3. add initial and repair review behavior;
4. add the structured result contract;
5. do not copy another reviewer's lens text.

At minimum, inspect the three reviewer files under
`arch-r/.assembly-lines/.machines/`. Update Tetris reviewer files only when the
corresponding target exists and is intentionally tracked. Do not reconstruct a
missing target from run logs or editor history.

## Implementation sequence

1. Confirm the misplaced `cli.ts` and `prompts.ts` changes are rolled back.
2. Run the focused fan-out proposal to restore the expected red baseline.
3. Add a reusable test-fixture helper for reviewer `AGENTS.md` content.
4. Install general reviewer instructions in fan-out proposal setup.
5. Make the single-responsibility step update reviewer `AGENTS.md` files.
6. Run the three formerly failing scenarios by name.
7. Run the complete `@fan-out-convergence` feature.
8. Update maintained reviewer `AGENTS.md` files without changing their lenses.
9. Run all proposal features, the standard suite, and TypeScript typecheck.
10. Run real-agent examples only when credentials are intentionally available.

## Verification commands

From `factory/`, run the three failing scenarios together:

```sh
npm test -- --profile proposal --name "Reviewers receive the task's requirements|A review lens is guidance rather than a reason to reject|All reviewers run again after a repair"
```

Run the whole fan-out proposal:

```sh
npm test -- --profile proposal --tags @fan-out-convergence
```

Run all proposal and standard coverage:

```sh
npm test -- --profile proposal
npm test
npm run typecheck
```

When external credentials are intentionally available:

```sh
npm run test:real
```

## Completion criteria

- No reviewer lens or stable review policy is hard-coded in `cli.ts` or
  `prompts.ts`.
- Every reviewer receives its behavior from its own `AGENTS.md`.
- Runtime prompts still provide seed, plan, changed files, attempt type,
  repair contract, and doer dispositions.
- Every configured reviewer lens reaches only the corresponding reviewer.
- Initial and repair result contracts are explicit in reviewer instructions.
- All 17 proposal scenarios pass.
- The standard non-real-agent suite and TypeScript typecheck pass.
- Maintained reviewer instruction files preserve their distinct lenses.
- The factory continues not to read or interpret `plan.md`.

## Out of scope

- Changing synthesiser consolidation or consistency validation
- Changing doer repair dispositions
- Changing fan-out concurrency, routing, attempt limits, or commit timing
- Making `machine.json.lens` a second instruction channel
- Reading or parsing `plan.md` in factory code
- Loosening or deleting the proposal assertions
