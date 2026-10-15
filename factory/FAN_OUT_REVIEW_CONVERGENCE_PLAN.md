# Fan-out review convergence plan

## Goal

Keep independent, parallel review on every doer attempt while making rejected
work converge within the existing attempt limit. A rejection must give the
doer one complete, actionable repair contract. A subsequent review must verify
that contract and inspect the repair for regressions, without turning optional
refactoring or work assigned to later plan tasks into new blockers.

The factory continues to make no judgement about whether a technical finding
is correct. It supplies the agents with the task and repair context, requires a
usable result shape, and routes the result declared by the assembly line.

## Proposed feature changes

The proposed additions are recorded in
`proposed-features/fan-out-review-convergence.feature`. They are kept outside
`spec/` until adopted into the course specification.

The examples establish these behaviours:

- Every reviewer receives the seed, plan, first unfinished task, and changed
  product files, so review is bounded by the current task.
- Reviewers are told that their lens guides the review but does not by itself
  make a concern blocking. Later-task work and optional improvements are
  advisory.
- A synthesiser that rejects an attempt must return non-empty `findings`.
- Each synthesised finding is a repair item with a stable identifier,
  requirement, evidence, repair, and verification method.
- The synthesiser consolidates overlapping reviewer reports into the repair
  contract and keeps non-blocking observations as advisories.
- The complete synthesised repair contract reaches the next doer attempt.
- After a repair, all reviewers run again. They receive the previous repair
  contract and the doer's disposition of it.
- Repair review verifies previous finding identifiers and also inspects the
  changed work for regressions or newly exposed violations of the current
  task.
- New blocking findings remain possible, but must identify the current-task
  requirement or regression that makes them blocking.
- Once all old findings are resolved and no new blocking findings exist, the
  synthesiser can accept the task. Advisories alone do not reject it.
- Repair context is cleared when the task is accepted and is not leaked into
  the next task.

## Result contracts

### Reviewer result

Reviewers finish with one JSON object:

```json
{
  "satisfied": false,
  "verification": [
    {
      "id": "TEST-JDBC-001",
      "status": "unresolved",
      "evidence": "tests/test_jdbc_operations.py derives its expectation from production"
    }
  ],
  "findings": [
    {
      "id": "TEST-JDBC-001",
      "requirement": "The supported JDBC operation boundary is regression-tested",
      "evidence": "tests/test_jdbc_operations.py:27-31",
      "repair": "Assert an independently declared set of supported operations",
      "verification": "Run the JDBC tests and the complete suite"
    }
  ],
  "advisories": []
}
```

On the initial review, `verification` is empty. On repair review it contains
one disposition for every previous finding assigned to that reviewer. A new
finding is allowed when the current work violates an explicit requirement or
the repair introduces or exposes a regression.

### Synthesiser result

The synthesiser finishes with one JSON object:

```json
{
  "satisfied": false,
  "findings": [
    {
      "id": "TEST-JDBC-001",
      "source": "reviewer_1",
      "requirement": "The supported JDBC operation boundary is regression-tested",
      "evidence": "tests/test_jdbc_operations.py:27-31",
      "repair": "Assert an independently declared set of supported operations",
      "verification": "Run the JDBC tests and the complete suite"
    }
  ],
  "advisories": []
}
```

`satisfied` is false exactly when `findings` is non-empty. The factory rejects
an internally inconsistent result rather than sending the doer an unexplained
retry. Finding identifiers need only remain stable for the life of the current
task.

### Doer repair disposition

When the doer receives findings, it is asked to return a disposition for each
identifier in addition to any fields required by its outgoing edges:

```json
{
  "repairs": [
    {
      "id": "TEST-JDBC-001",
      "status": "fixed",
      "change": "Used an independent expected operation set",
      "verification": "JDBC tests and complete suite pass"
    }
  ]
}
```

The disposition is review context, not proof that the finding is resolved.
The reviewers decide that on the next pass.

