# Observed Feign failure guidance

ArchR can cite a direct resolved Feign invocation inside a plain `try` body
with a single-type `feign.FeignException` catch. It uses retained source tokens
and invocation offsets, not a text search. The catch type must be fully
qualified or resolved through an explicit `import feign.FeignException;`.
Comments and string contents do not count as syntax. Shadowed or uncertain type
identities produce no observation; wildcard imports are not inferred.

This small rule excludes:

- Multi-catch, try-with-resources, subclass catches and broad exception catches.
- Calls outside the try body, including its catch and finally blocks.
- Nested try structures: affected calls are skipped rather than assigned an
  inferred exception route, including nested tries in handlers or finally.
- Associations crossing lambdas, anonymous classes or local classes.
- Indirect helper calls and catches in upstream callers. Only an existing
  resolved direct call to a recognized Feign client is considered; call
  resolution and traversal are not expanded.

The observation says only that the source places that invocation inside that
try with that catch. It does not prove the invocation throws, the catch executes,
or the handler implements business policy. Caller names do not establish
business responsibilities. ArchR does not interpret handler bodies, HTTP status
checks, retries, fallbacks or application-specific outcomes.

## Reading the guidance

The matching caller's **Handling integration-specific failures** subsection names
the caller, Feign operation and exception type and cites the call and catch
separately. It explains that an adapter could translate a client-library
exception into an application-level failure, leaving application code to choose
the response. The application contract determines the appropriate failure; the
observed method may already provide this boundary, so another layer is not
necessarily useful. No rewrite or before-and-after code is generated.

Other review conditions remain conditional. Without a match, the existing
hypothetical failure example remains: silence does not establish that handling
is absent. Without a supported caller, there is still no specific placement
recommendation or example. Repeated upstream paths do not repeat the same
observation, while distinct call/catch sites remain associated with their own
caller and integration. Default and detailed reports include identical guidance.

## Reproducible example

[Iteration 006 example report](../example-reports/006-arch-r-report-order-service.md)
is generated from the small source fixture at
[`tests/fixtures/feign-failure/order-service`](../tests/fixtures/feign-failure/order-service).
`shop.OrderService.placeOrder` calls `ProductClient.getProduct` on line 14 and
catches the explicitly imported exception on line 15. The catch rethrows it;
ArchR makes no inference about that behavior. These are source-analysis fixtures,
not a runnable Spring application; no Java compilation or execution is needed.

To reproduce, run from the repository root:

```sh
./arch-r analyze tests/fixtures/feign-failure/order-service
```

The generated `arch-r-report-order-service.md` uses an absolute module path.
The checked-in example normalizes only that header value to
`tests/fixtures/feign-failure/order-service` for portability. The example test
compares the complete report after this normalization, checks both citations,
checks matching guidance across modes and confirms fixture input immutability.

Focused tests live in `tests/test_failure_handling_detection.py`,
`tests/test_failure_handling_observations.py`,
`tests/test_observed_failure_guidance.py` and
`tests/test_iteration_006_example.py`. They cover supported spellings, excluded
syntax and type identities, precise offsets and lines, deduplication, attribution,
conditional/no-caller behavior, and the absence of invented failure outcomes.
