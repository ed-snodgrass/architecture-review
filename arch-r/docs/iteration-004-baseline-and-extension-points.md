# Iteration 004: baseline and extension points

This records the first task in the iteration-004 plan: inspect the existing
implementation and tests before extending it. It does not implement the later
mechanism tasks or change the plan's completion state.

## Verified baseline

From the ArchR repository root, `python3 -m unittest discover` passed all **255
tests** on Python **3.13.5** (14.112 seconds). The `python` command is unavailable
in this environment; use `python3`. No third-party dependencies or configured
Python type-check command are documented in `README.md`.

The seed is `iterations/004-database-and-http-declarations.md`; the plan is
`/workspaces/architecture-review/factory/runs/arch-r-004/plan.md`.

## Current pipeline and preservation contracts

- `archr/cli.py:main` validates the module, calls `discover_clients`, calls
  `trace_usage` with `DEFAULT_MAX_CALL_STEPS`, renders, then atomically writes.
  `--show-analysis-limitations` is an analyze-subcommand flag accepted before
  or after the module path. There is no CLI depth option.
- `archr/module.py:load_module` resolves paths from the caller's working
  directory and requires readable/searchable module and `src/main/java`
  directories. `_project_name` uses only the project's direct `artifactId`
  (with or without the Maven namespace), otherwise the directory name.
  `Module.report_filename` replaces runs outside ASCII letters, digits,
  `.`, `_`, and `-` with `-`.
- Reports go to the caller's working directory as
  `arch-r-report-<sanitized-module-name>.md`. `write_report` uses a temporary
  UTF-8 file with LF newlines and `os.replace`; input failures happen before
  writing, and output failures preserve the prior report and clean temporary
  files. `AnalysisError` produces a concise stderr message and exit status 1;
  argparse handles usage errors separately.
- `archr/discovery.py:read_java_sources` is the shared read-only source boundary:
  recursively sorted `.java` files under `src/main/java`, no symlink files or
  directories. Read/encoding/permission errors fail analysis. No configuration,
  tests, external modules, compilation, or execution is consulted.
- Discovery and indexing currently read sources independently. Tracing indexes
  once, but interface resolution runs ordinary call resolution again. An
  expanded pipeline must share consistent endpoint identities between these
  passes, rather than recognizing operations only in report rendering.

## Analyzer extension points

### Declarations and literal evidence

`archr/discovery.py` defines `FeignClient`, `Operation`, `Mapping`, and a
comment-aware lexer with source offsets and line numbers. `extract_clients`
recognizes imported (including wildcard-imported) or fully qualified Spring
Feign annotations, rejecting conflicting explicit imports. It reports one
finding per annotated interface, even without callers. Operation extraction
handles directly declared Spring mappings and interface prefixes; it does not
resolve inherited operations. Name/URL expressions and placeholders remain
unresolved.

`tokenize` already keeps Java text blocks as single tokens, but `_literal`
**explicitly rejects text blocks**. `_attributes` and `_annotation` provide
useful bounded annotation parsing for future JPA query extraction. Query
literal handling needs its own normalization/truncation boundary before any
report or diagnostic receives visible query text; do not simply expose raw
annotation expressions in detailed coverage.

`archr/indexing.py` supplies `SourceIndex`, `JavaType`, `Field`, `Method`, and
`Invocation`. `_resolve` uses explicit imports, package declarations, and fully
qualified names (not wildcard imports). `_fields` already inventories ordinary
explicitly typed fields, including constructor-injected fields and multiple
field declarators; generic and array fields are excluded. Constructor
parameters and locals are not fields. `_extract` records direct `implements`,
but **does not record interface `extends`**. Direct parameterized
`JpaRepository<Entity, ID>` recognition therefore needs header metadata or a
bounded declaration extractor; ordinary generic resolution must remain out of
scope. Match canonical Spring names, not simple-name spellings.

New declaration identities must distinguish repository/Feign interfaces from
client fields: a repository is shared across receiver fields, whereas a client
field is identified by declaring type plus field name. Existing
`qualified_name` and field evidence are reusable, but a library type name alone
cannot identify multiple RestTemplate/JdbcTemplate/WebClient fields.

### Operation resolution and method continuity

`archr/resolution.py:resolve_index` accepts only unshadowed typed-field calls,
including `this.field`. It requires a unique local source type and a unique
method matching name and argument count. `CallLink` retains caller method,
receiver field, target method, and invocation evidence. Same-arity overloads
remain ambiguous; missing/inherited methods and explicit generic syntax are
not guessed.

Library operations need a narrow endpoint-resolution exception before the
local-source requirement, not a relaxation for all external or inherited
methods. Preserve declaration evidence separately from operation-call evidence;
a synthetic library endpoint must not be cited as a real library method
source declaration. Repository declared methods can retain real local method
evidence. Unsupported operations must not seed integration usage chains.

`Invocation` currently records receiver, name, arity, line, offset, shadowing,
and explicit type arguments, but **not argument tokens or expression extent**.
Literal SQL/URL, HttpMethod constants, and fluent request extraction need that
additional bounded evidence. `_invocations` already tracks parameter/local
shadowing, block/loop/catch/resource scopes, nested argument calls, and skips
local/anonymous type bodies. Preserve those safeguards.

A fluent suffix currently becomes a separate `<chained expression>` invocation
with an unsupported receiver. WebClient recognition must account for the whole
supported uninterrupted expression, including its consumed segment sites,
without hiding nested unrelated argument calls. Build-only expressions must
not seed request-operation chains; split locals/helpers remain unsupported.

### Interfaces and traversal

