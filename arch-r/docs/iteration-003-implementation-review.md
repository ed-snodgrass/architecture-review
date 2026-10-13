# Iteration 003 implementation inspection

Scope: inspection of the first unchecked plan task and its blocking validator
subtask. The working tree already contains production changes addressing the
reported usability failures and revised regression tests. This inspection only
updates this document; tests, production files, and plan checkboxes are left
unchanged.

## Existing pipeline and change locations

- `archr/cli.py:main` loads the module, discovers Feign clients, traces usage
  with `DEFAULT_MAX_CALL_STEPS`, renders, and atomically replaces the report.
  The analyze parser accepts `--show-analysis-limitations` before or after the
  module path and passes it to rendering. The existing error boundary and
  `write_report` replacement/cleanup behavior remain intact.
- `archr/indexing.py:Invocation` retains path, line, receiver, method name,
  argument count, field-receiver status, explicit-generic status, and an optional
  source offset. `_invocations` assigns offsets to ordinary and chained calls,
  distinguishing identical calls on one line without expanding supported forms.
  `discovery.Token.start` already retains the absolute source offset, even when
  method-body token lists are sliced; path plus offset is a stable site key.
  Preserve existing positional construction of `Invocation` when adding identity
  metadata. Review `_step_key` in traversal as well so same-line resolved sites
  keep deterministic ordering without changing traversal depth or call forms.
- `archr/resolution.py:resolve_index` already retains unsupported receivers,
  unsupported explicit generics, unresolved types/methods, and overload
  ambiguity as `Diagnostic` objects. Candidates carry method evidence, but
  diagnostics now also retain unshadowed receiver-field evidence. Finding
  relevance uses this evidence rather than assuming a same-name field is used
  by a local or parameter receiver; existing shadowing rules remain intact.
- `archr/interfaces.py:resolve_interface_index` separately records unsupported,
  missing, and ambiguous implementation connections. Successful interface
  connections are possible links, not untraced sites. Failed interface routes
  have invocation evidence that optional module context must preserve.
  Coverage needs an explicit classification of these failed interface routes,
  not just `UsageTraversal.diagnostics`: the usage-report tests require optional
  details for missing and ambiguous implementations. Successful possible links
  must remain excluded; destination uncertainty is independent of either
  diagnostic collection.
- `archr/traversal.py:UsageTraversal` carries resolver and interface diagnostics
  module-wide, independent of client chains. Depth/cycle cutoffs are chain
  boundaries, not invocation-resolution diagnostics. Coverage aggregation must
  not count these boundaries or followed possible interface connections.
- `archr/report.py:_relevant_diagnostics` uses receiver-field and candidate
  method evidence rather than caller-method proximity. Relevant overload and
  interface ambiguity remain beside findings; unrelated receivers are excluded.
- `archr/report.py:_coverage_lines` aggregates retained resolver and failed
  interface diagnostics by source path and offset, deduplicates reasons, and
  sorts details by source location. `render_report` includes brief coverage even
  without clients; optional details identify same-line calls and explain reasons
  outside findings and the diagram. Zero gaps receive the seed's exact wording.
- `_adapter_guidance_lines` and `_usage_diagram_lines` derive output from
  supported chains, not raw diagnostics. Preserve their inputs and behavior;
  unrelated gaps must not become routes or adapter placement advice.
- The final limitations note in `render_report` should remain accurate about
  supported forms, source boundaries, runtime uncertainty, and applied depth,
  while describing the new summary/detail presentation concisely.

## Preservation checks and available regression tests

`tests/test_untraced_call_coverage.py` covers seven unrelated gaps, diagnostic
retention, both flag positions, same-line site identity, deterministic ordering,
multiple reasons and shared finding context, relevant field evidence, zero gaps,
no findings, possible links, destination uncertainty, depth/cycle boundaries,
mode replacement, immutability, invalid input, and atomic output failure.

The updated `tests/test_usage_report.py` checks optional module-wide context,
scoped overload/interface uncertainty across multiple clients, and identical
finding sections between modes. `tests/test_analysis_limitations.py` preserves
supported forms, runtime caveats, supplied traversal depth, and stable output.

Existing discovery/operations/report/acceptance tests protect Feign declarations,
destinations, source evidence, escaping, and grouping. Indexing/resolution,
explicit-generic, generic-arity, resource-scope, interface, and traversal tests
protect call-form boundaries and method identity. Adapter and diagram tests
protect placement guidance and supported routes. CLI/verification/acceptance
tests protect source exclusion, symlink boundaries, read-only behavior, report
naming, replacement, and concise failures.

The iteration-003 contracts exercise the reported usability changes. Verification
also exposed an older default-report contract that conflicts with this seed;
see the implementation follow-up below. No tests were changed and no production
workaround was added for that conflicting contract.

## Baseline run

Command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`

Result: 231 tests run; 19 failure records (including subtests), no errors.
Failures are confined to `test_analysis_limitations`,
`test_untraced_call_coverage`, and `test_usage_report`, reflecting missing
coverage summaries, the unrecognized detail flag, same-line identity collapse,
and current diagnostic presentation/relevance. Full run output was captured
outside the repository at `/tmp/arch-r-003-inspection-tests.log`.

## Implementation follow-up

Recorded the blocking validator finding under the current plan task without
checking it off. Addressed its three reported usability issues:

- `Invocation.source_offset` retains stable lexer offsets, distinguishing
  identical same-line sites; traversal ordering includes that identity.
- Resolver diagnostics retain unshadowed receiver-field evidence. Finding
  relevance now uses this evidence or candidate/target methods, not caller
  proximity. Unrelated diagnostics no longer appear beside Feign findings.
- Reports aggregate resolver and failed-interface diagnostics module-wide by
  site, deduplicate reasons, and show a brief default summary. Optional details
  identify each call with relative path, line, source offset and readable
  reasons. Followed possible links, destinations and traversal cutoffs are
  excluded from the count.
- The CLI accepts `--show-analysis-limitations` on either side of the path and
  passes it to rendering; the existing atomic report replacement is unchanged.

Verification: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover` ran 231
tests with one failure (no errors). Output:
`/tmp/arch-r-003-implementation-tests.log`.
The focused coverage, usage-report and limitations suites passed all 34 tests;
`git diff --check` passed.

The remaining failure is
`tests/test_iteration_002_acceptance.py::test_missing_implementation_and_declarations_are_not_usage`.
It requires unrelated missing-interface details and `Order`/`Port` citations in
the default report. With no implementation or receiver evidence connecting this
interface to Feign, iteration 003 requires these gaps to be summary-only by
default. Restoring those citations would violate the seed. This test needs
revision to request detailed mode for gap-specific assertions while retaining
its default finding/diagram checks. It is left unchanged; the conflict is also
recorded as a current-task subtask.

## Current verification

The baseline and implementation follow-up above describe earlier runs, not the
current checkout. On this inspection, `python3 -m unittest discover` ran all 231
tests successfully (no failures or errors), and `git diff --check` passed.

The pre-existing revision of
`test_missing_implementation_and_declarations_are_not_usage` now checks summary-
only default output, requests detailed mode for the unrelated interface gap,
and preserves finding/diagram equality and reversible report replacement.
Consequently the historical test conflict no longer blocks this checkout; no
production workaround is needed. The available tests cover the first task's
reported blockers and preservation checks; no test revision is requested.

Pre-existing working-tree test and production changes were left untouched.
The plan remains unchecked and incomplete, as requested.
