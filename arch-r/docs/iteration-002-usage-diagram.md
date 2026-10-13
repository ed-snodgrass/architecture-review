# Iteration 002: usage diagram verification

The first unfinished plan task is the Mermaid C4-style diagram extension.
The supplied working tree already implements it in `archr/report.py`, with
package-qualified Feign declaration identity supplied by `archr/discovery.py`.
No additional production change was necessary in this run.

The diagram shares class nodes and deduplicates class relationships while
retaining invocation evidence in the findings. Calling code, intermediaries,
and Feign integration points appear inside the module boundary; external
systems appear outside it. Observed calls and possible interface wiring have
distinct labels. Ambiguous interface routes and suggested adapters are not
shown as established components or connections. Methods and citations remain
in supporting text.

Repeated Feign interface names use package-qualified labels, including clients
with no supported callers and the declaration-only renderer. Unique interface
names retain short labels.

## Verification

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`
passed all 196 supplied tests. `tests/test_usage_diagram.py` now includes durable
regressions for same-named clients in different packages, distinct observed
routes, an uncalled client, no-call inventories, declaration-only rendering,
and deterministic output. This addresses the coverage gap recorded in the
plan's earlier verification note. The diagram tests also verify that analyzed
Java sources remain unchanged; no Java compilation or execution is involved.

No test files or plan checkboxes were changed in this run. Existing working-tree
changes were preserved. No test revision is required for this task.
