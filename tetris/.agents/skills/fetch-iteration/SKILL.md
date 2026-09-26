---
name: fetch-iteration
description: Fetch the next homework iteration's spec from the course into spec/. Use when the student says "fetch iteration", or before coaching or implementing when there is no iteration in progress.
---
Fetch the student's next homework iteration from the course on GitHub.

Work from `tetris/.factory`. `ITERATION` there holds one line: the iteration and its status, e.g. `001 WIP` or `001 Done`. If it doesn't exist, the student hasn't started.

1. Read `ITERATION`.
   - Missing or `Done`: go to step 2.
   - `WIP`: the current iteration is still in progress. It is ready when its checks pass. Run whatever checks the factory has (tests, linters).
     - If they pass, write `ITERATION` as `<iteration> Done` and go to step 2.
     - If they fail, or there are none, say so and ask the student whether to fetch the next iteration anyway. If they say no, stop. If they say yes, go to step 2 without marking the iteration done.
2. Check the working tree. If there are uncommitted changes in `spec/` or to `ITERATION` that you didn't just make, stop and ask.
3. Run `../.agents/skills/fetch-iteration/fetch.sh`. It downloads the course, then:
   - replaces `spec/README.md`, `spec/FACTORY.md` and `spec/features/` with the next iteration's, leaving anything else in `spec/` alone
   - copies the iteration's sample seed to `../seeds/tetris.md` if there is one and that file doesn't exist yet
   - refreshes `stand-ins/`
   - writes `ITERATION` as `<iteration> WIP`

   If it says there is nothing left to fetch, tell the student they have finished every iteration and stop.
4. Commit `spec/`, `stand-ins/`, `../seeds/` and `ITERATION` with message `Adopt spec for iteration <iteration>`.
5. For any iteration after 001, show the student what changed: `git show --stat HEAD`, and the diff of `spec/FACTORY.md`. That diff is how the factory's spec evolves.
6. Tell the student to say "coach me" to work through it step by step. Or, if they want you to build it, they can use `implement-it` (you build it, then demo it) or `implement-fast` (you just build it).

## Rules

- Fetch one iteration at a time.
- Don't edit anything in `spec/` by hand. It is the spec, not yours to change.
- `COURSE_REF` picks the course branch to fetch from. It defaults to `main`. Only set it if the student asks.
