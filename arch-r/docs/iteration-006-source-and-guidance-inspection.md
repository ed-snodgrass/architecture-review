# Iteration 006: source and guidance inspection

This implements only the first plan task (inspection). No detection, model,
rendering, test, fixture, or plan completion changes are included.

Seed: `iterations/006-feign-failure-guidance.md`.
Plan: `/workspaces/architecture-review/factory/runs/arch-r-006/plan.md`.

## Retained source and lexical boundaries

- `archr/indexing.py:SourceIndex.sources` retains `(module-relative path, text)`
  pairs. `index_source` and `index_module` populate these without Java execution.
  `discovery.read_java_sources` reads only production Java under `src/main/java`,
  excludes symlinks, and supplies POSIX module-relative paths.
- `discovery.Token` retains absolute `start`/`end` offsets and one-based `line`.
  `tokenize` removes comments and retains each string, character literal, or text
  block as one opaque token. Structural matching must compare whole tokens,
  never search their contents. `_balanced_end` balances braces, brackets, and
  parentheses; it does not itself identify try/catch ownership.
- `Invocation.source_offset` is the absolute receiver-start offset for ordinary
  field calls (including `this.field`); invocation line is likewise the receiver
  line. `site_identity` distinguishes repeated calls even on one line. Legacy
  manually constructed invocations may have no offset; do not guess for those.
- `Method` retains path, declaration-start line, method-name `declaration_line`,
  name, arity, annotations, and invocations. It does **not** retain body offsets
  or tokens. `_members` already knows body opening/closing tokens when building
  it; optional method-body bounds can be retained there in a later task.
- `_invocations` excludes local-type and anonymous-class bodies while preserving
  constructor argument calls. It does not exclude lambda bodies. A later detector
  must independently enforce lambda and try nesting boundaries rather than
  assume every indexed invocation belongs to its surrounding try.

## Type identity limitations

`_extract` parses non-static explicit imports and marks conflicting imports as
ambiguous; wildcard imports are ignored. Compilation-unit sibling names, member
types, and class type parameters shadow imports through `_compilation_unit_types`
and `_scoped_type_imports`. These import maps are **not retained** on `JavaType`
or `Method`. `_resolve` also falls back to the current package, so its result
alone cannot establish the seed's explicit-import requirement.

Later detection must preserve or reconstruct explicit import provenance and
conservative lexical shadows, including method/local declarations. It must not
infer exception identity from a simple name or wildcard import. Source-declared
canonical types can be checked against `SourceIndex.declared_type_names` and
`types`, following the existing library-type exclusions in `integrations.py`.
No existing try/catch observation or exception-resolution model was found.

## Resolved Feign calls and stable identities

`resolution.resolve_index` supplies immutable `CallLink` records containing
caller type/method, typed receiver field, target type/method, and invocation.
Resolution already rejects shadowed receivers, explicit generic invocations,
missing types/methods, and same-arity ambiguity. The detector should consume
these resolved links, restricted to recognized Feign targets, not rescan text
for new calls or broaden resolution.

`trace_usage` has the source index and resolution together before building
backward chains. Its roots include Feign targets identified by `JavaType.feign`.
`UsageChain.steps[0].link` is the actual direct integration call; later steps are
upstream routes. The same root can appear in several chains. Collecting
observations from unique direct links avoids upstream-path duplication.

- Integration identity: `IntegrationDeclaration.identity` is
  `(mechanism, declaring_type, field_name)`; Feign uses
  `('OpenFeign', qualified_interface_name, None)`.
- Caller identity: qualified type plus full method endpoint, including source
  location and arity, not the displayed name alone (`traversal._endpoint`).
- Site identity: invocation path/absolute offset plus catch path/absolute offset
  preserves distinct calls and catches on the same line. Include integration and
  caller identity when associating observations; line-only deduplication loses
  evidence. These are extension recommendations, not added model fields.

## Rendering seams and preservation hazards

`report._adapter_guidance_lines` selects finding-specific chains and deduplicates
review blocks by caller method, certainty, and interface connections. That key
intentionally merges multiple operations in a method; later rendering must
aggregate all matching observations before emitting its failure condition,
not retain only the first chain's operation. Keep possible-interface wiring
qualifications separate from the observed direct call/catch structure.

The HTTP failure condition currently always renders a hypothetical status-503
example. Replace only matching Feign failure guidance; database, other HTTP,
no-match, no-usage, and missing-caller behavior must remain scoped as before.
Two blanket disclaimers need attention in later tasks: the per-caller
“has not established that any of them occurs” and `render_report`'s global
“not observed behavior” introduction.

`_evidence(path, line)` formats escaped `relative/path.java:line` citations;
`_markdown` protects source-derived names as well. Cite the actual invocation
and catch token, not method declaration or target-interface line. Rendering is
pure: `render_report` consumes supplied analysis and must not read source.
The CLI passes `show_analysis_limitations` only to rendering, so observations
should be computed independently of that flag.

Preserve Summary, Architectural Connections, Findings, Adapter Review Guidance,
Findings with Evidence, Limitations order; brief cards, anchors, diagrams,
statuses, coverage site counting, and default/detailed-mode equality outside
appended limitation details. OpenFeign findings are filtered from the expanded
finding list because clients render separately.

## Fixtures and regression baseline

`example-reports/005-arch-r-report-order-service.md` shows the current Feign
`OrderService.resolveItem` guidance alongside repository `placeOrder` guidance.
Its failure example is hypothetical, not evidence of an existing catch. No
checked-in `OrderService.java` or `ProductClient.java` was found. Later fixture
work must supply actual matching source rather than invent citations for this
historical report.

Tests use disposable Java sources. Relevant seams include:

- `test_indexing`, `test_resolution`, `test_resource_scope`, and
  `test_explicit_generic_invocations`: offsets, ownership, shadows, and resolution.
- `test_adapter_guidance*`, `test_iteration_005_guidance`,
  `test_finding_diagnostic_relevance`: caller/finding scoping, conditional
  examples, missing callers, possible wiring, and unrelated diagnostics.
- `test_usage_report` and `test_brief_finding_cards`: reusable source/report
  fixtures. Existing hypothetical-example assertions use no-match sources;
  keep them and add positive catch cases in the later testing task.
- `test_iteration_005_acceptance`, `test_iteration_005_verification`,
  `test_coverage_mode_preservation`, diagram tests, and
  `test_verification_boundaries`: analysis snapshots, modes, deterministic
  rendering, CLI errors, no Java execution, and input immutability.

Inspection baseline from the ArchR root:

- `python3 -m unittest discover`: **418 tests passed** (22.565 seconds).
- `python3 -m compileall -q archr tests`: passed.
- `git diff --check`: passed before adding this document; rerun afterward.

These results verify the existing baseline, not the future detector or guidance.
No test files were modified.
