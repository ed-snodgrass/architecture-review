# Test handoff and run logging plan

## Goal

Allow a doer to request revised tests without editing test files, when the
selected assembly line explicitly routes that request to `test_author`.
Improve run logs so they identify machine catalysts, execution timestamps,
doer reattempts, every normal or error exit, and committed work. Give each
work commit a message naming the machine whose result caused the commit.

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
- When validated work is committed, append a commit record to `log.md`
  containing the UTC timestamp, machine name that caused the commit, commit
  hash, and commit message.
- Include the causing machine name in every generated work commit message,
  using the format `Factory work: <machine>`.
- Do not log a commit for an unsuccessful validation, a test-revision
  handoff, or any other path where no commit is created.

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
7. Pass the machine that caused a successful commit into the commit helper;
   create the `Factory work: <machine>` message and capture the resulting
   commit hash.
8. Append a commit record only after the commit succeeds, preserving the
   existing target-path filtering and unrelated-change protections.
9. Preserve test-change detection and ensure failed handoffs do not commit the
   doer's work.
10. Run the focused feature files, the complete BDD suite, and TypeScript
   typecheck.

## Completion criteria

- Existing test-author and orchestration behavior remains valid.
- A compliant doer can request revised tests through an explicit route.
- A doer that edits tests is still rejected; a test-revision handoff does not
  commit its incomplete attempt.
- Test-author feedback includes the doer's `findings`.
- The attempt counter resets after test revision.
- Every run-log line has a UTC ISO 8601 timestamp.
- Machine catalysts are logged as exact node names.
- First doer execution is unnumbered; retries are logged as reattempts.
- Both successful and error exits are logged with reasons and statuses.
- Each successful work commit is logged with its causing machine, hash, and
  message.
- Each generated work commit message identifies its causing machine.
- Failed validation and test-revision handoffs create neither a commit record
  nor a work commit.