## Prompt changes

### Reviewers

Include the seed and plan paths, identify the first unfinished task as the
review boundary, and retain the changed-product-file list. State that:

- the lens focuses the review but is not an acceptance criterion by itself;
- blocking findings must cite an explicit current-task requirement, a relevant
  test failure, or a regression;
- later plan tasks, speculative improvements, and preference-only refactors
  are advisories;
- reviewers must not change files.

On a repair attempt, also include the previous synthesised findings and the
doer's repair dispositions. Ask reviewers to verify the old identifiers and
then inspect the repair and relevant surrounding code for regressions and
newly exposed current-task violations. Do not prohibit new findings.

### Synthesiser

Continue giving the synthesiser only branch results, preserving the existing
fan-in boundary. On repair passes, those results contain the reviewers'
verification of the previous finding identifiers, so no separate work or
repair context is needed. Ask it to:

- merge duplicates and preserve the strongest concrete evidence;
- keep only current-task violations and regressions in `findings`;
- put later-task and optional observations in `advisories`;
- reject exactly when blocking findings remain;
- always return `satisfied`, `findings`, and `advisories`.

### Doer

Describe synthesised feedback as the current repair contract rather than as a
generic validator report. Ask the doer to address every identifier together
and report one disposition per identifier. Do not ask it to add reviewer
findings to the persistent plan: the repair contract is attempt-local state,
while `plan.md` remains the planner's task list.

## Orchestrator changes

1. Replace the single untyped `findings` value with attempt-local review
   state containing the synthesised findings, advisories, and latest doer
   dispositions.
2. Make reviewer and fan-in result requirements explicit instead of deriving
   only `satisfied` from labeled outgoing edges.
3. Before routing a fan-in rejection, validate that `findings` is a non-empty
   array and each item has the required repair-contract fields.
4. Before routing fan-in acceptance, validate that `findings` is empty.
5. Pass the rejected contract to the doer. Capture the doer's `repairs` result
   and pass both contract and dispositions to every reviewer on the next
   attempt.
6. Run every branch on every attempt. The second and later passes are repair
   reviews: verification of known findings plus regression and
   current-requirement review of the new work.
7. Give the synthesiser only the new branch results. Store its newly
   consolidated contract if it rejects.
8. Clear all repair state after successful routing to the planner, after a
   test-author handoff, and before work on the next task.
9. Preserve parallel branch execution, generic DOT routing, commit behaviour,
   logging, and the configured maximum number of doer attempts.

## BDD-first implementation

1. Adopt the proposed scenarios into the authoritative course feature file.
2. Add step definitions and agent fakes for structured reviewer findings,
   advisories, repair dispositions, verification, regressions, and malformed
   synthesiser results.
3. Make the result contract explicit for reviewers and the fan-in machine.
4. Add task scope and acceptance-threshold guidance to reviewer prompts.
5. Introduce attempt-local repair state and include it in doer, reviewer, and
   synthesiser prompts at the appropriate stages.
6. Validate rejected and accepted synthesiser results before routing.
7. Clear repair state at task and test-author boundaries.
8. Run the focused fan-out feature, the full suite excluding `@real-agent`,
   the real-agent examples, and TypeScript typecheck.

## Completion criteria

- Every doer attempt is reviewed by every configured fan-out branch.
- Repairs are checked against all previous blocking finding identifiers.
- Reviewers can report a regression or newly exposed explicit requirement on
  any repair pass.
- A rejected attempt always gives the doer a non-empty, structured repair
  contract.
- The doer never receives only `satisfied: false` or a synthesiser field the
  orchestrator silently ignores.
- Later-task concerns and optional refactors cannot reject an otherwise
  complete current task.
- Advisories remain visible in logs/results but do not enter the repair loop.
- Accepted work has no unresolved or new blocking findings.
- Repair state cannot leak from one task to another.
- Existing fan-out concurrency, routing, attempt limiting, and committing
  behaviour remains unchanged.
