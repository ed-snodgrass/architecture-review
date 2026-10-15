# Iteration 005: report baseline and extension points

This records the first task in the iteration-005 plan: inspect rendering,
models, CLI coverage handling, and existing behavior before changing presentation.
No analyzer, renderer, CLI, tests, or plan completion markers are changed here.

Seed: `iterations/005-prioritize-report-findings.md`.
Plan: `/workspaces/architecture-review/factory/runs/arch-r-005/plan.md`.

## Verified baseline

From the ArchR root, `python3 -m unittest discover` passed **387 tests** on
Python **3.13.5** (20.199 seconds). This is the iterations 001–004 baseline,
not verification of iteration-005 presentation. The project uses standard-library
unittest and has no documented third-party dependencies or typecheck command.

## Pipeline and preservation boundary

`archr/cli.py:main` loads the module, calls `discover_clients`, calls
`trace_usage(max_depth=DEFAULT_MAX_CALL_STEPS)`, obtains `discover_findings`,
and passes the results to `render_report`. The flag is passed only to rendering.
`--show-analysis-limitations` is an analyze-subcommand flag accepted on either
side of the module path; there is no new command, option, or output artifact.

`write_report` atomically replaces a UTF-8/LF Markdown file in the caller's
working directory, cleans temporary files, and preserves the prior report on
failure. Module loading and source-read errors still precede writing. Preserve
artifactId/folder naming, filename sanitization, exit codes, and concise errors.

Source discovery reads only production Java beneath the targeted module's
`src/main/java`, excluding symlinked source trees/files. No compilation,
execution, configuration lookup, or input mutation belongs in this iteration.
Discovery, indexing, resolution, operation/query extraction, interface routing,
and traversal need no changes for the requested presentation work.

## Existing report structure and rendering seams

`archr/report.py:render_report` currently renders title/module, Summary,
per-finding expanded prose, optional JPQL explanation, Analysis coverage,
Architectural connections, and exhaustive Limitations. Evidence and guidance
are interleaved per finding. Feign titles currently use external system names,
not integration-point identities.

- `_destination` couples Feign destination facts to confidence prose; retain
  facts but do not copy confidence paragraphs onto brief cards.
- `_integration_lines` combines declaration, operations, caveats, usage, and
  guidance for non-Feign findings. Split presentation responsibilities rather
  than losing operation facts when removing this combined layout.
- `_usage_lines` repeats general source-only and traversal explanations and
  renders per-step citation paragraphs. Its input already supplies the compact
  method paths needed by iteration 005.
- `_adapter_guidance_lines` currently suggests interfaces and placement. That
  wording must be replaced in the later guidance task: iteration 005 requests
  review conditions and separately hypothetical examples, not adapter shapes.
- `_query_lines`, `_evidence`, `_markdown`, and `_diagram` are reusable. Preserve
  escaping of source-derived names/values and the independent Mermaid escaping.
  Query previews are bounded before rendering/escaping; never recover raw query
  expressions for new examples or citations.
- `_usage_diagram_lines` already builds the required single diagram, including
  shared class edges, possible interface connections, field endpoints, literal
  HTTP destinations, and category-level unknown destinations. Move its output
  without changing assertions, node IDs, edge labels, or ordering. Preserve the
  declaration-only fallback in `render_report` when no traversal is supplied.

## Reusable identities, order, and evidence

### One presentation sequence, three sections

The current deterministic order is Feign first, sorted by
`(source_path, line, interface_name)`, followed by non-Feign findings sorted by
`(declaration.source_path, declaration.line, declaring_type, field_name or '')`.
`render_report` deliberately filters OpenFeign out of its expanded findings to
avoid reporting clients twice. Retain one ordered presentation sequence and
reuse it for cards, guidance, and evidence; do not independently enumerate the
three sections or accidentally include the OpenFeign findings twice.

`IntegrationDeclaration.identity` is `(mechanism, declaring_type, field_name)`.
Repository and Feign interfaces are shared endpoints; client fields are separate
endpoints even when their library types match. A Feign presentation identity can
use `('OpenFeign', qualified_name, None)` with source path/name fallback for
legacy manually supplied clients whose `qualified_name` is empty. Continue
`_client_chains`' source-path-aware matching for such clients.

`_feign_labels` already qualifies colliding simple interface names. Repository
names likewise need qualification on collisions; field titles should keep
owner-plus-field identity. Never use the external destination as the finding ID.
For links, explicit guidance/evidence anchors derived from the same ordered
finding records (for example `guidance-1` and `evidence-1`) would be deterministic
and identical between coverage modes. These are proposed renderer-local targets,
not new model fields or implemented anchors.

### Destination and status are independent dimensions

`FeignClient` retains `name`, `name_expression`, `url`, `url_expression`,
interface identity, declaration location, and declared mapped operations.
`${...}` URLs and unevaluated URL expressions are unresolved values, not absent
values. Missing URL/name facts need explicit unknown fields, without inventing
configuration. `_system_name`'s current missing-name prose is not itself a known
external system.

