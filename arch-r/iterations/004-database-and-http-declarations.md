# Iteration 004: Reveal database and additional HTTP declarations

## Outcome

A systems engineer sees recognized database and additional HTTP integration
declarations, their supported callers, and conditional adapter guidance.
Declarations remain useful findings even when no supported caller is found.

This iteration builds on completed iterations 001–003. Preserve Feign
behavior, two-step usage tracing, interface uncertainty, report naming, error
handling, deterministic output, and iteration 003's coverage reporting.
Expand dependency detection to the four mechanisms specified below.

## Commands and analysis boundary

```sh
arch-r analyze <spring-module-path>
arch-r analyze <spring-module-path> --show-analysis-limitations
```

No new command-line option is introduced. Both forms retain iteration 003's
report behavior and flag placement support.

Continue analyzing only the targeted module's `src/main/java`, without
compiling, running, or modifying it. Do not resolve configuration, bean wiring,
or external modules. Keep the default two-call-step limit in its existing
single analysis setting; no user-facing depth option is required.

## Recognized declarations

Retain OpenFeign and add exactly these mechanisms:

| Mechanism | Declaration required for a finding |
| --- | --- |
| Spring Data JPA | A source interface directly extending `org.springframework.data.jpa.repository.JpaRepository`, including normal entity/ID type arguments |
| Spring JDBC | An explicitly typed field of `org.springframework.jdbc.core.JdbcTemplate` |
| Spring HTTP | An explicitly typed field of `org.springframework.web.client.RestTemplate` |
| Spring reactive HTTP | An explicitly typed field of `org.springframework.web.reactive.function.client.WebClient` |

Include constructor-injected fields. Resolve types through explicit imports,
package declarations, and fully qualified names. A matching simple name alone
is insufficient: a local class named `JdbcTemplate` is not the Spring type.
Imports alone, constructor parameters without matching typed fields, local
variables, and `@Bean` factory methods do not create findings in this slice.
Indirect repository inheritance and custom subclasses of these client types
are outside scope.

A declaration is enough to report an integration even when no supported caller
is found. Label that state **Declared integration — No supported caller found**.
Do not equate a declaration with execution or call the integration unused.
`JpaRepository` indicates JPA persistence access; it does not establish a
particular database, JDBC URL, or direct JDBC call.

Use one finding per repository interface, and one per supported client field,
identified by its declaring class and field name. Continue one per Feign
interface. Calls through fields of the same repository interface belong to its
single finding. Multiple fields or repositories do not prove multiple distinct
external systems; describe summary counts as **integration declarations**,
with HTTP and database subtotals, rather than unique services or databases.

## Usage and operation evidence

Reuse iteration 002's field-call resolution and method-level chain continuity.
The new libraries are known integration endpoints: resolving their operations
does not require source for the library or a local repository implementation.
This is a narrow exception to the earlier exclusions for generic interfaces
and inherited operations, not a requirement for general Java type analysis.

Support direct calls through `field` or `this.field` as follows:

- Repository methods declared on the recognized interface, plus the common
  inherited operations `save`, `saveAll`, `findById`, `findAll`, `existsById`,
  `count`, `delete`, `deleteById`, and `deleteAll`. Do not infer SQL from method
  names. Do not treat `toString`, `equals`, or `hashCode` as persistence access.
- `JdbcTemplate.query`, `queryForObject`, `queryForList`, `update`, `execute`,
  and `batchUpdate`. Extract a query preview when the first argument is a
  directly visible string literal or Java text block. Other overloads retain
  call evidence but do not yield invented query text.
- `RestTemplate.getForObject`, `getForEntity`, `postForObject`, `postForEntity`,
  `put`, `patchForObject`, `delete`, `headForHeaders`, and `optionsForAllow`:
  report the corresponding HTTP verb and a literal first-argument URL/path
  when present. Also support `exchange` with a literal first argument and an
  explicit Spring `HttpMethod` constant as the second argument. Unknown
  arguments remain unresolved independently of the recognized operation.