`archr/interfaces.py:resolve_interface_index` treats Feign as terminal. Ordinary
non-generic interfaces yield possible links only with one direct local concrete
implementation and a unique matching implementation method. Multiple
implementors are not filtered to manufacture a route. New repository endpoints
must also bypass implementation selection. Library targets absent from the
source index need safe handling: this function currently directly indexes
`types[link.target_type]`.

`archr/traversal.py:trace_usage` seeds roots exclusively from indexed Feign
types and excludes them from ordinary interfaces. Extend terminal/root
classification to recognized operations for every new declaration. Keep the
single `DEFAULT_MAX_CALL_STEPS = 2` setting and method-level `_endpoint`
continuity: only callers of the exact integration-calling method join a chain,
not callers of unrelated methods on its class. Possible interface redirection
costs no extra step and makes the entire chain possible. Depth/cycle boundaries
retain evidence without claiming additional callers. One WebClient expression
must consume one integration-call step, not one per fluent segment.

## Reporting, coverage, and determinism

`archr/report.py:render_report` currently accepts Feign clients and optional
usage; sorts findings by path, line, and interface name; and emits one Markdown
report with one Mermaid diagram. `_client_chains` matches source path and
interface identity. Generalize finding association to explicit declaration
identity so field findings do not share chains merely because their library
receiver types match.

`_destination` is Feign-specific and couples destination visibility to confidence
wording. New findings need independent declaration, destination, operation,
and usage evidence. Current no-caller prose correctly avoids an unused verdict,
but iteration 004 requires the explicit declaration/no-caller label and
`Destination unknown`. Current title, summary counts, HTTP/Feign descriptions,
and limitations need generalization in later report tasks. Existing tests pin
many Feign-specific strings; preserve substantive Feign evidence and guidance,
while intentional seed-driven terminology changes will require later test
alignment by the task responsible for tests.

`_usage_lines`, `_link_evidence`, `_relevant_diagnostics`, and
`_adapter_guidance_lines` are the reusable presentation seams. Relevant gaps
require receiver/type or exact candidate-method evidence, not merely a shared
caller or file. Advice is conditional: direct use invites reviewing business
decisions; a traced intermediary is only a candidate adapter location; possible
wiring must be verified first. No supported callers means no specific placement
recommendation. Replace mechanism-specific HTTP language for database findings
without inferring layers or database identity.

`_usage_diagram_lines` deduplicates class nodes and relationship labels and
retains observed/possible distinctions. It qualifies duplicate simple Feign
names, includes declaration-only integration nodes, and excludes unresolved
receivers and suggested adapters. Its current `Outbound HTTP` external edge
and system-per-client layout need explicit declaration/destination uncertainty
labels for the expanded scope; separate unknown nodes do not prove separate
real systems. Queries and method details stay outside the diagram.

`UsageTraversal.untraced_sites` consolidates all retained resolver/interface
failure diagnostics by `Invocation.site_identity` (path plus absolute lexer
offset, with a legacy fallback). Reasons are deduplicated and sorted; identical
same-line calls remain distinct. Coverage is module-wide, independent of
findings, chain count, and depth. Destination uncertainty, followed possible
links, and depth/cycle boundaries are not untraced sites. Recognized WebClient
segments must not leave a cascade of receiver diagnostics. Integration-specific
query uncertainty belongs with the finding and must never leak an unbounded
preview through diagnostic messages.

`_coverage_lines` emits a brief default summary (or the exact bounded zero-gap
statement); the flag adds only a location-ordered site list. `_markdown` and
`_diagram` escape source-derived text independently. Apply the 100-Unicode-
character query limit before Markdown escaping, not to escaped output.
Determinism currently relies on sorted source paths, traversal roots/edges and
chains, coverage sites/reasons, diagram node/edge sets, and report findings.
Retain explicit stable ordering for new identities and extracted facts.

## Existing test map for subsequent work

- `test_discovery.py`, `test_operations.py`, `test_indexing.py`: lexical
  boundaries, type identity, declarations, mappings, member ownership, source
  evidence, excluded/symlinked sources, read-only repeatability.
- `test_resolution.py`, `test_generic_argument_arity.py`,
  `test_explicit_generic_invocations.py`, `test_resource_scope.py`,
  `test_resolution_fixture_validity.py`: field resolution, shadowing and
  lexical lifetimes, nested calls, arity, ambiguity, generic exclusions.
- `test_interface_connections.py`, `test_traversal.py`: possible wiring,
  method continuity, two-step depth, cycles, terminal Feign endpoints.
- `test_report.py`, `test_usage_report.py`, `test_usage_diagram.py`,
  `test_adapter_guidance.py`, `test_adapter_guidance_boundaries.py`,
  `test_finding_diagnostic_relevance.py`, `test_analysis_limitations.py`:
  report evidence, escaping, diagram identity, conditional guidance and
  uncertainty scoped to findings.
- `test_untraced_call_coverage.py`, `test_default_coverage_summary.py`,
  `test_optional_coverage_details.py`, `test_coverage_mode_preservation.py`,
  `test_iteration_003_regressions.py`: distinct site identity, reason
  deduplication, module-wide counts, flag placement, unchanged architectural
  sections between modes, no-caller/empty-result coverage.
- `test_cli.py`, `test_acceptance.py`, `test_iteration_002_acceptance.py`,
  `test_verification_boundaries.py`, `test_iteration_003_verification.py`:
  executable behavior, naming, failures/atomic preservation, input snapshots,
  deterministic repeated reports and cross-process hash-seed stability.

No tests or analyzer behavior were changed during this inspection. Expanded
mechanism regression coverage belongs to later tasks; the existing passing
suite establishes the preservation baseline, not iteration-004 acceptance.
