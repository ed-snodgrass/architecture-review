# Iteration 002: method-level call resolution

The first unfinished plan task is implemented in the supplied working tree in
`archr/resolution.py`, with invocation support in `archr/indexing.py`. This
verification does not mark the task or its subtasks complete.

## Behavior

- Resolves ordinary `field.method(...)` and `this.field.method(...)` invocations
  using the declared field type and exact method name and argument count.
- Retains caller and target method identities, field declarations, invocation
  locations, and overload candidates as module-relative source evidence.
- Reports ambiguous overloads, missing types or methods, unsupported receivers,
  and explicit generic invocation syntax rather than guessing connections.
- Keeps intermediary methods distinct and does not expand same-class helpers.
- Tracks parameter and local shadowing, annotated and comma-separated locals,
  loop variables, catch parameters, and try-with-resources lifetimes.
- Counts generic constructor arguments without confusing type-argument commas
  with invocation argument separators; ordinary comparisons remain expressions.
- Interface implementation selection and backward traversal remain later tasks.

## Verification

Ran `python3 -m unittest discover -s tests -v`: all 97 tests passed.
The supplied `tests/test_resolution.py` now includes durable coverage for
annotated/comma-separated locals, loop and catch lifetimes, generic initializer
and invocation argument counting, resource-variable lifetimes, and explicit
generic invocation diagnostics. Its generic initializer assertion now permits
the retained `Factory` invocation evidence, resolving the previously recorded
test defect without an implementation workaround.

The suite also covers source-only, bounded, read-only, repeatable resolution,
exact citations, ambiguous overloads, unrelated intermediary methods, and
iteration 001 regressions. No test files were edited in this run, and no
analyzed Java source was compiled, executed, or modified. The implementation
was already present when that verification began; that run added only this
verification record. At that point no test revision was identified.

## Validator follow-up: array parameters and enhanced-for iterable scope

The subsequent run corrected two invocation-indexing defects in
`archr/indexing.py`, recorded as unfinished subtasks under method resolution:

- Parameter names now exclude trailing array dimensions and declaration
  annotations/modifiers. A parameter such as `Client client[]` shadows the field
  for unqualified invocations, while `this.client` still refers to the field.
- Enhanced-for variable names become active at the loop body, not in the
  iterable expression. In `for (Client client : client.items())`, the iterable
  invocation uses the field unless an enclosing parameter/local shadows it.
  Body shadowing and restoration after the loop remain intact.

Verification: all 97 unchanged supplied tests pass. Thirteen in-memory
indexing/resolution cases also pass, covering pre/post-name and multidimensional
arrays, annotated dimensions, varargs, explicit `this`, annotated enhanced-for
variables, array declarators, braced/unbraced bodies, nested loops, enclosing
parameter shadowing, and deterministic resolution. No test files were edited
and no analyzed Java sources were executed or modified.

Tests need revision: the supplied suite lacks durable regression coverage for
post-name array parameter shadowing and same-named field invocations in
enhanced-for iterable expressions. Existing loop tests use `clients` as the
iterable, so they cannot detect premature shadowing of `client.items()`.
Add coverage for these cases, explicit `this`, enclosing shadowing, and field
restoration after the loop. No faulty-test workaround was introduced; the task
and both new subtasks remain unfinished.

## Current supplied-suite verification

Re-read the seed and plan and verified the existing implementation of the first
unfinished task; no additional production changes were necessary. Ran
`python3 -m unittest discover -s tests -v`: all 101 supplied tests passed.

The current `tests/test_resolution.py` now supplies the formerly missing
regressions for array/varargs parameter shadowing and enhanced-for iterable
scope, including annotated declarations, explicit `this`, nested loops,
enclosing variable shadowing, and field restoration. The earlier test-revision
finding above describes the previous suite, not the current one. No test
revision is identified for this task in the current supplied suite.

No test files or plan checkboxes were changed in this run. Interface
implementation selection, traversal, and report integration remain later tasks.

## Annotated and comma-separated local declarations: current verification

The first unchecked subtask is the validator finding about annotated locals and
subsequent comma-separated declarators. Its implementation is already present
in `archr/indexing.py`: `_local_declarations` skips declaration annotations and
`final`, records each declarator at its own name token, and `_invocations`
activates shadowing at that token. Earlier initializers retain field calls;
self-initializers and later calls use the unsupported local receiver. Explicit
`this.client` remains a field receiver.

Verified the unchanged supplied tests for annotated locals, self-initializers,
comma-separated initialized and uninitialized locals, annotated array
declarators, and restoration after block exit. All 45 method-resolution tests
pass (`python3 -m unittest tests.test_resolution -v`), and all 109 suite tests
pass (`python3 -m unittest discover -s tests`). No additional production changes
or test revisions are needed for this subtask. The existing test-file working
tree modification was preserved; no tests or plan checkboxes were edited in
this run. The subtask remains unchecked as requested.

## Catch-parameter lifetime: nested-catch validator follow-up

The first unfinished subtask concerns catch-parameter scope restoration. The
existing dedicated catch scope already ends at its body; no production change
is needed. All 114 supplied tests pass (`python3 -m unittest discover -s tests
-q`). Test files, including their pre-existing working-tree changes, were left
unchanged. No task was marked done.

Tests need revision: `tests/test_resolution.py:902-903` redeclares `client` in a
nested catch while the outer catch parameter remains in scope, which Java
forbids. Replace the inner name with a distinct name and assert that calls on
the outer `client` remain unsupported inside and after the inner catch,
including its finally block. Retain explicit `this.client` and field-restoration
assertions after the outer catch. This finding is recorded as an unchecked
subtask beneath the current catch-scope task in the plan.

An in-memory indexing probe using distinct `client` and `inner` catch names
passed: both parameter receivers remain unsupported, the outer name still
shadows the field after the inner catch and in its finally block, explicit
`this.client` remains supported, and unqualified field calls resume in the
outer finally block and after the outer catch. No Java source was compiled or
executed, and no implementation workaround was introduced for the faulty test.
The durable fixture correction was blocked in that run by the instruction not
to modify tests.

## Catch-parameter lifetime: durable test correction

Corrected `test_nested_catch_exit_restores_outer_catch_before_restoring_field`
in `tests/test_resolution.py` to use distinct outer `client` and inner `inner`
catch parameters. Exact receiver/line assertions now cover both parameters
inside the inner catch, continued outer-parameter shadowing in the inner
finally block and after the inner catch, explicit field access, and restoration
of unqualified field access in the outer finally block and afterward.

Verification: all 50 method-resolution tests and all 114 suite tests pass
(`python3 -m unittest discover -s tests -p test_resolution.py -q` and
`python3 -m unittest discover -s tests -q`). No production code or plan
checkboxes were changed; the task remains unfinished. No Java fixture was
compiled or executed.
