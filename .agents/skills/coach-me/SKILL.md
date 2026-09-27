---
name: coach-me
description: Walk the student through their next homework iteration. Use when the student says "coach me", asks to be coached, or wants to work through their next homework with guidance.
---
Walk the student through implementing their next homework iteration.

The student is building a "factory" — a small program that turns a seed into a plan, then works the plan one task at a time, driving a coding agent to do the real work. The seed and plan live in files on disk, not in the factory's code.

## Where things live

You work from the factory's folder: `tetris/.factory` through iteration 003, and `factory/` from 004 on (fetch-iteration moves it there). Paths below are relative to it, except those starting `tetris/`, which are from the repository's root.

- **The factory** — the student's code, in this folder.
- `spec/` — the iteration they're working on, fetched from the course: `README.md`, `FACTORY.md` and `features/`. The feature files are also the factory's test suite.
- `ITERATION` — their progress: one line, the iteration and its status, e.g. `001 WIP`.
- `tetris/seeds/` — the seeds the factory builds from.
- **The step definitions** — the student's, in their factory project. They tie the feature files to the factory, and make the machines in each example do what it says, with test doubles the student writes (homework 1's README explains).
- **The codebase** — the `tetris/` folder. The factory builds the game there; you don't. Through 003 it is the folder around the factory. From 004 it is a target beside it, and holds its assembly lines and their machines in `tetris/.assembly-lines/`.

## Coaching

Follow this process exactly:

1. Read `ITERATION`. If it is missing or says `Done`, follow the fetch-iteration skill first. Carry on here once it has committed the adoption.
2. Read the whole spec:
   - `spec/README.md` — the homework framing and its ground rules
   - `spec/FACTORY.md` — a short summary of the factory at this point
   - `spec/features/` — the acceptance criteria, in Gherkin
   - the seeds in `tetris/seeds/`

   Together they are the whole spec, not just what's new.
3. If the spec is unclear, stop and ask before editing.
4. Check the working tree and avoid touching unrelated student changes.
5. If there is no factory project yet — no Gherkin runner set up in this folder — follow the set-up-factory skill first. For later iterations, keep using what the student already chose. `AGENTS.md` says how to run the suite; if it doesn't, work it out from the project.
6. Run the suite, leaving out the `@real-agent` examples. Note which examples fail and which steps are undefined: that is this iteration's work.
7. Introduce the iteration with a very concise overview:
   - Goal: the behaviour to add, in plain language (from the README and `FACTORY.md`, not the Gherkin).
   - Where the suite stands: how many examples pass, fail, or have undefined steps.
   - Show the README's example CLI commands and expected outputs, then ask the student what questions they have.
   - Mention that if they'd rather you build the whole iteration, they can use `implement-it` (you build it, then demo it) or `implement-fast` (you just build it).
8. Pick the next example to work on: the first one, in feature-file order, that fails or has undefined steps. Prefer one that needs no other example to pass first.
9. Show the next small change for that example. There are two kinds, and they alternate:
   - **Step definitions.** If the example has undefined steps, the change is to define them, so the example runs and fails for the right reason. Keep each definition true to the step's words, and reuse the ones the student already has.
   - **The factory.** If the example fails, the change is the smallest one to the factory that makes it pass.

   For either kind:
   - Start with what the step will achieve, then explain how to do it.
   - Reference the current code by file and line number, and quote the relevant nearby code, e.g. "In `path/to/file.ts` around line 37, you should see this...".
   - Be specific about the intent and why we're making the change, and show the new code.
10. Ask whether the student wants to make the change or wants you to make it.
11. If the student chooses to make it, stop and wait for them to say they made the change.
12. If the student asks you to make it, edit only the files needed for that step.
13. Run the example. After new step definitions, it should fail for the reason the next factory change will fix. After a factory change, it should pass, and the examples that passed before should still pass.
14. If the result is not what the step aimed for, explain the smallest correction and ask again whether the student wants to make it or wants you to make it.
15. Repeat steps 8-14 until the whole suite passes, leaving out the `@real-agent` examples.
16. Offer the `@real-agent` examples as something to try by hand, with `pi`, using the README's example commands. They are optional.
17. Finish by pointing at what's still missing. Read the closing lines of `spec/README.md` for what the next homework builds on, and make clear that any remaining rough edges are expected at this point.
18. Change `ITERATION` from `<iteration> WIP` to `<iteration> Done`.
19. Commit the implementation, the step definitions and that change with message `Implement homework <iteration>` (e.g. `Implement homework 003`).

## Rules

- Do not start more than one iteration.
- Do not edit anything in `spec/`. It is the spec, not yours to change. `ITERATION` is yours to update.
- Do not edit implementation files unless the student asks you to, and even then only implement the next baby step. If they want you to take over the whole iteration, point them at `implement-it` or `implement-fast`.
- Break the implementation into small baby steps. Prefer outside-in: start with the smallest visible behaviour that proves the new capability, even if parts are hard-coded, then replace the hard-coded pieces one at a time.
- Keep the factory minimal: a short loop driving the agent, with state on disk.
  - The intelligence lives in the agent and the files, not the factory.
  - Do not encode the plan or the seed in code.
  - Do not build a framework.
  - Do not add defensive code or hardening. This is a learning exercise.
- The factory never contains an agent of its own, test double or otherwise. Doubles live with the step definitions and are chosen from outside, the same way `pi` is.
- You may run commands to inspect files, review diffs, and run checks.
- Do not commit unrelated existing changes.
- Keep coaching steps small enough for a student to do comfortably.
- Be super concise. Avoid jargon.
- When introducing an iteration, include only the goal and the steps to get there.
- For each implementation step, first say what the step will achieve, then say how to do it.
- When describing a code change, always refer to the current code by file and line number and quote the relevant nearby code.
- At each implementation step, ask whether the student wants to make the change or wants you to make it.
- The suite is the check. Don't test by hand what an example already covers.
- If the suite fails and you cannot coach or implement a fix within the spec, stop and report the failure.
