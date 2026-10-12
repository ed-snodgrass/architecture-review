# Iteration 002 source inventory

`archr.indexing.index_module(Module)` returns an immutable `SourceIndex`.
Types have package-qualified identities, declaration citations, explicitly
typed fields, and method declarations (including constructors, unmapped
interface methods and overloads). Each method owns its invocation inventory;
invocations retain receiver spelling, name, argument count and call citation.
Citations are 1-based lines and module-relative POSIX source paths.

Type names use package declarations, explicit imports and fully qualified
names. Ordinary field declarations, including final constructor-injected
fields, are recorded independently of usage. Comments, strings and text blocks
are lexer tokens rather than declaration/call text. Nested type bodies are not
attributed to enclosing methods. Generic/array field types are not resolved by
this slice. This is an inventory, not method selection or runtime resolution:
receiver names are not yet connected to their fields and target methods.
Same-class helpers are not followed. Interface wiring, traversal, diagnostics,
CLI orchestration and report changes remain subsequent tasks.

`discovery.read_java_sources` now supplies the existing sorted, UTF-8,
Java-only, symlink-excluding and permission-checked source boundary to both
Feign discovery and indexing. Neither consumer compiles, executes or modifies
Java sources. Existing CLI/report behavior remains unchanged.

## Verification

`PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover`: 54 of 55 tests
passed, including all 45 iteration 001 regressions and nine indexing tests.
The remaining indexing assertion in
`test_comments_strings_and_text_blocks_do_not_create_declarations_or_calls`
expects line 14 for `client.real()`, but the fixture places that call on line
13 (the closing text-block delimiter is line 10, followed by two comment
lines). The index reports line 13. No test files were changed and no plan
checkbox was updated.

## Validator follow-up

All three findings are recorded as pending subtasks under the source-indexing
task in `factory/runs/arch-r-002/plan.md`; no task was marked done.

- Class literals such as `String.class` no longer trigger the local-type
  declaration skip. A declaration requires a following identifier and must not
  follow a dot, so supported calls after the literal retain their evidence.
- Anonymous constructor bodies are skipped as separate ownership boundaries.
  Their method and initializer calls are not attributed to the enclosing
  method. Constructor-argument calls and calls after the body remain indexed,
  including nested anonymous constructions. Anonymous methods are not separately
  inventoried in this slice.
- The line-14 assertion remains an acknowledged test defect: the correct
  citation is line 13. No test files were modified to conceal the discrepancy.

After these changes, `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover`
again ran 55 tests: 54 passed, with only the same incorrect line-14 expectation
failing. An additional in-memory assertion check passed for class literals,
anonymous methods and initializers, constructor arguments, local classes,
nested anonymous bodies, and trailing calls, including exact source lines.
The check did not create or modify test files or execute Java code.

## Source-citation validator follow-up verification

The first unchecked subtask in the supplied plan concerns the historical
line-14 expectation in `tests/test_indexing.py:176`. Inspection of the fixture
confirms that `client.real()` is on Java source line 13: the text block closes
on line 10, and lines 11–12 are comments. Preserve the indexer's 1-based line
13 citation; changing it to 14 would introduce an off-by-one error.

The supplied test now also expects line 13. No production correction or test
edit is needed for this subtask. Fresh verification with
`PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_indexing.SourceIndexTests.test_comments_strings_and_text_blocks_do_not_create_declarations_or_calls -v`
passes the targeted test. Running
`PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -v` passes all 59
tests. Only this documentation was changed; the plan remains unmodified and
the subtask remains unchecked as requested.

## Previous task verification

The current supplied tests already expect line 13 for `client.real()`; the
historical assertion defect above no longer occurs. No test files were edited
in this run. The latest validator findings list is empty, so there are no new
findings to record as subtasks; existing pending subtasks and task checkboxes
remain unchanged.

Field declarations now retain their explicitly declared types even when an
initializer contains an anonymous-class body, including subsequent fields in
the same declaration. Those bodies do not become enclosing class methods.
Method annotations with named arguments are removed before classifying a
member, so annotation assignments do not hide ordinary method declarations.

Verification: `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -v`
passes all 59 current tests (45 iteration 001 regressions and 14 source-indexing
tests), including the class-literal and nested anonymous-body validator cases. An additional in-memory check confirms anonymous field
initializer ownership, multiple typed fields, following annotated methods,
exact invocation lines, and deterministic repeated extraction. It creates no
test files and executes no Java code. The source-indexing task remains unmarked.