For `WebClient`, additionally recognize an uninterrupted fluent expression
rooted in a supported field, for example:

```java
client.get().uri("https://products.example/items").retrieve().bodyToMono(String.class);
```

Extract HTTP verbs from `get`, `post`, `put`, `patch`, `delete`, `head`,
`options`, or `method` with an explicit Spring `HttpMethod` constant. Extract a
literal argument to `uri`. Recognize `retrieve`, `exchangeToMono`, and
`exchangeToFlux` as request operations in that same expression. This does not
prove subscription or network execution. A chain that only builds a request
may supply configuration evidence but must not be called an observed request
operation. Do not join chains split across local variables or helper methods.
This bounded pattern is the only new chained-receiver support required.

In backward tracing, a method invoking a recognized operation is the first
caller of the integration; its supported upstream caller is the second step.
WebClient's fluent segments together represent one integration call step.
Do not trace unrelated methods of a declaring class into the integration.
Keep existing possible-interface links and their evidence and uncertainty.

If no supported operation caller is found, retain the declaration and its
no-caller label even when other methods on the field are referenced. Unknown
operations do not remove a declaration or become invented external calls.

## Destinations and query previews

Show literal URLs and HTTP methods only where supported source evidence makes
them visible. A relative URI is a path, not a known host. Preserve placeholders
as unresolved; do not resolve constants, variables, builder configuration,
properties, profiles, or runtime expressions. If only the injected declaration
is known, report **Destination unknown**. Never invent a database name from a
repository, entity, field, or query table name.

For repository methods, inspect Spring Data JPA's
`org.springframework.data.jpa.repository.Query` annotation:

- Show a directly literal `value`, including its shorthand annotation form.
- Label it **SQL** when `nativeQuery = true` is explicit.
- Label it **JPQL** when `nativeQuery` is absent or explicitly false; explain
  once that JPQL queries Java persistence entities rather than database tables.
- If the native-query setting cannot be resolved, label it **Query (language
  unresolved)** instead of choosing SQL or JPQL.

Include annotated query evidence even if no caller is found. Do not extract
named queries, derive generated SQL, or evaluate concatenated expressions.

For both JdbcTemplate SQL and repository query text:

1. Read the literal value, collapse whitespace runs to one space, and trim it.
2. Show at most **100 Unicode characters**, including the truncation marker:
   if longer than 100, show the first 99 characters followed by `…`.
3. Cite the query's source file and line so the full text can be inspected.

The limit applies to the visible query preview, not its label, citation, or
Markdown escaping. Do not include the full truncated query elsewhere in the
report, including detailed coverage output. Nonliteral queries are marked
unresolved with source evidence rather than evaluated.

## Report and diagram

Use a general title such as **Outbound dependencies: order-service**. Keep
the module identity, a short summary, one finding per declaration, a single
Mermaid C4-style diagram, and limitations. Each finding explains:

- the mechanism and declared integration in plain language;
- whether a supported operation caller was found;
- known or unknown destinations, operation details, and bounded query previews;
- source-path-and-line evidence for declarations, calls, and extracted facts;
- supported usage chains, relevant uncertainty, and conditional adapter advice.

Keep declaration evidence, destination certainty, and usage certainty separate.
An unknown database destination does not weaken evidence of a repository
declaration or an observed source call.

Apply iteration 002's guidance to all mechanisms: direct use can prompt review
of whether business decisions depend on integration details; an intermediary
can be a candidate adapter location. Do not infer architectural layers or
business responsibility from names, classify every direct call as a defect,
or assert that persistence types leak into business logic without analysis.
Give no specific placement recommendation when no supported caller is found.

The diagram includes recognized integrations and supported usage relationships,
with unknown external destinations clearly labeled. If using separate unknown
destination nodes for different findings, make clear that they do not establish
distinct real systems. Distinguish declared integrations, observed source calls,
and possible links in labels. Do not draw declarations as confirmed runtime
traffic. Keep queries, method details, and unsupported receivers out of the
diagram. Suggested adapters remain guidance, not existing components.

