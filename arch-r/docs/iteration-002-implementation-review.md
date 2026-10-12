# Iteration 002: iteration 001 implementation review

Scope: the first task in the iteration 002 plan only. This review identifies
extension points; it does not implement caller analysis or change task status.
Reviewed both iteration seeds, the executable, all `archr/` source modules,
and all five test modules (plus package initializers).

## Existing pipeline and contracts to preserve

| Location | Current responsibility | Preservation constraint |
| --- | --- | --- |
| `arch-r`, `archr/cli.py:main` | Parse `analyze <spring_module_path>`, load module, discover clients, render, write | Keep the command, relative/absolute paths, and lack of Java/Maven dependencies. No new flags or configuration files. |
| `archr/module.py:load_module` | Resolve the path and validate readable module and `src/main/java` directories | Keep this single-module boundary and concise `AnalysisError` handling. |
| `archr/module.py:_project_name`, `Module.report_filename` | Read only the project's own artifact ID (including Maven namespaces), fall back to directory name, sanitize filename | Preserve identity, fallback behavior, and readable original name in report. |
| `archr/discovery.py:discover_clients` | Recursively read UTF-8 `.java` files in stable module-relative path order | Preserve directory/readability checks, exclusion of symlink files and child directories, error propagation, and read-only access. Do not scan resources, tests, other modules, or generated trees outside the boundary. |
| `archr/discovery.py:extract_clients` | Recognize Spring Feign interfaces, attributes, annotation evidence and interface body offsets | Preserve aliases, explicit/qualified/wildcard annotation imports, conflicting-import protection, and unevaluated expressions. |
| `archr/discovery.py:extract_operations` | Extract directly declared mapped methods, combined interface/method mappings and evidence | Keep existing operations and unspecified/unresolved values; do not invent HTTP methods or paths. |
| `archr/report.py:render_report` | Pure deterministic Markdown and one Mermaid C4-style diagram | Retain one finding per client, operation details, escaped source text, and stable ordering/newline. Extend rather than replace dependency discovery. |
| `archr/report.py:_destination` | Classify literal, placeholder, missing and expression destinations | Keep destination confidence separate from forthcoming usage certainty. No configuration evaluation. |
| `archr/cli.py:write_report` | Write temporary UTF-8 report in caller's working directory and atomically replace destination | Preserve report location/name, cleanup, and existing successful report on analysis/write failure. Finish analysis before writing. |

The source walker currently lives inside `discover_clients`. Future indexing
should reuse or extract that read-only, sorted source-loading boundary rather
than introduce a second walker with different permissions or symlink behavior.
The current implementation does not compile, execute, or modify Java sources.

## Extension points for subsequent tasks

1. **Source index:** `Token` and `tokenize` already preserve offsets and line
   numbers while removing comments and retaining string literals as single
   tokens. Balanced-delimiter and annotation helpers can support a conservative
   index, but are private discovery helpers today; shared use should be made
   explicit. Add package-qualified type identities, imports, fields, all method
   declarations (including unmapped Feign methods), parameter counts, bodies,
   invocations and citations. Keep class ownership so nested/local declarations
   and string contents cannot become calls accidentally.
2. **Method resolution:** `Operation.method_name` describes HTTP detail, not a
   method identity: it lacks argument count, declaration evidence and overload
   distinctions. Do not use mapped operations as the entire call-resolution
   index. Resolve an invocation through its explicitly declared field type and
   uniquely matched method name/argument count. Imports, fields and constructor
   assignments alone remain non-usage. Preserve unresolved evidence instead of
   guessing overloads or connecting an unrelated intermediary method.
3. **Interfaces:** index ordinary direct `implements` declarations separately
   from observed invocations. A unique concrete local implementation is a
   possible connection, not confirmed wiring. Retain interface/implementation
   method and declaration evidence, list multiple candidates without selecting
   one, and describe missing implementations only within the boundary. Feign
   remains terminal; it needs no local implementation.
4. **Traversal:** introduce a separate backward method-level traversal over
   resolved links. Pass one named depth setting, default two, into traversal;
   do not distribute literal depth checks across discovery/report code.
   Interface resolution and outbound HTTP consume no call steps. Track method
   identities for cycles, retain distinct call sites, propagate possible
   certainty, and record depth/cycle cutoff reasons explicitly.
