# Iteration 005: Prioritize report findings and defer supporting detail

## Outcome

A systems engineer can scan ArchR's most important results before reading its
architectural guidance, source evidence, and analysis limitations. Every
integration is summarized in the same compact format, while supporting detail
remains available later in the report without repeated caveats or call-chain
prose.

This iteration builds on completed iterations 001–004. Preserve all existing
discovery, destination, operation, query, traversal, uncertainty, diagram,
coverage, command-line, error, and deterministic-output behavior. This slice
restructures the Markdown report and makes its adapter guidance easier to
understand; it does not expand or reinterpret the analysis.

## Commands and analysis boundary

Retain both existing commands and their current flag-placement behavior:

```sh
arch-r analyze <spring-module-path>
arch-r analyze <spring-module-path> --show-analysis-limitations
```

Continue analyzing only the targeted module's `src/main/java`, without
compiling, running, or modifying it. Keep the two-call-step limit and all
supported declaration and invocation forms from iteration 004. No new option,
output artifact, analysis mechanism, or destination resolution is introduced.

## Report order

Render every report in this order:

1. Report title and module identity
2. **Summary**
3. **Architectural Connections**
4. **Findings**
5. **Adapter Review Guidance**
6. **Findings with Evidence**
7. **Limitations**

Keep the existing summary meaning and counts. Move the single Mermaid C4-style
diagram immediately after the summary without changing what its nodes and
relationships assert. All brief findings appear before any expanded guidance,
and all expanded guidance appears before any detailed evidence. Preserve the
same deterministic finding order across those three sections.

## Brief findings

Under **Findings**, render one short card per recognized integration. Use the
integration point, rather than the external system, as its title. For example,
use `ProductServiceClient` for a Feign integration and `OrderRepository` for a
repository integration. Retain enough qualification or declaring-class and
field identity to distinguish integration points that otherwise have the same
name.

Every card uses these labels in this order:

1. **Destination**
2. **Status**
3. **External system**
4. **Mechanism**
5. **Adapter Recommendation**

Do not include operations, query previews, declaration citations, call-chain
detail, confidence paragraphs, or general source-only caveats in a card.

Use explicit **Unknown** or **Unresolved** values rather than omitting a field
or inventing a value. Preserve the distinction between an unresolved
expression such as `${product-service.url}` and a destination for which no
value is known. A repository does not establish a database identity, so both
its destination and external system remain unknown unless supported evidence
already establishes otherwise.

Use concise caller-status vocabulary:

- **Caller found** when a supported source caller chain was established;
- **No caller found** when no supported caller or relevant unresolved caller
  was recorded within the analysis boundary; and
- **Caller unresolved** when evidence connects a possible caller to the
  integration but the supported analysis cannot resolve that connection.

These labels summarize source-analysis state only. Explain their meaning once
in Limitations; do not repeat the explanation on every card.

The Adapter Recommendation is at most one sentence. It identifies the actual
observed class or method to inspect and the condition to inspect for. It must
not assert that the condition exists. Link it to that finding's expanded
guidance and link the card separately to that finding's evidence. When no
supported caller identifies code to inspect, still render the field and state
why no recommendation is provided, for example: **No recommendation: no
supported caller was found, so ArchR cannot identify code to inspect.**

## Adapter review guidance

Under **Adapter Review Guidance**, render one subsection per finding in the
same order and with a stable link target from its card. Guidance identifies
what a systems engineer should inspect to decide whether an adapter would be
valuable. It does not recommend a particular interface, wrapper,
implementation shape, class placement, or refactoring in this iteration.

Use the actual observed class and method names in guidance. Do not infer
behavior from those names or present illustrative behavior as an observation.
Each example must be introduced as an illustrative “if your code looks like
this” condition that was not established by ArchR.

Explain each review condition in plain language before or after its example so
a reader does not need prior knowledge of adapter terminology. In particular:

