# Agent instructions

This is a software factory built during the lean software manufacturing
course. Open your agent at the repository root. Build the factory source
in `factory/`; it stays there for every homework. Run it from the root
through `bin/factory`, a symlink set-up-factory creates after the student
chooses a language. Both `--seed` and `--target` are required from homework 1:
`bin/factory --seed tetris/spec.md --target tetris/tetris1`.

Targets are plain folders. The factory commits only the generated work
inside the selected target, in the Git repository containing it. Plans
live in `<target>/.factory/plan.md` through 003, excluded from work commits.
From 004, jobs keep plans in `factory/jobs/<name>/`, and targets keep lines
and machines in `.assembly-lines/`.

The repository is the student's fork, named for their capstone project.
Tetris is not their capstone: it is the practice target every student's
factory builds first. Say so when you first explain the course to them.

- `factory/spec/` holds the current homework iteration, fetched from the course. Don't edit it. Its feature files are the factory's test suite.
- `factory/ITERATION` holds the student's progress, e.g. `001 WIP`.

Skills, in `.agents/skills/` at the repository's root:

- **fetch-iteration** — when the student says "fetch iteration", or there is no iteration in progress.
- **set-up-factory** — when there is no factory project yet: sets up a Gherkin runner for `factory/spec/features/` in the student's language.
- **coach-me** — when the student says "coach me", asks to be coached, or wants to work through their homework with guidance.
- **implement-it** — when the student wants you to build the iteration and demo it.
- **implement-fast** — when the student wants you to just build the iteration.

If your harness doesn't load skills, read the skill's `SKILL.md` and follow it.
