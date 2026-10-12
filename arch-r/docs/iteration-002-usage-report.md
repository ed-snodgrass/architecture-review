# Iteration 002: finding-level usage and evidence

The implementation and verification notes below describe the previous run.
The subsequent tests-only revision is recorded at the end.

Implemented the first unfinished plan task without marking it complete or editing tests.

- The CLI passes the named default call-step limit to the existing source-only traversal and passes its result to the renderer.
- Each finding gains **How the code uses this connection** and **Evidence and uncertainty** sections. These describe direct calls, intermediaries, possible interface wiring, method-level chains, depth/cycle cutoffs, and per-call-site evidence.
- Method indexing retains the method-name line separately from the declaration-start line (which may identify an annotation), so the report can cite both accurately.
- Destination confidence remains independent of usage certainty. No caller found is explicitly bounded by supported analysis, not an unused-client claim.
- Unresolved connections unrelated to any finding are presented once in **Module-wide unresolved connections**, explicitly not established routes to any Feign client. Finding sections retain diagnostics touching displayed method endpoints, matching implementation candidates, or candidate methods declared by that client. Candidate methods and implementations retain citations; matching is method-level rather than class-name inference.
- Rendering remains deterministic and escapes source text. Adapter guidance and diagram expansion remain later tasks. The CLI's obsolete caller-analysis statement is removed to avoid contradicting the usage sections; declaration-only renderer calls remain supported without triggering filesystem analysis.

## Verification and test findings

`python3 -m unittest discover -s tests -q`: 172 of 173 supplied tests pass.
`git diff --check` passes. Test files were not edited in this run, and no
analyzed Java was compiled, executed, or modified. The validator finding was
recorded as an unchecked subtask in the plan; the current task remains unchecked.
An additional disposable three-client probe confirms that an unrelated
unresolved-type diagnostic appears exactly once outside the findings and that
repeated output is byte-identical.

The supplied working tree includes revised acceptance expectations for caller
inspection and usage-report assertions that distinguish an unused verdict from
an explicit denial. The two assertion defects recorded in the previous run are
therefore no longer present; no production workaround is needed. The supplied
usage-report coverage exercises direct and intermediary calls, unrelated
methods, interface uncertainties, declarations without calls, ambiguous
overloads, depth and cycle cutoffs, retained call-site evidence, independent
destination confidence, and repeatable output.

Tests need revision: `tests/test_usage_report.py:249` requires a missing
implementation diagnostic inside the product-client finding, although its
`Order → Port` invocation has no implementation or supported route to that
client. The diagnostic and its citations are now retained in the module-wide
section instead. That test should check the module-wide section while still
checking the finding's bounded no-caller statement. Durable coverage should
also verify that unrelated diagnostics occur once with multiple clients and
that relevant overload/interface uncertainty remains within the corresponding
finding. Tests were left unchanged; no production workaround was added.

The pre-existing implementation was retained, with typed call-link evidence
rendering and clearer wording identifying the enclosing method of an invocation.
Adapter guidance, expanded diagram nodes, and comprehensive limitation text
remain later plan tasks. The first unfinished task remains unchecked.

## Tests-only revision

Corrected `tests/test_usage_report.py` without modifying production code:

- The missing-interface test now checks its diagnostic, boundary qualification,
  and receiver/interface citations in the module-wide section. The product
  finding must retain its bounded no-supported-caller explanation and must not
  attribute the unrelated `Order`/`Port` call to the client.
- Added durable three-client coverage for unrelated unresolved types, missing
  interface implementations, and ambiguous implementations. Each invocation's
  diagnostic citation appears exactly once in module context, not in findings;
  candidate declarations and interface/receiver evidence remain available.
- Added three-client isolation coverage for product-relevant ambiguous interface
  wiring and billing-relevant overload ambiguity. Their candidates and citations
  stay in the corresponding findings, without depicting unresolved upstream
  routes. An unrelated call in another method of a client-calling class remains
  module context, exercising method-level rather than class-level relevance.
- Both multi-client cases assert byte-identical reports on repeated analysis.
  The existing fixture helper verifies that analyzed module files are unchanged;
  no Java is compiled or executed.

Verification: `python3 -m unittest discover -s tests -q` passes all 175 tests;
`git diff --check` passes. The first unfinished task and its validator subtask
remain unchecked; this revision supplies tests, not task implementation.

## Current implementation verification

The supplied working tree already implements the first unfinished task in
`archr/cli.py`, `archr/indexing.py`, and `archr/report.py`. Retained that
implementation rather than adding a workaround or proceeding to later tasks.
The revised supplied tests resolve the diagnostic-placement assertion defect
and provide durable multi-client diagnostic isolation and deterministic-output
coverage.

`python3 -m unittest discover -s tests -q` passes all 175 tests, and
`git diff --check` passes. No test files or plan checkboxes were changed in this
run. No further test revision is needed for this task.