- interpreting a client response means translating external fields, statuses,
  or representations into meaning used by this module;
- handling integration-specific failures means code directly reacts to details
  such as HTTP status codes, timeouts, client-library exceptions, retry rules,
  SQL errors, or persistence-library behavior; and
- mixing integration details with business decisions means the same method
  both communicates with a dependency and decides what the module should do.

Give each applicable condition its own small Java example rather than one
example that combines several concerns. Keep examples brief and educational.
Use only observed class and method names, but hypothetical local names and
statements may illustrate the condition. Never claim the illustrated branch,
exception handling, mapping, or decision was found in source.

Tailor conditions to the mechanism and available caller evidence. Do not show
HTTP-specific examples for a repository merely to fill a template. If no
supported caller was found, explicitly explain that ArchR cannot identify code
to review and provide no invented code example. Possible or unresolved
connections keep their existing uncertainty and make the guidance conditional.

## Findings with evidence

Under **Findings with Evidence**, render one subsection per finding in the same
order and with a stable link target from its card. Every finding uses these
subheadings in this order, even when a subsection has no evidence:

1. **Declaration**
2. **Operations**
3. **Observed Call Chains**

For an empty subsection, state explicitly what was not observed within the
supported analysis, such as **No supported operations observed.** Do not omit
the heading and do not turn absence within the supported scope into proof that
runtime behavior is absent.

### Selective source citations

The Declaration subsection gives the integration declaration's relative source
path and line. The Operations subsection gives one readable source location
for each observed operation, request, or query and retains bounded query
previews and operation-specific destination facts from iteration 004. It need
not repeat receiver declarations, target declarations, or method-token
locations for every call.

The Observed Call Chains subsection uses compact method paths, for example:

```text
OrderController.placeOrder → OrderService.placeOrder → OrderRepository.save
```

Do not expand every path step into a paragraph of invocation, receiver, target,
and method-name citations. Preserve whether a path is observed, possible, or
unresolved, plus relevant interface ambiguity and traversal depth or cycle
boundaries. Put finding-specific uncertainty beside the relevant evidence, not
on the brief card or in the global Limitations section.

### Group repeated paths

Group operations that share an upstream method path. For example:

```text
OrderController.placeOrder → OrderService.placeOrder
  → OrderRepository.findByCustomerIdAndIdempotencyKey
  → OrderRepository.save
```

Show a shared path once rather than emitting a separately numbered chain with
the same explanation for each terminal operation. Deduplicate equivalent paths
without combining paths whose methods, certainty, interface resolution, depth
boundary, or cycle behavior differ. Each observed operation remains visible
under Operations with its selective citation.

Do not repeat general statements about source calls, runtime execution,
destination independence, traversal depth, or library source under every
finding. State them once in Limitations. Within evidence, include only
uncertainty that changes how that particular finding or path should be read.

## Short, report-relevant limitations

Replace the current exhaustive limitations prose with a shorter summary of the
limitations that apply to the generated report. Include, once:

- the Java source boundary and the fact that ArchR did not compile or run the
  module;
- the applied two-call-step traversal limit;
- the meaning of **Caller found**, **No caller found**, and **Caller
  unresolved**;
- that declarations and source calls do not prove runtime wiring, execution,
  or reachability;
- unresolved destination or configuration facts relevant to the report;
- supported mechanisms and source forms at a concise level; and
- the module-wide untraced-call coverage summary inherited from iteration 003.

Put the default coverage summary in Limitations rather than creating a separate
top-level Analysis Coverage section. With `--show-analysis-limitations`, append
the existing deduplicated, source-ordered call-site details there. The flag
continues to change only the coverage detail; findings, guidance, evidence, and
the diagram remain identical between modes.

Do not repeat finding-specific unresolved expressions, interface candidates,
query uncertainty, or path boundaries in Limitations when they already appear
with the affected evidence. Do not publish a catalog of every unsupported Java
construct when it did not affect the report.

