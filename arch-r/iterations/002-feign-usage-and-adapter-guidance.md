# Iteration 002: Explain Feign usage and where an adapter could fit

## Outcome

A systems engineer can see how code inside the targeted module uses each
external HTTP service, including an existing intermediary, and receive a
plain-language suggestion about where an adapter could fit. Observed calls,
possible connections, and architectural suggestions are clearly separated.

This iteration extends iteration 001. Its command, input boundary, report
location, dependency discovery, destination handling, error behavior, and
deterministic output remain in force. It replaces the limitation that callers
are not inspected and permits advisory adapter suggestions. It does not
refactor code or issue an acceptance verdict.

## User command

```sh
arch-r analyze <spring-module-path>
```

The existing `arch-r-report-<module-name>.md` gains usage explanations,
supporting evidence, and adapter guidance for each Feign finding.

## Analysis boundary

Analyze Java source only within the targeted module's `src/main/java`, without
compiling, running, or modifying it. Trace calls backward from each discovered
Feign client for a maximum of **two call steps**:

```text
OrderService → ProductGateway → ProductServiceClient → product-service
```

Here, `ProductGateway → ProductServiceClient` is step one and
`OrderService → ProductGateway` is step two. The outbound HTTP connection is
not a call step. Resolving an interface to its implementation does not consume
an additional step.

Keep the depth limit as a single named analysis setting, defaulting to two,
passed to the traversal rather than embedded throughout it. A future iteration
can expose configuration without rewriting traversal. No new CLI flag or
configuration file is required now. The report states the applied limit.

Reaching the limit means the displayed chain may continue; it does not prove
that more callers exist. Mark that boundary explicitly. Stop cycles without
repeating nodes indefinitely, and explain when a cycle limits a chain.

### Supported calls

Support ordinary instance-method calls through explicitly typed Java fields,
including constructor-injected fields, with receivers written as `field.method`
or `this.field.method`. Resolve types using package declarations, explicit
imports, and fully qualified names. These forms are sufficient for this slice;
a complete Java compiler or general call-graph engine is not required.

Each observed connection requires an actual invocation and evidence of the
receiver's declared type. An import, field declaration, constructor assignment,
annotation, or class name alone is not a call.

Trace at method level before summarizing at class level: an upstream call must
reach the intermediary method that calls the Feign client. Do not connect an
upstream caller of an unrelated intermediary method to that client. For this
slice, follow methods that can be uniquely matched by name and argument count;
if that does not distinguish overloads, flag the unresolved connection instead
of selecting an overload. Helpers called within the same class need not be
followed in this iteration.

Do not infer business responsibility from names such as `Service`, `Gateway`,
or `Adapter`. Explain the observed relationship using the actual class names
and plain-language roles such as “calling code” and “intermediary.” A class that
calls a client directly may itself serve as an adapter; direct use alone is not
proof of an architectural problem.

### Calls through interfaces

When a receiver is an interface with exactly one concrete implementation
declared directly in the analyzed module, follow the corresponding method in
that implementation. Support ordinary non-generic interfaces and direct
`implements` declarations for this slice.

Label the resulting link as **possible connection**: source shows a candidate,
but runtime wiring was not verified. Cite the invocation, interface method,
implementation declaration, and implementing method. Any chain containing
this link remains a possible chain, even if its other calls are observed.

When multiple implementations are visible, report the ambiguity and name the
candidates with evidence; do not choose one or draw a confirmed upstream path
through it. Calls observed inside an implementation can still be reported.
When none is visible, say that no implementation was found within the analysis
boundary, rather than claiming that none exists.

Do not resolve Spring bean selection, qualifiers, profiles, factories, proxies,
reflection, or runtime dispatch. The Feign client itself is the terminal HTTP
integration point and does not require a local implementation.

## Report

Keep one finding per Feign client, with the existing destination and operation
details. Add these sections within each finding:

1. **How the code uses this connection:** a plain-language explanation and
   the supported chains, identifying direct callers and any intermediary.
   Explain that source calls show possible behavior, not proof of execution.
2. **Evidence and uncertainty:** readable `relative/source/path.java:line`
   citations for call sites and declarations supporting each link, plus reasons
   for possible or unresolved connections and any depth or cycle boundary.
3. **Where an adapter could fit:** conditional advice tied to the displayed
   arrangement, clearly labeled as a suggestion rather than an observed fact
   or required change.

Explain an adapter once in plain language: code that keeps the details of
communicating with an external service separate from the module's own work.
If mentioning a domain-facing interface or port, explain it as an interface
expressing what the calling code needs without exposing HTTP client details.

Keep destination confidence from iteration 001 separate from usage certainty.
An unresolved URL does not make an observed source call uncertain; a literal
URL does not make inferred runtime wiring certain.

Guidance depends on what was seen:

- **Direct use:** suggest reviewing whether the caller also handles business
  decisions. If so, a domain-facing interface between that code and the Feign
  integration could isolate external-service details. Do not assert that the
  caller contains business logic or that an adapter is missing.
