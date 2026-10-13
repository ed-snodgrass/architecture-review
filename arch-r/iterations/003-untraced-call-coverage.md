# Iteration 003: Summarize untraced calls with optional details

## Outcome

A systems engineer can read the existing Feign dependency report without
unrelated untraced calls appearing as architectural concerns. A brief coverage
summary preserves awareness of analysis gaps; an optional flag exposes the
individual call sites and reasons.

This iteration builds on iterations 001 and 002. Preserve Feign discovery,
source evidence, two-step usage tracing, interface uncertainty, adapter
guidance, and the existing diagram. This slice changes how analysis coverage
is presented; it adds no dependency mechanisms or supported call forms.

## Commands and report behavior

```sh
arch-r analyze <spring-module-path>
arch-r analyze <spring-module-path> --show-analysis-limitations
```

Accept the flag before or after the module path. Both forms write the existing
`arch-r-report-<module-name>.md` in the caller's current directory. The flag
adds coverage details to that report, not a separate artifact. Switching modes
replaces the same report, removing the optional details on a default run.

Preserve the existing source boundary, read-only analysis, error behavior,
and output determinism. Identical input and options produce identical output.

## Brief default coverage

Retain untraced-call diagnostics internally, including `unsupported-receiver`,
but do not present them as architectural findings without dependency evidence.
Default coverage is at most two short sentences, for example:

> 7 call sites were not traced; external effects cannot be ruled out.
> Use `--show-analysis-limitations` for details.

With none recorded, use **No untraced call sites recorded within supported
analysis.** This does not imply complete Java coverage or absence of other
external dependencies.

Count distinct recorded untraced invocation sites module-wide, not once per
finding or diagnostic reason. Distinct calls on the same source line remain
separate sites. Repeated traversal or multiple reasons for one site do not
increase the count. This counts recorded call-tracing gaps, not every construct
that the analyzer might fail to recognize.

Show coverage even when no Feign dependency is found. Do not add individual
unrelated call sites, diagnostic codes, or reasons to the default report.
Keep the existing general scope and limitations note accurate and concise.

## Optional coverage details

With `--show-analysis-limitations`, retain the brief summary and append a
module-wide list of the counted sites. Each entry provides a readable relative
source path and line, identifies the call, and explains in plain language why
it was not traced. Include enough location or call information to distinguish
multiple sites on one line. Diagnostic codes alone are not sufficient.

Order entries deterministically by source location. Consolidate reasons for a
site, deduplicating repeated reasons. Do not repeat the list under each Feign
finding. The flag changes only coverage detail: dependency counts, findings,
usage chains, guidance, and diagrams must be identical between modes.

## Keep relevant uncertainty beside the finding

Do not hide uncertainty that specifically affects a recognized Feign
integration: ambiguous implementations or overloads, unresolved destinations,
and depth or cycle cutoffs remain with their evidence in the default finding.
These are not all untraced call sites; destination uncertainty and traversal
limits alone must not inflate the untraced-site count.

An unrelated call such as `request.getId()` must not be attributed to every
integration or produce an adapter warning. An untraced site may remain
referenced beside a finding when receiver/type evidence connects it to that
integration. Proximity in the same method alone is insufficient.

A relevant untraced invocation can appear beside its finding and in detailed
coverage, but is counted only once module-wide. A possible interface link
that was followed is not an untraced call solely because runtime wiring is
unverified.

Never claim that untraced calls have no external effects. No new detector,
general call-graph expansion, or proof of external behavior is required to
classify the existing diagnostics for presentation.

## Acceptance examples

### Unrelated unsupported receivers become a brief summary

Given a Feign finding and seven distinct recorded untraced calls through local
variables or parameters, with no evidence connecting those calls to the client,

When ArchR runs without the flag,

Then the report states that seven call sites were not traced in at most two
short coverage sentences. It does not list those sites or reasons, turn them
into dependency findings, diagram them, or give adapter advice about them.

### Details are available on request

Given the same input,

When ArchR runs with `--show-analysis-limitations`,

Then the report retains the summary and lists the seven sites with source
locations, call identification, and plain-language reasons. Its findings,
dependency counts, usage chains, guidance, and diagram match the default run.
The flag works before and after the module path.

### Shared diagnostics are counted once

Given several Feign clients and one untraced invocation recorded during
multiple traversals with repeated or different reasons,

Then the summary counts one site, and detailed coverage contains one entry
with distinct reasons. Two different untraced calls on the same line count
as two sites and remain distinguishable in the details.

### Relevant uncertainty remains visible by default

Given a possible interface connection, an ambiguous overload relevant to a
Feign client, an unresolved destination, and an unrelated untraced call,

Then relevant uncertainty and evidence remain beside the finding in both
modes. The unrelated site is listed only in detailed mode. The summary counts
recorded untraced invocations, not followed possible links or destination
uncertainty.

### Coverage is meaningful without findings or gaps

Given a module with no Feign findings but recorded untraced calls,

Then its report still includes the coverage summary and optional details.

Given no recorded untraced call sites,

Then the report says no untraced call sites were recorded within supported
analysis. It does not claim full coverage or absence of external dependencies.
Detailed mode does not invent entries.

### Output remains stable and reversible between modes

Given unchanged module input,

Then repeated runs with the same options are byte-identical. A detailed run
followed by a default run replaces the same file and removes optional details.
Neither run modifies the module. Existing invalid-input and output-failure
behavior remains intact, including preserving a previous successful report.

## Not in this iteration

- Database or additional HTTP dependency detection; these belong to iteration 004
- New call forms, query extraction, destination resolution, or expanded tracing
- Changes to dependency grouping, diagram structure, or architectural guidance
  beyond removing concerns based solely on unrelated untraced calls
- Separate diagnostic artifacts, new output formats, or a depth option
- Code changes or test recommendations for the analyzed module or acceptance verdicts