## Acceptance examples

### The important information appears first

Given a report containing a Feign client and a JPA repository,

Then Summary is followed by Architectural Connections and the complete brief
Findings section. Adapter Review Guidance follows all cards, Findings with
Evidence follows all guidance, and Limitations is last. The two findings have
the same order in all three finding-oriented sections.

### Cards are uniform and concise

Given `ProductServiceClient` targets `${product-service.url}` through OpenFeign
and has a supported caller,

Then its card is titled with `ProductServiceClient` and contains, in order,
Destination `${product-service.url}` marked unresolved, Status **Caller
found**, External system `product-service`, Mechanism `OpenFeign HTTP client`,
and a one-sentence Adapter Recommendation. It links to both its guidance and
its evidence and contains no operations, source citations, confidence
paragraphs, or repeated runtime caveats.

Given `OrderRepository` identifies no database,

Then its integration-point card explicitly reports Destination **Unknown** and
External system **Unknown** rather than omitting or inventing those values.

### Guidance explains conditions without claiming they were observed

Given `OrderService.resolveItem` directly invokes
`ProductServiceClient.getProduct`,

Then the card recommends inspecting `OrderService.resolveItem` in one sentence.
Its expanded guidance separately explains response interpretation,
integration-specific failure handling, and mixed integration and module
decisions in plain language. Each applicable condition has its own small Java
example using the observed names, and every example is clearly illustrative
rather than reported as analyzed behavior. The guidance does not yet prescribe
a domain-facing interface or other adapter shape.

### No caller yields an honest non-recommendation

Given a recognized integration declaration with no supported or relevant
unresolved caller,

Then its card says **No caller found** and its Adapter Recommendation states
that none is provided because ArchR cannot identify code to inspect. Its
guidance subsection repeats that specific reason without inventing a class,
method, behavior, or example.

### Evidence is selective and consistently structured

Given an integration with declaration and operation evidence,

Then its evidence has Declaration, Operations, and Observed Call Chains
subheadings. Declaration has one source location, each operation has one useful
source location, and the chain is a compact method path without per-step
receiver and target citations. Finding-specific uncertainty remains adjacent
to the affected evidence.

Given a finding with no supported operations or chains,

Then both empty subsections remain present with explicit scoped statements and
do not claim that runtime operations or callers are absent.

### Repeated repository paths are grouped

Given `OrderController.placeOrder → OrderService.placeOrder` reaches both
`OrderRepository.findByCustomerIdAndIdempotencyKey` and
`OrderRepository.save`,

Then the shared controller-to-service path appears once with both repository
operations beneath it. Each operation retains its own selective citation in
Operations. Other controller methods remain separate paths.

### Caveats and coverage are stated once

Given several findings share the same source-only and traversal limitations,

Then those caveats appear once in a short Limitations section, not in every
card, guidance subsection, or evidence subsection. The default untraced-call
summary also appears there. Detailed mode appends the existing call-site list
without changing any other report section.

### Existing analysis remains stable

Given the same module and command options before and after this iteration,

Then recognized declarations, extracted operations and queries, destination
certainty, call resolution, diagram relationships, and coverage counts do not
change merely because their presentation moved. Repeated runs are
byte-identical, invalid input retains existing failure behavior, and the
analyzed module is not modified.

## Not in this iteration

- New dependency mechanisms, call forms, tracing depth, configuration
  resolution, or runtime analysis
- Changes to the meaning or contents of the architectural diagram
- A new output format, interactive or collapsible report, or user-configurable
  report layout
- Prescribing a domain-facing interface, adapter implementation, class
  placement, or refactoring
- Deciding whether an adapter is required or issuing an architectural
  acceptance verdict
- Quoting or reconstructing the analyzed method body as though illustrative
  examples were observed source
- Changes to the analyzed module or recommendations for its tests
