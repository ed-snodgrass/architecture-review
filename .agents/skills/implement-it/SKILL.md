---
name: implement-it
description: Implement the student's current homework iteration yourself, then demo it and pause. Use when the student says "implement it" or wants the iteration built for them with a walkthrough.
---
Implement the current homework iteration, then explain and demo what changed before asking whether to continue.

This is guided autopilot. Do the implementation yourself, but walk the student through the build one iteration at a time. After each iteration, show what was learned, what changed, how to try it, and what's still missing.

Work from the factory's folder: `tetris/.factory` through iteration 003, and `factory/` from 004 on (fetch-iteration moves it there). Paths in the repository below are from its root. The spec is in `spec/`, the student's progress in `ITERATION`, and the seeds in `tetris/seeds/`. The factory builds the game in `tetris/`: the folder around it through 003, and a target beside it from 004, holding its assembly lines and their machines in `tetris/.assembly-lines/`.

Follow this process exactly:

1. Read `ITERATION`. If it is missing or says `Done`, follow the fetch-iteration skill first. Carry on here once it has committed the adoption.
2. Read the whole spec: `spec/README.md`, `spec/FACTORY.md`, `spec/features/` and the seeds in `tetris/seeds/`.
3. If the spec is unclear, stop and ask before editing.
4. Check the working tree and avoid touching unrelated student changes.
5. Check the current branch.
6. If the current branch is `main`, offer to create and switch to a dated solution branch named `solution/YYYY-MM-DD` before editing. If that branch already exists, suggest `solution/YYYY-MM-DD-2`, then `solution/YYYY-MM-DD-3`, and so on.
7. If the student says yes, create and switch to the branch. If they say no, continue on the current branch.
8. If there is no factory project yet — no Gherkin runner set up in this folder — follow the set-up-factory skill first. For later iterations, keep using what the student already chose. `AGENTS.md` says how to run the suite.
9. Implement only this iteration, driven by the suite, leaving out the `@real-agent` examples. Do not start any later iteration. Until the suite passes, repeat:
   - Run the suite and take the first example that fails or has undefined steps.
   - If it has undefined steps, define them, true to their words, reusing the step definitions that exist. Run it: it should fail for the reason the factory change will fix.
   - Make the smallest factory change that makes it pass, without breaking the examples that passed before.
10. If the suite fails and you cannot fix it within the spec, stop and report the failure.
11. Change `ITERATION` from `<iteration> WIP` to `<iteration> Done`.
12. Commit the implementation, the step definitions and that change with message `Implement homework <iteration>`.
13. Report back with:
    - the iteration number and title
    - the goal in plain language, from `spec/README.md` and `spec/FACTORY.md`
    - a short summary of what changed, in the factory and in the step definitions
    - the suite passing, as the student can run it
    - the README's example CLI commands, and the `@real-agent` examples, as things the student can try by hand with `pi`
    - what's still missing, from the closing lines of `spec/README.md`
14. Ask: "Ready for me to implement the next iteration?"
15. Stop and wait for the student's answer. If they say yes, repeat from step 1. If they say no, stop.

Rules:

- Implement one iteration per commit.
- Offer a solution branch before editing on `main`; do not create a branch without the student confirming.
- Pause after each iteration; do not automatically continue without the student confirming.
- Do not edit anything in `spec/`. `ITERATION` is yours to update.
- Do not commit unrelated existing changes.
- Keep each implementation scoped to its spec.
- Keep the factory minimal: a short loop driving the agent, with state on disk. Do not encode the plan or the seed in code.
- The factory never contains an agent of its own, stand-in or otherwise. Stand-ins are chosen from outside, the same way `pi` is.
- Avoid defensive code and production hardening unless the spec asks for it.
