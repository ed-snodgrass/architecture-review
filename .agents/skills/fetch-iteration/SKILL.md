---
name: fetch-iteration
description: Fetch the next homework iteration's spec from the course into spec/. Use when the student says "fetch iteration", or before coaching or implementing when there is no iteration in progress.
---
Fetch the student's next homework iteration from the course on GitHub.

Work from the factory's folder: `tetris/.factory` through iteration 003, `factory/` from 004. `ITERATION` there holds one line: the iteration and its status, e.g. `001 WIP` or `001 Done`. If it doesn't exist, the student hasn't started.

1. Read `ITERATION`.
   - Missing or `Done`: go to step 2.
   - `WIP`: the current iteration is still in progress. It is ready when its test suite passes: the feature files in `spec/features/`, run by the factory's Gherkin runner, leaving out the `@real-agent` examples. `AGENTS.md` says how to run it; if it doesn't, work it out from the project.
     - If the suite passes, write `ITERATION` as `<iteration> Done` and go to step 2.
     - If it fails, say how many examples fail or have undefined steps, and ask the student whether to fetch the next iteration anyway. If they say no, stop. If they say yes, go to step 2 without marking the iteration done.
     - If there is no suite yet, say so, suggest the set-up-factory skill, and ask whether to fetch anyway.
2. Check the working tree. If there are uncommitted changes in `spec/` or to `ITERATION` that you didn't just make, stop and ask.
3. Run `"$(git rev-parse --show-toplevel)/.agents/skills/fetch-iteration/fetch.sh"`. It downloads the course, then:
   - replaces `spec/README.md`, `spec/FACTORY.md` and `spec/features/` with the next iteration's, leaving anything else in `spec/` alone
   - copies the iteration's sample seed to `tetris/seeds/tetris.md` if there is one and that file doesn't exist yet
   - refreshes `stand-ins/`
   - writes `ITERATION` as `<iteration> WIP`
   - from 004, if the factory is still in `tetris/.factory`, moves it to `factory/` with `git mv`: from 004 the factory has a codebase of its own, beside `tetris/`

   If it says there is nothing left to fetch, tell the student they have finished every iteration and stop.
4. From the repository's root, commit the factory's folder, `tetris/seeds/` and, if fetch.sh moved the factory, its old folder, with message `Adopt spec for iteration <iteration>`.
   - If fetch.sh moved the factory, tell the student plainly: close this session and open their coding agent in `factory/` from now on. Their homework 3 line and machines belong in `tetris/.assembly-lines/`, which the 004 homework explains. Then stop.
5. For any iteration after 001, show the student what changed: `git show --stat HEAD`, and the diff of `spec/FACTORY.md`. That diff is how the factory's spec evolves.
6. If there is a suite, run it, leaving out the `@real-agent` examples, and show which examples now fail or have undefined steps. That is the work for this iteration: steps keep their words between iterations unless their meaning changed.
7. Tell the student to say "coach me" to work through it step by step. Or, if they want you to build it, they can use `implement-it` (you build it, then demo it) or `implement-fast` (you just build it).

## Rules

- Fetch one iteration at a time.
- Don't edit anything in `spec/` by hand. It is the spec, not yours to change.
- `COURSE_REF` picks the course branch to fetch from. It defaults to `main`. Only set it if the student asks.
