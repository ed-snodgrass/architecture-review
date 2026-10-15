# Iteration 005 verification

## Completed checks

- `python3 -m unittest discover`: **418 tests passed** (24.329 seconds).
- `python3 -m compileall -q archr tests`: passed.
- `git diff --check`: passed.

These are the documented Python project checks; there is no ArchR npm or
TypeScript project check. Plan checkboxes and completion flags remain unchanged,
as requested.

## Reconciliation of the failing suite

Reconciled the original 75 failures and 9 errors rather than skipping tests or
restoring superseded presentation. Older tests now select integration-point
cards and their corresponding guidance/evidence using `tests/report_sections.py`.
They expect method-qualified compact paths, three caller statuses, unknown
values, review conditions instead of adapter placement prescriptions, and
coverage nested in Limitations. Coverage counts, order, deduplication, diagnostic
relevance, query bounds, destination uncertainty and diagram assertions remain
checked. The optional-details test's follow-on `assertEqual(*reports)` error and
iteration-004 verification's missing expected-output entry were consequences of
earlier stale assertions; both now complete normally.

Verbose per-step receiver/target citations are intentionally absent in iteration
005. Those old location checks now inspect retained analysis evidence using
`tests/analysis_evidence.py`, while report tests check compact paths, selective
operation/declaration citations and finding-specific uncertainty. Location checks
do not merely check that the input file contains the line. Existing resolution,
interface and traversal tests continue checking endpoint identity, ambiguity,
method matching, two-step boundaries and cycles independently of presentation.
Guidance tests no longer demand a domain-facing interface or adapter location;
they retain conditionality, observed caller identity, uncertainty, relevance,
no-invented-behavior and no-architectural-verdict assertions.

No production regression was identified after reconciling these assertions. No
production analysis, CLI or rendering code needed repair in this verification
change.

## Independent iteration 004 preservation evidence

`tests/iteration_004_preservation.json` was captured by running
`tests/preservation_snapshot.py` against the **old implementation**, commit
`49fc30675c6469b01ef5c32fb93843e2017c656a` (`94faf9a^`), extracted into a temporary
directory with `git archive`. This is the implementation preceding the iteration
005 baseline-inspection commit; its documented suite baseline was 387 passing
tests. It is not a snapshot generated from the current implementation.

The input was the disposable mixed module from
`tests/test_iteration_005_acceptance.py`. To reproduce, instantiate that fixture,
then run the snapshot script in a subprocess with its module path as the sole
argument, the extracted old package directory as `PYTHONPATH`, and a working
directory outside this checkout (so the current package cannot shadow it).
The snapshot script imports only APIs present in both implementations.

The committed SHA-256 fingerprints cover canonical JSON of complete discovered
clients, declarations, finding operations/queries/destinations, method resolution,
interface resolution, and traversal including coverage sites/counts and path
boundaries. A separate fingerprint covers the complete Mermaid content. JSON
uses sorted keys, ASCII escaping and compact separators. Source locations are
relative; no temporary module path participates in these values.

`test_analysis_matches_independently_captured_iteration_004_baseline` compares
each current dimension with this fixed historical evidence. All seven match.
Additionally, `git diff 94faf9a^ HEAD -- archr` shows only `archr/report.py`
changed during iteration 005: discovery, operation/query extraction, destination
classification, resolution, traversal, coverage, module loading and CLI code are
unchanged. The unchanged legacy semantic suites and fixed historical snapshot
provide preservation evidence independent of repeated current runs.

## Execution, CLI, failure and immutability evidence

`tests/test_iteration_005_verification.py` also verifies that both render modes
leave the supplied analysis objects unchanged, repeated rendering is byte-equal,
and coverage details are the only mode difference. Input snapshots check bytes,
permissions and modification times. Missing paths and invalid UTF-8 return exit
code 1 with concise stderr and no traceback/stdout, preserve the previous report,
leave source metadata untouched and create no extra artifacts.

The full passing suite includes existing CLI/invalid-input and atomic-write
checks, source boundary and no-process-launch checks, iteration-004 mixed-module
verification, repeated CLI output across hash seeds, both flag positions,
selective citations, grouped paths and coverage-only mode differences. All tests
analyze disposable Java source; none compiles or executes the analyzed module.
