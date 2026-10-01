---
name: implement-fast
description: Implement the student's current homework iteration yourself, without a walkthrough. Use when the student wants the iteration built quickly.
---
Implement the current homework iteration.

Work from the factory's folder: `tetris/.factory` through iteration 003, and `factory/` from 004 on (fetch-iteration moves it there). Paths in the repository below are from its root. The spec is in `spec/`, the student's progress in `ITERATION`, and the seeds in `tetris/seeds/`. The factory builds the game in `tetris/`: the folder around it through 003, and a target beside it from 004, holding its assembly lines and their machines in `tetris/.assembly-lines/`.

Follow this process exactly:

1. Read `ITERATION`. If it is missing or says `Done`, follow the fetch-iteration skill first. Carry on here once it has committed the adoption.
2. Read the whole spec: `spec/README.md`, `spec/FACTORY.md`, `spec/features/` and the seeds in `tetris/seeds/`.
3. If the spec is unclear, stop and ask before editing.
4. Check the working tree and avoid touching unrelated student changes.
5. If there is no factory project yet — no Gherkin runner set up in this folder — follow the set-up-factory skill first. For later iterations, keep using what the student already chose. `AGENTS.md` says how to run the suite.
6. Implement only this iteration, driven by the suite, leaving out the `@real-agent` examples. Do not start any later iteration. Until the suite passes: take the first example that fails or has undefined steps, define its missing steps (true to their words, reusing what exists), then make the smallest factory change that makes it pass.
7. From the repository root, verify the public CLI through the exact `bin/factory` entry point before presenting any CLI command as runnable. Run the README's command when it is safe. If a full run would contact a real agent, do not run it; use a non-destructive invocation that reaches the language CLI and proves launcher resolution and argument parsing, and explicitly say in the final summary that the real-agent command was not run. Checking the symlink, file existence or executable bits alone is not enough.
8. Change `ITERATION` from `<iteration> WIP` to `<iteration> Done`.
9. Commit the implementation, the step definitions and that change with message `Implement homework <iteration>`.

Rules:

- Do not start more than one iteration.
- Do not edit anything in `spec/`. `ITERATION` is yours to update.
- Do not commit unrelated existing changes.
- Keep the implementation scoped to the spec.
- Keep the factory minimal. It never contains an agent of its own, test double or otherwise.
- If the suite fails and you cannot fix it within the spec, stop and report the failure.