- **An intermediary is visible:** identify it as a candidate adapter location.
  Suggest reviewing whether its interface expresses the caller's needs and
  keeps HTTP details out of calling code. Do not claim that it is an adequate
  architectural adapter merely because it wraps a client.
- **The chain includes a possible interface connection:** make the suggestion
  conditional on that wiring and state what the engineer should verify.
- **No supported caller is found:** retain the Feign dependency, say no caller
  was found within the supported analysis, and give no specific placement
  recommendation. Do not call the client unused.

### Diagram

Extend the single Mermaid C4-style diagram to show the calling code and
intermediaries inside the analyzed module, each Feign integration point, and
the external systems. Keep method names and source locations in supporting
text, not diagram nodes. Share repeated class nodes instead of duplicating
them for every chain.

Distinguish observed calls from possible interface connections in relationship
labels. An interface and its candidate implementation may be represented as one
labeled intermediary node if the relationship remains clear. Do not depict an
ambiguous interface route as established. Suggested new adapters belong in
the guidance text, not as existing components in the diagram.

### Limitations and stability

Replace the old “did not inspect callers” note with the actual supported call
forms, depth limit, and source-only limitations. Unsupported syntax must not
silently become proof of absence. When a relevant connection is encountered
but cannot be resolved, state that limitation with evidence; a comprehensive
inventory of unsupported Java syntax is not required.

Preserve deterministic ordering and byte-identical reports for unchanged input.
Multiple call sites for the same class relationship can share a diagram edge,
but their supporting evidence remains available in the finding.

## Acceptance examples

### Direct use is explained without asserting an architectural defect

Given `OrderService` has a constructor-injected `ProductServiceClient` field
and invokes `client.getProduct(id)` inside `placeOrder`,

When ArchR analyzes the module,

Then the product-service finding shows `OrderService → ProductServiceClient`,
cites the call site and receiver type, and explains the direct relationship.
It suggests reviewing whether a domain-facing interface would separate
business decisions from HTTP details, without claiming the caller is business
logic or declaring that an adapter is missing.

### An existing intermediary is visible

Given `OrderService.placeOrder` calls `ProductGateway.lookup`, and
`ProductGateway.lookup` calls `ProductServiceClient.getProduct`, through
explicitly typed fields,

Then the report shows both call steps, cites both invocations, identifies
`ProductGateway` as an intermediary and possible adapter location, and does not
claim it provides sufficient isolation. The diagram shows the three classes
inside the module and the external product service.

### Unrelated methods do not form a chain

Given `ProductGateway.lookup` calls Feign, `ProductGateway.health` does not,
and `OrderService` only calls `ProductGateway.health`,

Then ArchR reports the gateway's Feign call but does not show a chain from
`OrderService` to Feign through `health`.

### A single interface implementation yields a possible connection

Given `OrderService` calls `ProductGateway.lookup` through an interface field,
and `HttpProductGateway` is its sole local concrete implementation and calls
Feign in its implementation of `lookup`,

Then ArchR follows the connection within the two-step limit, identifies the
interface and implementation, and marks the upstream link and full chain as
possible. It cites the call and interface/implementation evidence, states that
runtime wiring is unverified, and makes its adapter guidance conditional.

### Multiple implementations remain ambiguous

Given the same interface call but two local implementations,

Then ArchR names both candidates with evidence and does not select one. It
still reports any directly observed implementation-to-Feign call, but neither
text nor diagram presents the upstream interface call as a confirmed route.

### The depth boundary is explicit

Given `CheckoutController → OrderService → ProductGateway → ProductServiceClient`,
with each arrow representing a supported call into the method continuing the
chain,

Then the report shows the two steps from `OrderService` through `ProductGateway`
to Feign. It does not add `CheckoutController` to that chain and says the
two-step boundary was reached and the chain may continue.

### Declarations alone are not usage

Given a class imports or holds a field of a Feign client type but never invokes
it, and there are no other supported callers,

Then the dependency remains in the report, which says no supported caller was
found and does not claim the client is unused or recommend a specific adapter
placement.

### Independent uncertainties stay separate

Given an observed direct call to a Feign client whose URL is `${product.url}`,

Then the call is reported as observed while the destination remains unresolved.
Conversely, a literal destination does not remove the possible label from an
interface-based chain.

### Traversal terminates and output remains stable

Given supported call relationships containing a cycle, multiple callers, or
multiple call sites,

Then analysis terminates within the depth limit, retains distinct supported
relationships and evidence, and explains any cycle cutoff. Repeated analysis
of unchanged input produces the same report with identical contents.

## Not in this iteration

- Proving runtime wiring, execution, reachability, or absence of other callers
- Assessing whether an adapter is sufficient or issuing an acceptance verdict
- Generating code, refactoring instructions, or test recommendations for the
  analyzed module
- General Java data-flow analysis, reflection, method references, lambdas,
  inherited method resolution, generic interface resolution, or same-class
  helper traversal
- Following receivers expressed as local variables, parameters, chained
  expressions, or dynamically constructed objects
- Resolving destination configuration or discovering other dependency types
- Analyzing other modules, test sources, or generated source trees
- A user-facing depth option or additional output formats
