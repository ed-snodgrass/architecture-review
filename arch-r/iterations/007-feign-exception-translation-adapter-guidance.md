# Iteration 007: Recommend an adapter for observed Feign exception translation

## Outcome

A reader whose code catches a concrete nested `feign.FeignException` around a
direct Feign call and directly throws an application-owned exception can see
that ArchR observed an existing technical-to-application failure translation.
The affected OpenFeign finding recommends placing that translation behind an
adapter when the integration boundary is crossed, without creating a second
finding or claiming that the application chose the wrong failure outcome.

Use deterministic source rules. Do not use AI review, execute Java, modify the
analyzed module, or infer runtime exception behavior.

## Detection rule

Starting from an existing resolved direct call to a recognized Feign client,
record a translation observation only when all of the following hold:

1. The invocation is in the body of a plain `try` statement in its caller
   method.
2. That statement has a single-type catch parameter explicitly resolved to a
   concrete nested type of `feign.FeignException`, such as
   `FeignException.NotFound`.
3. The catch body directly contains exactly one `throw new` statement whose
   constructed exception type is declared in the analyzed source and is not in
   the `feign` package.
4. The call, catch, and throw can be associated without crossing a nested try,
   lambda, anonymous class, local class, or other unsupported scope boundary.

Recognize nested exception types through these explicit forms:

- `FeignException.NotFound`, when `feign.FeignException` is explicitly
  imported and unshadowed.
- `feign.FeignException.NotFound`, when `feign` and `FeignException` are
  unshadowed.
- `NotFound`, when `feign.FeignException.NotFound` is explicitly imported and
  unshadowed.

Apply the same rule to every explicitly named one-level nested exception type;
do not maintain a catalog of known Feign subtype names. Treat the explicit
nested-type syntax as the available source evidence. Do not infer nested types
from wildcard imports.

An exception is **application-owned** for this slice exactly when its resolved
declaration is present in the analyzed source and its qualified name is outside
the `feign` package. Do not infer ownership, layer, or domain meaning from a
class name such as `UnknownProductException` or from package naming
conventions.

The observation establishes that source translates a specifically named Feign
exception into an application-owned exception at this call site. It does not
establish that the Feign call throws that exception at runtime, that the new
exception expresses the correct application outcome, or that an additional
wrapper class is necessarily valuable.

## Report behavior

Enrich the existing OpenFeign finding and its **Handling integration-specific
failures** guidance. Do not add a new finding or change finding counts.

For each matching observation, report:

- The actual caller and Feign operation.
- The caught concrete Feign exception type.
- The application-owned exception constructed by the catch.
- Relative path and line citations for the call, catch, and `throw new`.
- A positive statement that the method already prevents this specific
  Feign exception from escaping unchanged.
- An adapter recommendation because the observed translation crosses the
  integration boundary.

Use language equivalent to:

> `OrderService.resolveItem` catches `FeignException.NotFound` from
> `ProductServiceClient.getProduct` and translates it to the application-owned
> `UnknownProductException`. This already prevents that Feign-specific failure
> from escaping this method. Consider whether `OrderService` is intended to be
> the integration boundary. If the application uses ports and adapters, the
> same translation could live behind a `ProductCatalog` port; if this method
> already owns that boundary, another wrapper may add no value.

Always include the adapter recommendation for a matching translation. Keep it
as architectural guidance rather than a declaration that another adapter is
required. Do not invent the port name `ProductCatalog` from arbitrary source;
use general adapter/port wording unless an existing application-owned port is
deterministically resolved at the call site.

Do not reproduce the whole method or generate replacement code in this slice.
Use the three source citations as evidence. Preserve the existing conditional
guidance when no translation observation matches.

## Conservative exclusions

Do not report this translation observation for:

- The base `FeignException`, broad exceptions, multi-catch, wildcard-import
  inference, or unrelated and shadowing same-named types.
- A thrown type not declared in analyzed source, or a type in `feign.*`.
- Returning a value, logging, retrying, wrapping without `throw new`, rethrowing
  the caught exception, or throwing a pre-existing variable.
- Zero or multiple `throw new` statements, conditional throws, ambiguous throw
  paths, or catch bodies with additional control flow.
- Indirect Feign calls through helpers, upstream exception propagation,
  try-with-resources, nested tries, calls in catch or finally blocks, lambdas,
  anonymous classes, or local classes.

These exclusions keep the slice from interpreting handler semantics or control
flow. Unsupported code retains the existing conditional guidance.

## Acceptance and verification

- Every explicitly named concrete nested `FeignException` form above is
  recognized when it catches a resolved direct Feign call and directly throws
  one source-declared, non-Feign exception.
- `FeignException.NotFound` translated to a source-declared
  `UnknownProductException` produces one observation with correct call, catch,
  throw, integration, caller, and exception identities.
- The existing OpenFeign finding is enriched without changing finding counts,
  section order, brief cards, diagram meaning, coverage totals, or CLI behavior.
- The report states that translation already occurs and always includes the
  qualified adapter recommendation, without claiming that another wrapper is
  mandatory or inventing a port name.
- Distinct call/catch/throw sites remain distinct; repeated upstream paths do
  not duplicate an observation.
- Every conservative exclusion above has focused false-positive coverage.
- No-match and unsupported cases preserve iteration 006 guidance unchanged.
- Default and detailed report modes contain identical translation guidance.
- The published iteration example is rendered from a fixture containing a
  real matching nested Feign catch and application-owned exception declaration.
- Input source remains unchanged and report output remains deterministic.

Run from `arch-r/`: `python3 -m unittest discover`,
`python3 -m compileall -q archr tests`, and `git diff --check`.

## Deferred

Interpreting catch-body business semantics; deciding whether the translated
exception is the correct application outcome; response/status mappings;
retries or fallbacks; generated refactorings; full source excerpts; indirect
calls; complex control flow; framework exception mappers; and recommendations
for integration libraries other than OpenFeign.
