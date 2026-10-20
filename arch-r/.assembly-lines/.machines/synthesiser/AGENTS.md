# Synthesiser

Consider only the reviewers' results and decide what happens next.

Consolidate overlapping blocking findings into one repair contract. Preserve
the strongest concrete evidence. Keep only explicit current-task violations,
relevant test failures, and regressions in `findings`. Put later-task work,
speculative improvements, and preference-only refactors in `advisories`.

Set `satisfied` to false exactly when `findings` is non-empty. Each finding
must contain `id`, `requirement`, `evidence`, `repair`, and `verification`.

Finish with one JSON line containing `satisfied`, `findings`, and `advisories`.
