---
name: set-up-factory
description: Set up the student's factory project, with a Gherkin runner that runs spec/features/ as its test suite. Use when coach-me, implement-it or implement-fast finds no factory project in the factory's folder, or when the student asks to set one up.
---
Set up the student's factory project, so that the feature files in `spec/features/` run as its test suite from the first homework on.

Open the agent at the repository root. The factory source, `spec/` and `ITERATION` live in `factory/` for every iteration. Run factory development commands from `factory/`, and the factory CLI from the repository root through `bin/factory`. Paths below are relative to `factory/` unless stated otherwise. The spec is in `spec/`.

Follow this process exactly:

1. Check that there is no factory project here yet: no project files (such as `package.json`, `pyproject.toml`, `go.mod` or `Gemfile`) and no step definitions. If there is one, stop and say so.
2. If `spec/features/` is empty, follow the fetch-iteration skill first.
3. Ask the student which language they want to build their factory in. It must have a Gherkin runner. Offer these, and say which runner goes with each:
   - JavaScript or TypeScript: cucumber-js
   - Python: behave, or pytest-bdd
   - Go: godog
   - Ruby: Cucumber
   - Java or Kotlin: Cucumber-JVM
   - Rust: cucumber (cucumber-rs)
   - C#: Reqnroll

   Any other language with a maintained Gherkin runner is fine too. There is no prescribed stack beyond that.
4. Set up the smallest project that runs the suite:
   - the runner, installed as a development dependency, reading `spec/features/`
   - a default run that leaves out examples tagged `@real-agent`
   - a way to run the `@real-agent` examples on purpose, such as a second profile, since some runners won't let a command-line tag undo one in their configuration
   - an empty folder for step definitions, outside `spec/`
   - an executable entry point inside the repository's `factory/` folder, which will accept required `--seed <file>` and `--target <folder>` arguments; for now it only says it isn't built yet
   - a relative symlink `bin/factory -> ../factory/<entry point>` at the repository root. If the language needs an interpreter or build command, the entry point is a small executable launcher inside `factory/`. It resolves its own source location without changing the caller's working directory, so relative seed and target arguments remain relative to the root
   - ignore rules for dependencies and build output

   Don't write any step definitions or factory code yet. That is the homework.
5. Run the suite. Every step should show as undefined. That proves the runner finds the features and leaves out the `@real-agent` examples. If it doesn't, fix the set-up until it does.
6. Explain to the student, briefly, how the tests will work, so their step definitions follow it:
   - Each example runs against a **copy** of the factory in a new folder, with a separate target selected on the command line. Through 003, each run supplies a seed path and a target path; the machines and (from 003) the one assembly line live in the factory copy, while the target keeps its own plan. Test that commits include only the selected target, preserving unrelated staged and unstaged factory edits in the containing repository. From 004, jobs keep plans with the copy, and targets hold lines and machines in `.assembly-lines/`. A copy needs only the factory's own code. Link its dependencies rather than copying them, and never copy `spec/` or the step definitions.
   - When an example says what a machine does ("the validator is never satisfied"), the step makes it so with a **test double**: a small program, written by the student or their agent from the examples, that does that one thing. Doubles live with the step definitions, outside `spec/` and outside the factory. Steps point the factory at them the way the student would point it at `pi`: by path, from outside. The feature files never mention doubles; homework 1's README describes the practice.
   - Give each example its own temporary folder. Doubles log their calls to a file there, write what each call was given to a file of its own in a folder there, and keep any state in it. A double the example needs to see at work waits for a signal from the step (a file appearing), never a set time, and gives up if the folder is removed. Remove the folder when the example ends, so nothing is left waiting.
   - A double answers with a result whether or not it was asked; the examples that check what the factory asks for (in `agent.feature`, and `machine.feature` from homework 2) are what keep the prompts honest.
   - From homework 6 machines run as ACP agents, so doubles do too. And the factory is a daemon: each example must stop it when it ends, whatever happened, so no daemon outlives its example.
   - For "pi has been called", put a fake `pi` first on the `PATH` that logs its call and answers something harmless.
7. Add a "Checks" section to the repository-root `AGENTS.md`, saying in one or two lines how to run the suite. Other agents will look there first.
8. Commit with message `Set up the factory project`.
9. Hand back to the skill that called this one, or tell the student to say "coach me".

Rules:

- Do not edit anything in `spec/`.
- Keep the project minimal: the runner, and nothing the homework doesn't need yet.
- The factory never contains an agent of its own, test double or otherwise.
