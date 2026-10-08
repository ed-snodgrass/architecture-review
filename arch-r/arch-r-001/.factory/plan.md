# Iteration 001 plan: Feign outbound HTTP dependencies

Seed: `/workspaces/architecture-review/arch-r/iterations/001-feign-outbound-http.md`

## Approach

Build ArchR as a small Python 3 command-line application using the standard library, with an executable `arch-r` entry point and automated `unittest` tests. Analyze Java source statically; never compile, run, or modify the analyzed module. Keep report ordering and content deterministic.

## Tasks

- [x] **Scaffold application and CLI validation** — Create the package, executable `arch-r analyze <spring-module-path>`, and test harness. Validate that the module and conventional `src/main/java` directory exist and are readable; reject missing, unreadable, or non-directory input concisely with a nonzero exit and no report. Support relative and absolute paths. Read the project's own Maven artifactId (not its parent's) with directory-name fallback, and sanitize report filenames as specified. Test metadata, path handling, filename sanitization, and invalid input.
- [x] **Extract Feign clients and source evidence** — Recursively scan only Java files under `src/main/java` in stable order. Recognize Spring OpenFeign annotations on interfaces, including multiline annotations, `name`, `value`, and positional alias syntax. Capture literal URLs, unresolved placeholders, and missing destinations without guessing. Preserve module-relative source paths and annotation line numbers; avoid matching comments, strings, unrelated annotations, and non-interface declarations. Test extraction and boundaries.
- [x] **Extract mapped HTTP operations** — Find operations belonging to each discovered interface using `RequestMapping`, `GetMapping`, `PostMapping`, `PutMapping`, `PatchMapping`, and `DeleteMapping`. Handle multiline annotations, path/value aliases, mapping arrays, and explicit RequestMapping methods. Keep exact source evidence and honestly represent unspecified methods or paths. Test multiple clients, interface-level mappings, and method ownership.
- [x] **Generate deterministic standalone Markdown reports** — Include module name/path, dependency count, a plain-language finding per client, system name, destination, confidence and reason, operations, and readable `relative/source/path.java:line` evidence. Literal URLs have high confidence; placeholders have lower confidence and are explicitly destination unresolved; absent URLs are not invented. Include one Mermaid C4-style diagram with module, Feign integration points, external systems, and architectural connections only. Escape report and diagram content safely. Explain zero findings without claiming no other outbound calls, and include the required callers/port/adapter limitation. Test report content, escaping, and stable ordering.
- [x] **Wire report writing and verify acceptance examples** — Connect discovery and rendering to the CLI; write or replace `arch-r-report-<safe-module-name>.md` in the caller's current directory only after successful analysis. Handle analysis and output errors concisely. Add end-to-end tests for literal destinations, unresolved placeholders, aliases, multiple clients, no clients, invalid input, and byte-identical repeated analysis. Verify the analyzed source stays unchanged and test/config/generated sources are excluded. Run the complete test suite.
- [x] **Document usage and final verification** — Add a concise README covering Python requirements, command examples, report location, testing, confidence semantics, static-analysis limitations, and unsupported scope. Run all tests and demonstrate the CLI against temporary representative modules; confirm the implementation satisfies the seed without adding configuration resolution or architectural verdicts.

## Verification notes

- Wire report writing and verify acceptance examples: connected source discovery and Markdown rendering to the executable CLI, with atomic replacement in the caller's directory and concise analysis/output errors. Added end-to-end coverage for literal destinations and evidence, placeholders without configuration resolution, aliases, multiple/no clients, excluded sources, unchanged module files, repeatable report bytes, unreadable/invalid sources, and output failures. Existing invalid-input tests also pass. `python3 -m unittest discover` passes all 45 tests.

- Extract mapped HTTP operations: implemented source-only mapping discovery with method/path arrays, interface-level prefixes, explicit HTTP methods, unresolved expressions, and annotation evidence. Nested declarations and method bodies are excluded. `python3 -m unittest discover` passes all 29 tests.

## Completion rule

Mark each task complete only after its implementation and associated checks pass. All tasks must be checked before reporting iteration completion.
