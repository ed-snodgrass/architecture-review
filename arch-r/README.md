# ArchR

ArchR reports statically declared Spring Cloud OpenFeign outbound HTTP dependencies in one conventional Java/Spring Maven module. It reads source without compiling, running, or modifying the module.

## Requirements and usage

Python 3.10 or newer is required. There are no third-party Python dependencies, and Java and Maven are not required.

From this repository:

```sh
./arch-r analyze path/to/order-service
./arch-r analyze /absolute/path/to/order-service
```

The module must have a readable `src/main/java` directory. Relative module paths are resolved from the caller's current directory. To run from another directory, use the absolute path to this repository's `arch-r` executable (or put this repository on `PATH`):

```sh
/path/to/arch-r analyze ./order-service
```

On success, ArchR writes `arch-r-report-<module-name>.md` in the **caller's current directory**, not necessarily in the analyzed module. It uses the project's own Maven `artifactId`, falling back to the module directory name when the artifact ID cannot be read. Filename characters other than ASCII letters, digits, `.`, `_`, and `-` are replaced in runs with `-`; the report retains the readable name.

Repeated analysis replaces the same report with identical content for unchanged input. Invalid or unreadable input and output failures produce a concise error on stderr and a nonzero exit status, without creating a new report or replacing an existing successful report.

## Reading the report

The standalone Markdown report includes the module name and path, a dependency count, one plain-language finding per Feign interface, source-path-and-line evidence, mapped HTTP operations, usage chains, conditional adapter guidance, and one Mermaid C4-style architectural diagram. The diagram distinguishes observed source calls from possible interface connections; suggested adapters appear only in guidance text. A Markdown viewer with Mermaid C4 support can render the diagram; its source is also readable as text.

- **High confidence:** the client declaration and a literal destination URL are visible in source.
- **Lower confidence / destination unresolved:** the URL contains a `${...}` placeholder, is an unevaluated expression, or is absent. ArchR shows what is declared and does not guess a destination or resolve configuration.
- **No findings:** no supported statically declared Feign dependencies were found. This does not mean the module has no outbound calls by other means.

## Scope and limitations

ArchR recursively scans Java files only under `src/main/java`. It recognizes OpenFeign interface declarations and Spring `RequestMapping`, `GetMapping`, `PostMapping`, `PutMapping`, `PatchMapping`, and `DeleteMapping` operations, including interface-level mappings. This is source-level analysis, not a Java compiler or a runtime call trace; inherited operations and runtime behavior are outside its scope.

ArchR traces callers backward from each Feign client for at most **two call steps**, using ordinary instance-method invocations through explicitly typed fields (including constructor-injected fields), written as `field.method(...)` or `this.field.method(...)`. It resolves types using packages, explicit imports, and fully qualified names, and matches methods by name and argument count. It does not connect callers of unrelated intermediary methods or choose among ambiguous overloads. Declarations alone are not usage.

For ordinary non-generic interfaces with a single direct concrete implementation in the module, ArchR reports a **possible connection**, not verified runtime wiring. Multiple implementations remain ambiguous; no local implementation means none was found within the analysis boundary. Interface resolution and the outbound HTTP connection do not consume call steps. The report states the applied limit and marks depth and cycle boundaries; a chain reaching the limit may continue, but does not prove more callers exist.

Adapter guidance is a conditional suggestion, not an observed fact or required change. An adapter keeps external-service communication details separate from the module's own work; a domain-facing interface expresses what callers need without exposing HTTP client details. For direct use, ArchR suggests reviewing whether the caller also handles business decisions. A visible intermediary is a candidate adapter location, not proof of adequate isolation. Guidance for possible interface wiring is conditional on verifying that wiring. If no supported caller is found, ArchR gives no specific placement recommendation and does not call the client unused.

Source calls do not prove execution, reachability, or runtime wiring; destination confidence is separate from usage certainty. Unsupported or unresolved connections are not proof that callers are absent. Local-variable or parameter receivers, chained or dynamically constructed receivers, same-class helper traversal, inherited method resolution, generic interface resolution, reflection, method references, and lambdas are outside the supported slice. ArchR does not resolve Spring bean selection, qualifiers, profiles, factories, or proxies. It does not generate or refactor code, determine whether an adapter is needed or sufficient, or issue an architectural acceptance verdict.

Unsupported scope includes configuration/property resolution (properties, YAML, profiles, environment variables, or configuration services), other HTTP clients (`RestClient`, `WebClient`, `RestTemplate`, Spring HTTP Service Clients, or raw HTTP libraries), messaging, databases, Gradle-specific metadata, Maven aggregator analysis, test sources, and generated sources outside the conventional main Java tree. Output is Markdown only, not HTML, JSON, or PlantUML.

## Testing

From this repository, run the complete standard-library test suite:

```sh
python3 -m unittest discover
```

Tests cover extraction, mappings, report rendering, CLI errors, and end-to-end acceptance examples, including unchanged source files, excluded source trees, unresolved placeholders, and byte-identical repeated reports.
