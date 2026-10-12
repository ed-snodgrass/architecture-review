# Iteration 002: interface connections

The first unfinished plan task is ordinary non-generic interface resolution.
The plan and its completion markers remain unchanged. Traversal and reporting
are subsequent tasks, not part of this change.

## Implementation

`archr/indexing.py` records direct, non-parameterized `implements` identities,
resolved using package declarations, explicit imports, or fully qualified names.
Type declarations retain source citations and abstract, generic, and Feign
flags. Existing field/method/invocation indexing remains the source of usage
evidence; declarations alone do not create connections.

`archr/interfaces.py` provides `resolve_interface_index(SourceIndex)` and the
source-only `resolve_interfaces(Module)` entry point. The working tree already
contained the indexing extension and a draft resolver when this run began.
This run reviewed those changes and completed declaration-candidate indexing:
candidates are built once in deterministic order, independently of method
availability, and repeated implemented identities cannot duplicate a candidate.

A unique supported concrete direct implementor yields a **possible** connection,
not verified dispatch. It retains the original invocation and receiver field,
interface declaration/method, implementation declaration, and implementing
method. Implementing methods match by name and argument count only. Unrelated
methods remain separate endpoints. Resolving the interface introduces no
additional invocation or call step.

Multiple candidates produce an ambiguity diagnostic naming each candidate and
its declaration citation, without selecting a route. Missing candidates are
explicitly scoped to the module's `src/main/java` boundary. Inherited methods,
ambiguous same-arity overloads, and generic interfaces have diagnostics rather
than guessed endpoints. Abstract, indirect, and generic implementors are outside
the supported candidate set. Feign interfaces remain terminal even when a local
implementation is present. Independently observed implementation-to-Feign calls
remain available through `archr.resolution`.

## Verification

- `python3 -m unittest discover -s tests -v`: all 147 supplied tests pass.
- `python3 -m unittest tests.test_interface_connections -v`: all 16 supplied
  interface tests pass after completing candidate indexing.
- Tests cover unique/multiple/missing implementations, the four required link
  citations, type identity, method-level matching and ambiguity, inherited and
  generic exclusions, Feign termination, declarations without usage, preserved
  direct Feign calls, repeated call-site evidence, boundary restrictions,
  read-only analysis, and deterministic repeated results.
- No test files were changed in this run. The supplied untracked interface test
  file was already present. No Java sources were compiled or executed.

The supplied tests adequately cover this task; no test revision is requested.