`IntegrationFinding` retains declaration, operations, destination, and chains.
`DestinationEvidence.certainty` distinguishes UNKNOWN, LITERAL, PATH (host
unknown), and UNRESOLVED. Operation destinations are independent: the finding's
default unknown destination must not overwrite operation-specific literal,
relative-path, or unresolved facts. A repository does not identify a database.

`OperationEvidence.has_supported_caller` excludes query annotations and
WebClient builder-only configuration. `IntegrationFinding.supported_call_evidence`
deduplicates direct operation/chain citations independently of destinations.
Neither current `status_label` nor `usage_certainty` supplies the new three-way
card vocabulary directly: relevant unresolved caller evidence is retained in
traversal diagnostics, not represented as a separate finding status.

`_relevant_diagnostics` is the reuse point for that evidence. It matches resolved
receiver-field/type identity or exact route candidate methods; sharing a caller
method, file, or simple name is insufficient. Preserve that scoping when deriving
Caller unresolved. A supported direct caller remains evidence even if an upstream
interface route is ambiguous; preserve that uncertainty beside its chain rather
than silently dropping the observed direct call. Possible chains must not become
claims of verified wiring or execution.

### Selective evidence and path grouping

- Declaration: Feign `source_path/line` or `finding.declaration_evidence`.
- Feign operations: `Operation.methods/paths/method_name/evidence` retain mapped
  methods and interface prefixes, even without an observed caller.
- Other operations: `OperationEvidence` retains invocation/configuration/query
  kind, citations, HTTP method, destination, query language, and bounded preview.
  Keep builder-only configuration distinct from a request operation.
- Chains: `UsageChain.steps` are nearest-integration first; reverse them for
  upstream-to-integration display. `CallLink` supplies actual caller and target
  method names, not just class names. Synthetic library target method locations
  are not real library source citations.
- Interface connections retain interface, implementation, implementing method,
  reason, and possible certainty. `boundary`, `boundary_reason`, and `cycle_link`
  retain path-specific depth/cycle facts.

Group only equivalent upstream method paths with compatible certainty,
interface resolution, depth, and cycle behavior. Use method declaration identity
(including source location and arity), not display strings alone: overloads and
same-named methods must not merge. Repeated invocation sites may share a displayed
path while every operation remains visible under Operations. Keep any meaningful
path uncertainty rather than deduplicating it away. Empty Operations and Observed
Call Chains headings must remain with scoped absence statements.

## Coverage and limitations

`UsageTraversal.untraced_sites` deduplicates resolver/interface failures by
`Invocation.site_identity`, retains separate same-line sites via offsets, sorts
sites by source position, and deduplicates/sorts reasons. Coverage is module-wide,
not the sum of finding-relevant diagnostics. Destination/query uncertainty,
followed possible interfaces, and depth/cycle boundaries are not coverage gaps.

`_coverage_lines` currently owns a top-level Analysis coverage heading, a brief
count/zero-gap statement, and optional source-ordered details. Later work should
move that content into Limitations, not recompute sites or filter them to findings.
The flag must still change only the appended call-site detail, including when
there are no findings. Explain caller labels, source/runtime boundaries, two-step
limit, supported mechanisms/forms, and configuration boundary once; retain
finding-specific uncertainty in evidence instead of duplicating it globally.

## Tests and migration hazards

The passing suite pins both semantic behavior and old presentation strings.
Later test changes must distinguish intentional report-layout changes from
analysis regressions:

- `test_report.py`, `test_usage_report.py`, `test_outbound_report.py`: current
  titles, confidence prose, per-finding headings, citations, and escaping.
- `test_adapter_guidance.py`, `test_adapter_guidance_boundaries.py`: observed
  caller scoping, conditional wiring, honest no-caller advice, and old placement
  language that iteration 005 intentionally supersedes.
- `test_finding_diagnostic_relevance.py`: receiver/type-based relevance,
  shadowing, unrelated calls, overload and interface ambiguity.
- `test_integration_findings.py`, declaration/operation/query tests, resolution
  and traversal tests: independent evidence dimensions and unchanged analysis.
- `test_usage_diagram.py`, `test_integration_diagram.py`: diagram assertions,
  shared repositories, distinct fields, unknown/literal destination semantics.
- Coverage summary/detail tests, `test_coverage_mode_preservation.py`,
  `test_integration_coverage.py`, and iteration-003 regressions currently split
  at `## Analysis coverage`; migrate those helpers to compare all non-detail
  content after coverage moves inside Limitations, without weakening equality.
- Iteration 001–004 acceptance/verification tests and `test_cli.py` protect
  flag placement, bounded Unicode previews, hash-seed determinism, repeated
  report bytes, input snapshots, and preservation of output on invalid input.

`README.md` still describes the earlier Feign-only slice; it is not an accurate
inventory of iteration-004 mechanisms. Use the seed, models, and regression
suite as the preservation contract. This inspection adds only this document;
all later rendering and test tasks remain untouched.
