# Iteration 006: Explain an alternative for observed Feign failure handling

## Outcome

A reader whose code catches `feign.FeignException` around a direct Feign call
can understand what ArchR observed and how an adapter could separate that
technical failure from application decisions. The explanation is grounded in
source evidence rather than a hypothetical failure-handling example.

Use deterministic source rules. Do not use AI review, execute Java, or modify
the analyzed module. This document plans the slice; it does not implement it.

## Agreed scope

- Focus on integration-specific failure handling, not response interpretation.
- Recognize `feign.FeignException`, not a growing catalog of client exceptions.
- Explain the alternative in prose; do not generate a rewrite or prescribe an
  application-specific failure outcome.

The following conservative syntax and presentation boundaries are proposed
implementation defaults to keep this iteration small.

## Detection rule

Starting from an existing resolved direct call to a recognized Feign client,
record an observation only when:

1. The invocation is in the body of a plain `try` statement in its caller method.
2. That statement has a single-type catch parameter resolved explicitly to
   `feign.FeignException`: either fully qualified or via an explicit import.
3. The call and handler can be associated without crossing a nested try,
   lambda, anonymous class, or local class boundary.

Use token structure and existing invocation offsets, not text searches for
`catch` or exception names. Exclude comments and string contents. Do not match
an unrelated or shadowing application type named `FeignException`; uncertain
type identity yields no observation. No wildcard-import inference is added.

The observation establishes only that source contains this call inside a try
with this catch. It does not prove the call throws, the catch executes, the
handler implements a business policy, or an adapter is absent or required.
Do not label the observed caller as business code based on its name.

Exclude multi-catch, try-with-resources, subclass catches, generic exception
catches, indirect calls through helpers, and upstream exception propagation.
Calls in catch or finally blocks do not belong to the preceding try body.
For nested try structures, skip the affected call in this first version rather
than inferring which handler would receive its exception.

## Report behavior

In the affected caller's existing **Handling integration-specific failures**
guidance, replace the hypothetical failure example with:

- An observed statement naming the actual caller, Feign operation, and caught
  exception type, with relative path and line citations for the call and catch.
- A general explanation tied to that observation: this method names a
  client-library exception; an adapter could catch it at the integration
  boundary and expose a failure meaningful to the application. Application
  code would decide how to respond without depending on Feign exception types.
- A qualification that the application contract determines the appropriate
  outcome, and that the caller may already serve as that adapter. Review its
  responsibilities before adding another layer.

For example, with fixture names only:

> `OrderService.placeOrder` calls `ProductClient.getProduct` inside a try with
> a `feign.FeignException` catch. [Call and catch source citations.]
> Consider whether this method is the right boundary for Feign-specific
> failures. An adapter could translate the exception into an application-level
> failure, leaving its caller to choose the response. Select that failure from
> the application's needs; this catch alone does not establish what it should
> mean. If this method already provides that boundary, another wrapper may
> add no value.

Do not infer HTTP status handling, retry behavior, fallback behavior, or a
domain meaning such as “product unavailable” from the caught type. Full source
excerpts and before-and-after code are deferred.

Correct the existing blanket wording that ArchR has not established any review
condition: distinguish this observed catch structure from the remaining
conditional checks. Other conditions retain their existing guidance.

If the rule does not match, retain conditional failure guidance; do not claim
that failure handling is absent. Keep missing-caller behavior unchanged.
Deduplicate repeated upstream paths to the same observation, but retain
distinct call/catch sites and associate each with the correct integration.

Preserve report section order, brief cards, caller statuses, diagram meaning,
CLI behavior, coverage counts, and default versus detailed-mode behavior.
Both report modes include the same new guidance.

## Implementation plan

1. Add a small immutable failure-handling observation containing caller and
   integration identity plus call/catch source locations. Use the source index's
   retained text and invocation offsets; retain method bounds if necessary.
2. Implement a bounded token-based detector using existing resolved Feign calls
   and conservative type identification. Keep detection separate from rendering
   and do not expand call resolution or traversal.
3. Pass observations to guidance rendering and render the observed explanation
   only for matching callers and integrations. Update the introductory wording.
4. Add focused acceptance and false-positive tests, update the example report
   using a fixture with an actual matching catch, and document the rule boundary.

## Acceptance and verification

- An explicitly imported `FeignException` caught around a resolved direct Feign
  call produces the observation, correct citations, and alternative explanation.
- A fully qualified `feign.FeignException` catch produces the same result.
- A catch around a different call, a call outside the try, comments, string
  literals, and an unrelated same-named exception produce no observation.
- Unsupported nested, multi-catch, resource, subclass, broad-exception and
  indirect-call cases do not acquire unsupported claims.
- Repeated upstream routes do not repeat the observation; distinct calls and
  handlers remain attributable to the correct finding.
- Guidance does not invent handler behavior or application outcomes, assert
  that an adapter is required, or present an observed catch as hypothetical.
- No-match and no-caller reports preserve conditional and scoped wording.
- Existing analysis, diagrams, coverage, error behavior, input immutability,
  and deterministic rendering remain covered by regression tests. Guidance is
  identical in default and detailed modes.

Run from `arch-r/`: `python3 -m unittest discover`,
`python3 -m compileall -q archr tests`, and `git diff --check`.

## Deferred

Other clients or exception types; interpreting catch bodies, status checks or
retry policies; response mapping; runtime reachability; automated architectural
verdicts; source excerpts; generated refactorings; new flags or output formats.
