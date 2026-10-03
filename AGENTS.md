# Agent instructions

This is the starter for a software factory built during the lean software
manufacturing course. Open the agent at the repository root. Student
factory source and fetched homework live in `factory/`. Setup creates
`bin/factory`, a symlink to the entry point in the student's chosen language.
The homework specs define how the factory runs and manages its targets.

When helping a student, use the skills below for the homework they request.
When maintaining the starter itself, work on the requested scaffolding,
skills or tooling change; homework adoption is a separate student action.
Course content is authored in the tutorial repository and fetched here.

Students name their fork for their capstone project. Tetris is the shared
practice target their factories build first, not their capstone. Explain
that distinction when introducing the course to a student.

- `factory/spec/` holds the current homework iteration, fetched from the course. Don't edit it. Its feature files are the factory's test suite.
- `factory/ITERATION` holds the student's progress, e.g. `001 WIP`.

Skills, in `.agents/skills/` at the repository's root:

- **fetch-iteration** — when the student says "fetch iteration", or there is no iteration in progress.
- **set-up-factory** — when there is no factory project yet: sets up a Gherkin runner for `factory/spec/features/` in the student's language.
- **coach-me** — when the student says "coach me", asks to be coached, or wants to work through their homework with guidance.
- **implement-it** — when the student wants you to build the iteration and demo it.
- **implement-fast** — when the student wants you to just build the iteration.

If your harness doesn't load skills, read the skill's `SKILL.md` and follow it.

## Checks

From `factory/`, run `npm test` for the suite excluding `@real-agent`; use `npm run test:real` to run those examples explicitly.
Run `npm run typecheck` to check the TypeScript source.
