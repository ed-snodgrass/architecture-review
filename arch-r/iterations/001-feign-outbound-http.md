# Iteration 001: Reveal Feign outbound HTTP dependencies

## Outcome

A systems engineer can point ArchR at one conventional Java/Spring Maven
module and receive a readable Markdown report of the module's statically
declared OpenFeign HTTP dependencies.

This iteration proves the smallest complete ArchR experience: find an
architecturally significant connection, explain it in plain language, point
to its evidence, state uncertainty honestly, and show the connection in a
simple diagram.

## User command

```sh
arch-r analyze <spring-module-path>
```

`<spring-module-path>` may be relative to the current directory or absolute.
ArchR analyzes the module without compiling or running it.

On success, ArchR writes the report in the caller's current directory:

```text
arch-r-report-<module-name>.md
```

The filename-safe module name replaces each run of characters other than
letters, digits, `.`, `_`, or `-` with `-`. The report itself retains the
original, readable module name.

## Analysis boundary

For this iteration, a module is a directory with the conventional Maven
source tree `src/main/java`. ArchR recursively examines Java source files in
that tree only.

The module name is:

1. the project's `<artifactId>` from the module's `pom.xml`; or
2. the module directory's name when no artifact ID can be read.

ArchR finds interfaces annotated with Spring Cloud OpenFeign's
`@FeignClient`. For each client it records:

- the external-system name from the annotation's `name` attribute, or its
  alias `value`;
- the `url` attribute, when present;
- operations declared with Spring mapping annotations such as
  `@RequestMapping`, `@GetMapping`, `@PostMapping`, `@PutMapping`,
  `@PatchMapping`, and `@DeleteMapping`; and
- the source file and line supporting every reported fact.

ArchR treats a Feign client as the module's HTTP integration point. It does
not assume that this integration point is a sufficient architectural adapter.

## Report

The generated Markdown report must stand on its own for a reader who is not a
software developer. It contains:

1. The analyzed module's name and path.
2. A short summary stating how many outbound HTTP dependencies were found.
3. One finding for each Feign client, including:
   - a plain-language description of the connection;
   - the external-system name;
   - the literal destination URL, or the unresolved property placeholder;
   - the confidence and reason for it;
   - the discovered HTTP operations as supporting detail; and
   - clickable or plainly readable `relative/source/path.java:line` evidence.
4. One Mermaid C4-style diagram showing the analyzed module, each Feign
   integration point, and each external HTTP system. The diagram shows
   architectural connections, not individual methods or code structure.
5. A limitations note saying that ArchR did not inspect callers and therefore
   did not determine whether a separate domain-facing port or adapter is
   needed.

Findings with a literal URL have **high confidence**, because both the client
declaration and destination are visible in source. Findings whose URL is a
`${...}` placeholder are marked **destination unresolved** with lower
confidence. The report names the placeholder but does not guess or resolve
its value.

The report must remain deterministic for unchanged input so it is useful in
version control.

## Acceptance examples

### A literal destination is explained with evidence

Given a Maven module named `order-service` containing:

```java
@FeignClient(name = "inventory", url = "https://inventory.example")
public interface InventoryClient {
    @GetMapping("/items/{id}")
    Item getItem(@PathVariable String id);
}
```

When the engineer runs:

```sh
arch-r analyze path/to/order-service
```

Then ArchR creates `arch-r-report-order-service.md` in the current directory,
and the report:

- says that `order-service` makes an outbound HTTP connection to `inventory`;
- shows `https://inventory.example` as the destination;
- marks the finding high confidence;
- describes the `GET /items/{id}` operation as supporting detail;
- cites the Feign declaration and mapped operation by source file and line;
  and
- diagrams `order-service`, its Feign integration point, and the external
  `inventory` system.

### A configured destination is not guessed

Given a Feign client declared with:

```java
@FeignClient(name = "pricing", url = "${pricing.url}")
```

When ArchR analyzes the module,

Then the report identifies `pricing` as an outbound HTTP dependency,
shows `${pricing.url}` as unresolved, explains the reduced confidence, and
does not claim a concrete host or inspect Spring configuration to find one.

### Annotation aliases are understood

Given a client declared with `@FeignClient(value = "shipping", url =
"https://shipping.example")`,

When ArchR analyzes the module,

Then the report names the external system `shipping`.

### Multiple clients produce multiple clear findings

Given a module containing two Feign client interfaces,

When ArchR analyzes the module,

Then the report contains two findings and a single diagram showing both
outbound connections without adding method-level detail to the diagram.

### No finding is still a useful result

Given a valid module whose `src/main/java` contains no `@FeignClient`,

When ArchR analyzes the module,

Then ArchR creates the module-named report, states that no statically declared
Feign outbound HTTP dependencies were found, and does not imply that the
module makes no outbound calls by other means.

### Invalid input fails clearly

Given a missing path, an unreadable path, or a path that is not a directory,

When ArchR is asked to analyze it,

Then ArchR exits unsuccessfully with a concise explanation and does not write
a report.

### Repeated analysis is stable

Given an unchanged module,

When ArchR analyzes it twice from the same current directory,

Then the second run replaces the same module-named report with identical
content rather than creating another report.

## Not in this iteration

- Inspecting callers of a Feign client
- Deciding whether the code needs a separate port or adapter
- Recommending refactoring or issuing an acceptance verdict
- Resolving `${...}` placeholders from properties, YAML, profiles,
  environment variables, or configuration services
- Detecting `RestClient`, `WebClient`, `RestTemplate`, Spring HTTP Service
  Clients, raw HTTP libraries, messaging, or database dependencies
- Gradle-specific metadata, Maven aggregator analysis, test sources, or
  generated sources
- Compiling, running, or modifying the analyzed module
- Producing HTML, JSON, or PlantUML output