5. **Orchestration and rendering:** connect indexing/resolution/traversal in
   `main` before `render_report` and before atomic output. Supply usage results
   explicitly to the renderer rather than have rendering read source or infer
   relationships from class names. Keep destination classification independent.
   Add per-finding explanation, evidence/uncertainty and conditional guidance;
   centralize the plain-language adapter/port definitions. No caller found is
   not proof of an unused client and warrants no specific placement advice.
6. **Diagram/stability:** existing `feign_N` and `external_N` identifiers follow
   sorted findings. Add deterministic shared class identities and deduplicated
   relationship edges, while retaining all invocation evidence in text. Label
   observed and possible relationships distinctly; omit established ambiguous
   routes and hypothetical adapters. Reuse Markdown/Mermaid escaping for new
   labels and citations. Keep methods and source locations out of nodes.
7. **Limitations/docs:** replace the obsolete caller disclaimer in the report
   and update `README.md` once caller analysis exists, not during this review.
   State supported field-call forms, the applied depth, source-only uncertainty
   and unresolved relevant syntax without claiming exhaustive caller discovery.

## Regression coverage and known iteration transition

- `tests/test_cli.py`: namespaced/project-only artifact identity, fallback,
  filename sanitation, relative/absolute paths, invalid/unreadable input, usage
  errors and help.
- `tests/test_discovery.py`: annotation aliases, line/body-offset evidence,
  comments/string noise, annotation type resolution, unevaluated expressions,
  sorted Java-only recursion, excluded source trees, symlinks, unreadable
  sources/directories, and invalid encoding.
- `tests/test_operations.py`: all supported mappings, arrays and unspecified
  values, interface prefixes/HTTP conditions and evidence, qualified/conflicting
  annotations, method ownership, nested types and default method bodies.
- `tests/test_report.py`: destination handling, unknown names/operations,
  deterministic ordering (including reversed input), one diagram, final
  newline, and Markdown/Mermaid injection resistance.
- `tests/test_acceptance.py`: executable behavior from another working
  directory, destination non-resolution, dependency counts, excluded/unchanged
  source trees, byte-identical replacement, preservation of an existing report
  on failure, and temporary-file cleanup.

Some current assertions intentionally describe iteration 001 and will need
revision in the later coverage task: `test_zero_findings_and_limitations` and
`test_literal_destination_evidence_and_diagram` assert the old “did not inspect
callers” wording. Diagram tests assert existing module-to-Feign edges and exact
node/line counts for fixtures without callers; new caller diagrams require
additional coverage, not inferred class-level routes. Existing tests do not
exercise typed fields, method-level usage, interface wiring ambiguity, traversal
boundaries/cycles or adapter guidance. No test files were changed for this review.

## Baseline verification

Ran `python3 -B -m unittest discover` from the repository root: **45 tests
passed**. `-B` avoids writing bytecode in this process. Acceptance tests invoke
the existing executable against temporary Java fixtures; they do not compile
or execute the analyzed Java. No production behavior changed in this task.

## Validator finding: Markdown-escaped module paths

Recorded as a subtask of the first review task in
`factory/runs/arch-r-002/plan.md`; task and subtask remain unchecked.

- **Finding:** `tests/test_acceptance.py:63`, medium severity. A raw temporary
  module path may contain underscores, but `report.py:_markdown` deliberately
  renders them as `&#95;`. Comparing the raw path to Markdown makes the
  assertion depend on temporary-directory spelling.
- **Resolution already present in the supplied working tree:** the acceptance
  test computes `escaped_module_path` using the renderer's escaping rules and
  checks that value, rather than `str(self.module)`. Its `arch_r_tests_` prefix
  guarantees underscores are exercised. These test changes predate this work;
  no test files were edited here. Keep production escaping unchanged: emitting
  raw paths to accommodate an assertion would weaken injection protection.
- **Verification:** `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover`
  passed all **45 tests**. A second full run with `TMPDIR` set to a temporary
  directory prefixed `arch_r_validator_[path]_` also passed all **45 tests**,
  explicitly exercising underscore and bracket escaping. SHA-256 comparisons
  before and after that run confirmed all files under `tests/`, including
  existing bytecode, were unchanged.

The finding is addressed by verifying the existing escaped comparison, not by
changing tests or report behavior. Future usage citations and labels should
continue to use centralized output escaping, and assertions should distinguish
filesystem values from their rendered Markdown representation.