## Coverage inherited from iteration 003

Preserve iteration 003's brief default coverage summary and opt-in details via
`--show-analysis-limitations`, applying them to the expanded analysis.
Supported WebClient fluent segments must not produce a cascade of
unsupported-receiver warnings or inflate the untraced-site count. Unresolved
query expressions and other uncertainty tied to a recognized integration stay
beside that finding. General limitations must name the supported libraries and
source forms accurately.

## Acceptance examples

### A repository declaration is useful without callers

Given `OrderRepository extends JpaRepository<Order, Long>` with the correct
Spring import and no supported caller,

Then ArchR reports one declared JPA database integration with declaration
evidence, **No supported caller found**, and **Destination unknown**. It does
not require a local implementation, identify a database, or call it unused.

### Client fields are declarations, imports alone are not

Given explicitly typed fields for JdbcTemplate, RestTemplate, and WebClient,
with no calls,

Then ArchR reports three declarations with no supported caller found. An
unused import or an unrelated user-defined class with the same simple name
produces no additional integration finding.

### SQL and JPQL previews are bounded

Given a JdbcTemplate call with literal SQL, a repository `@Query` with default
settings, and another `@Query(nativeQuery = true, value = "...")`,

Then their query labels are SQL, JPQL, and SQL respectively, with source
evidence. Whitespace is normalized. A 100-character normalized query is shown
unchanged; a 101-character query becomes 99 characters plus `…`. A multiline
Java text block follows the same rules. Detailed mode never reveals a longer
preview. A nonliteral query remains unresolved.

### A database caller and intermediary are explained

Given `OrderService.placeOrder → OrderGateway.store → OrderRepository.save`,
using supported typed fields,

Then the repository finding shows the two-step chain with invocation and
receiver evidence. It identifies the gateway as an intermediary and gives
conditional adapter guidance without claiming actual database execution.

### RestTemplate operations expose only visible destination details

Given `rest.getForObject("https://products.example/items", String.class)`,

Then the field's finding includes GET, the literal URL, and call evidence.
For a variable URL, the operation remains visible but the destination is
unresolved. For a relative path, ArchR does not invent a host.

### WebClient fluent requests are recognized within the agreed boundary

Given a supported WebClient field used in
`client.get().uri("/items").retrieve().bodyToMono(String.class)`,

Then the finding reports GET, path `/items`, unknown host, and source request
evidence without claiming subscription or runtime traffic. Fluent segments
do not inflate either call depth or coverage counts. A request builder split
across local variables is not reconstructed; the field declaration remains.

### Counts do not imply unique systems or complete coverage

Given two repository interfaces and two RestTemplate fields,

Then the summary counts four integration declarations: two database and two
HTTP. It does not assert four external systems. With no recognized declaration,
the report says none were found within supported scope, not that the module
has no external dependencies.

### Existing behavior and stable output remain intact

Given Feign declarations alongside the new mechanisms,

Then Feign evidence and usage guidance still appear, and all mechanisms share
the report and diagram. Repeated runs with the same options are byte-identical;
the analyzed module is unchanged. Invalid input retains the existing failure
behavior and does not replace a previously successful report.

## Not in this iteration

- Additional libraries such as RestClient, NamedParameterJdbcTemplate,
  EntityManager, MyBatis, raw JDBC, Java HttpClient, messaging, or cloud SDKs
- Indirect repository inheritance, custom client subclasses, or general
  inherited/generic method resolution
- New declarations from locals, parameters alone, factories, or bean methods
- General chained-expression, data-flow, same-class helper, or runtime analysis
- Configuration resolution, database identity discovery, SQL generation,
  query validation, or automatic architectural-layer classification
- Code changes or test recommendations for the analyzed module, acceptance
  verdicts, additional output formats, or a user-facing depth setting
