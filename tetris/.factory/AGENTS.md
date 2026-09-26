# Agent instructions

This is a software factory built during the lean software manufacturing
course. It builds Tetris in `..` (the `tetris/` folder), from the seeds in
`../seeds/`.

- `spec/` holds the current homework iteration, fetched from the course. Don't edit it. Its feature files are the factory's test suite.
- `stand-ins/` holds the stand-in agents the tests use.
- `ITERATION` holds the student's progress, e.g. `001 WIP`.

Skills, in `../.agents/skills/`:

- **fetch-iteration** — when the student says "fetch iteration", or there is no iteration in progress.
- **set-up-factory** — when there is no factory project yet: sets up a Gherkin runner for `spec/features/` in the student's language.
- **coach-me** — when the student says "coach me", asks to be coached, or wants to work through their homework with guidance.
- **implement-it** — when the student wants you to build the iteration and demo it.
- **implement-fast** — when the student wants you to just build the iteration.

If your harness doesn't load skills, read the skill's `SKILL.md` and follow it.
