# Test handoff and run logging plan

## Goal

Allow a doer to request revised tests without editing test files, when the
selected assembly line explicitly routes that request to `test_author`.
Improve run logs so they identify machine catalysts, execution timestamps,
doer reattempts, and every normal or error exit.

## Scope

- Treat `doer -> test_author [label="tests_need_revision"]` as an explicit
  assembly-line capability; do not add an implicit route.
- Require the doer to leave tests unchanged and return
  `{"tests_need_revision": true, "findings": ...}` when the tests are missing
  or insufficient.
- Pass the doer's `findings` to `test_author`, which revises tests without
  implementing the task.
- Reset the doer-attempt counter after test-author revision.
- Keep immediate rejection when the doer actually changes test files.
- Use exact machine names for machine catalysts, with descriptive labels only
  for non-machine catalysts.
- Append UTC ISO 8601 timestamps to every new run-log line.
- Log each normal completion and error exit with reason and status.
- Log only retries after the first doer execution as `reattempt N`.

## BDD-first implementation

1. Extend `test-author.feature` with the explicit doer-to-test-author handoff,
   findings transfer, no-commit behavior, and attempt-counter reset.
2. Extend `orchestration.feature` with catalyst naming, per-line timestamps,
   reattempt logging, successful exits, and error exits.
3. Add or update step definitions and fakes needed to make those examples
   executable.
4. Update the CLI prompt and result-field handling for `tests_need_revision`
   and `findings`.
5. Route doer feedback to `test_author` only when the assembly line declares
   that labeled edge; reset attempts when that route is taken.
6. Centralize log-line creation so every appended line has a UTC ISO timestamp,
   the exact machine catalyst where applicable, and structured exit details.
7. Preserve test-change detection and ensure failed handoffs do not commit the
   doer's work.
8. Run the focused feature files, the complete BDD suite, and TypeScript
   typecheck.

## Completion criteria

- Existing test-author and orchestration behavior remains valid.
- A compliant doer can request revised tests through an explicit route.
- A doer that edits tests is still rejected and its work is not committed.
- Test-author feedback includes the doer's `findings`.
- The attempt counter resets after test revision.
- Every run-log line has a UTC ISO 8601 timestamp.
- Machine catalysts are logged as exact node names.
- First doer execution is unnumbered; retries are logged as reattempts.
- Both successful and error exits are logged with reasons and statuses.
