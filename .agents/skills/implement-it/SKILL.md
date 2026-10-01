---
name: implement-it
description: Implement the student's current homework iteration yourself, then demo it and pause. Use when the student says "implement it" or wants the iteration built for them with a walkthrough.
---
Implement the current homework iteration, then explain and demo what changed before asking whether to continue.

This is guided autopilot. Do the implementation yourself, but walk the student through the build one iteration at a time. After each iteration, show what was learned, what changed, how to try it, and what's still missing.

Open the agent at the repository root. The factory source, `spec/` and `ITERATION` live in `factory/` for every iteration. Run factory development commands from `factory/`, and the factory CLI from the repository root through `bin/factory`. Paths below are relative to `factory/` unless stated otherwise. The spec is in `spec/`, the student's progress in `ITERATION`, and the seed at `tetris/spec.md` relative to the repository root. The factory builds the game in the folder passed with `--target`, such as `tetris/tetris1/` or `tetris/tetris2/` (from the repository root). The current feature specs define target behavior and where plans and other state live.

Follow this process exactly:

1. Read `ITERATION`. If it is missing or says `Done`, follow the fetch-iteration skill first. Carry on here once it has committed the adoption.
2. Read the whole spec: `spec/README.md`, `spec/FACTORY.md`, `spec/features/` and the seed at `tetris/spec.md` relative to the repository root.
3. If the spec is unclear, stop and ask before editing.
4. Check the working tree and avoid touching unrelated student changes.
5. Check the current branch.
6. If the current branch is `main`, offer to create and switch to a dated solution branch named `solution/YYYY-MM-DD` before editing. If that branch already exists, suggest `solution/YYYY-MM-DD-2`, then `solution/YYYY-MM-DD-3`, and so on.
7. If the student says yes, create and switch to the branch. If they say no, continue on the current branch.
8. If there is no factory project yet — no Gherkin runner set up in this folder — follow the set-up-factory skill first. For later iterations, keep using what the student already chose. The repository-root `AGENTS.md` says how to run the suite.
9. Implement only this iteration, driven by the suite, leaving out the `@real-agent` examples. Do not start any later iteration. Until the suite passes, repeat:
   - Run the suite and take the first example that fails or has undefined steps.
   - If it has undefined steps, define them, true to their words, reusing the step definitions that exist. Run it: it should fail for the reason the factory change will fix.
   - Make the smallest factory change that makes it pass, without breaking the examples that passed before.
10. If the suite fails and you cannot fix it within the spec, stop and report the failure.
11. From the repository root, verify the public CLI through the exact `bin/factory` entry point before presenting any CLI command as runnable. Run the README's command when it is safe. If a full run would contact a real agent, do not run it; use a non-destructive invocation that reaches the language CLI and proves launcher resolution and argument parsing, then explicitly report that the real-agent command was not run. Checking the symlink, file existence or executable bits alone is not enough.
12. Once the suite passes, check the iteration description in `spec/README.md` for optional follow-up work before marking the iteration Done:
    - Look for the exact heading `## Once your suite passes`. If present, offer to work through that section, including creating an HTML comparison report when the README suggests one. This heading is a shared contract with the tutorial repository; course content stays in the README.
    - If the description includes a bonus round, show the student its goal and tasks, and ask whether they would like to try it. Use the README's bonus round rather than inventing one.
    - For each offer, wait for the student's answer. If they accept, work through the course's tasks with them; if they decline, skip that activity. If neither section is present, continue directly. Skipping optional work does not prevent marking the iteration Done.
13. Change `ITERATION` from `<iteration> WIP` to `<iteration> Done`.
14. Commit the implementation, the step definitions and that change with message `Implement homework <iteration>`.
15. Report back with:
    - the iteration number and title
    - the goal in plain language, from `spec/README.md` and `spec/FACTORY.md`
    - a short summary of what changed, in the factory and in the step definitions
    - the suite passing, as the student can run it
    - the public-entrypoint command used for the smoke test and its result
    - the README's example CLI commands, and the `@real-agent` examples, as things the student can try by hand with `pi`; if only a non-destructive smoke test was run, say that the real-agent command was not run
    - what's still missing, from the closing lines of `spec/README.md`
16. Encourage the student to take a look around their factory's codebase. Offer to answer any questions about it, and ask whether there is any refactoring they would like to do.
17. Stop and wait for the student's answer. Answer their questions and help with any requested refactoring before moving on.
18. Ask: "Ready for me to implement the next iteration?"
19. Stop and wait for the student's answer. If they say yes, repeat from step 1. If they say no, stop.

Rules:

- Implement one iteration per commit.
- Offer a solution branch before editing on `main`; do not create a branch without the student confirming.
- Pause after each iteration; do not automatically continue without the student confirming.
- Do not edit anything in `spec/`. `ITERATION` is yours to update.
- Do not commit unrelated existing changes.
- Keep each implementation scoped to its spec.
- Keep the factory minimal: a short loop driving the agent, with state on disk. Do not encode the plan or the seed in code.
- The factory never contains an agent of its own, test double or otherwise. Doubles live with the step definitions and are chosen from outside, the same way `pi` is.
- Avoid defensive code and production hardening unless the spec asks for it.
