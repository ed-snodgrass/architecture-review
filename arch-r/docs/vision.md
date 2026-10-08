# Vision

**ArchR** helps systems engineers who accept contractor software see what a module is really connected to. It explains the external dependencies in plain language and draws C4 diagrams showing where an adapter belongs, so they can challenge the contractor before accepting the delivery.

## Decision rules

When a choice isn't obvious, apply these in order:

1. **Clarity over precision.** The reader is not a software engineer. If plain language and technical accuracy pull apart, favor what the reader can understand and keep the precise detail in the supporting evidence.
2. **Evidence over inference.** Every finding points to the code that supports it. If it can't be tied to the code, don't assert it.
3. **Flag, don't assert, when unsure.** Say what was seen, what is unclear, and how confident the finding is. Never present a guess as a fact.
4. **Fewer, clearer findings.** Prioritize dependencies that cross an architectural boundary, such as reaching directly into a database instead of going through a service. Leave out incidental ones.
5. **Explain first, then suggest.** Describe what is there before saying where an adapter might fit. The engineer decides what to do with it.
6. **Diagrams show connections, not code.** A diagram should make sense at a glance. If it needs explaining, simplify it.

## Non-goals

- Generating or recommending tests (for now)
- Writing or refactoring code
- Issuing a pass/fail verdict on acceptance
- Analyzing anything beyond the targeted module or service
