---
name: implement-fast
description: Implement the student's current homework iteration yourself, without a walkthrough. Use when the student wants the iteration built quickly.
---
Implement the current homework iteration.

Open the agent at the repository root. The factory source, `spec/` and `ITERATION` live in `factory/` for every iteration. Run factory development commands from `factory/`, and the factory CLI from the repository root through `bin/factory`. Paths below are relative to `factory/` unless stated otherwise. The spec is in `spec/`, the student's progress in `ITERATION`, and the seed at `tetris/spec.md` relative to the repository root. The factory builds the game in the folder passed with `--target`, such as `tetris/tetris1/` or `tetris/tetris2/` (from the repository root). The current feature specs define target behavior and where plans and other state live.

Follow this process exactly:

1. Read `ITERATION`. If it is missing or says `Done`, follow the fetch-iteration skill first. Carry on here once it has committed the adoption.
2. Read the whole spec: `spec/README.md`, `spec/FACTORY.md`, `spec/features/` and the seed at `tetris/spec.md` relative to the repository root.
3. If the spec is unclear, stop and ask before editing.
4. Check the working tree and avoid touching unrelated student changes.
5. If there is no factory project yet — no Gherkin runner set up in this folder — follow the set-up-factory skill first. For later iterations, keep using what the student already chose. The repository-root `AGENTS.md` says how to run the suite.
6. Implement only this iteration, driven by the suite, leaving out the `@real-agent` examples. Do not start any later iteration. Until the suite passes: take the first example that fails or has undefined steps, define its missing steps (true to their words, reusing what exists), then make the smallest factory change that makes it pass.
7. Look for the exact heading `## Once your suite passes` in `spec/README.md`. If it is present, offer to work through that section with the student before marking the iteration Done, including creating an HTML comparison report when the README suggests one. Wait for their answer. If they accept, work through the section with them; if they decline, continue to the completion step. Follow the course's tasks rather than inventing them. If the section is absent, continue directly. This heading is a shared contract with the tutorial repository; course content stays in the README.
8. Change `ITERATION` from `<iteration> WIP` to `<iteration> Done`.
9. Commit the implementation, the step definitions and that change with message `Implement homework <iteration>`.
10. Encourage the student to take a look around their factory's codebase. Offer to answer any questions about it, and ask whether there is any refactoring they would like to do.

Rules:

- Do not start more than one iteration.
- Do not edit anything in `spec/`. `ITERATION` is yours to update.
- Do not commit unrelated existing changes.
- Keep the implementation scoped to the spec.
- Keep the factory minimal. It never contains an agent of its own, test double or otherwise.
- If the suite fails and you cannot fix it within the spec, stop and report the failure.
