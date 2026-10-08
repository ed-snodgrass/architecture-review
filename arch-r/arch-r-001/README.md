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

The standalone Markdown report includes the module name and path, a dependency count, one plain-language finding per Feign interface, source-path-and-line evidence, mapped HTTP operations, and one Mermaid C4-style architectural diagram. A Markdown viewer with Mermaid C4 support can render the diagram; its source is also readable as text.

- **High confidence:** the client declaration and a literal destination URL are visible in source.
- **Lower confidence / destination unresolved:** the URL contains a `${...}` placeholder, is an unevaluated expression, or is absent. ArchR shows what is declared and does not guess a destination or resolve configuration.
- **No findings:** no supported statically declared Feign dependencies were found. This does not mean the module has no outbound calls by other means.

## Scope and limitations

ArchR recursively scans Java files only under `src/main/java`. It recognizes OpenFeign interface declarations and Spring `RequestMapping`, `GetMapping`, `PostMapping`, `PutMapping`, `PatchMapping`, and `DeleteMapping` operations, including interface-level mappings. This is source-level analysis, not a Java compiler or a runtime call trace; inherited operations and runtime behavior are outside its scope.

ArchR does not inspect callers or determine whether a separate domain-facing port or adapter is needed. A Feign integration point is not assumed to be a sufficient architectural adapter. It gives no refactoring recommendation or architectural acceptance verdict.

Unsupported scope includes configuration/property resolution (properties, YAML, profiles, environment variables, or configuration services), other HTTP clients (`RestClient`, `WebClient`, `RestTemplate`, Spring HTTP Service Clients, or raw HTTP libraries), messaging, databases, Gradle-specific metadata, Maven aggregator analysis, test sources, and generated sources outside the conventional main Java tree. Output is Markdown only, not HTML, JSON, or PlantUML.

## Testing

From this repository, run the complete standard-library test suite:

```sh
python3 -m unittest discover
```

Tests cover extraction, mappings, report rendering, CLI errors, and end-to-end acceptance examples, including unchanged source files, excluded source trees, unresolved placeholders, and byte-identical repeated reports.
