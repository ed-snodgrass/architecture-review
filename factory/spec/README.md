# Homework 1 — Basic unvalidated loop

Build a **Ralph loop**: a small program (your "factory") that turns a seed
into a plan, then works the plan one task at a time, driving a coding agent
to do the real work. By the end, running your factory enough times builds a
real, playable game of Tetris in the terminal.

## What you're building

Your factory source lives in `factory/` in your capstone repository. Open
your coding agent at the repository root; `bin/factory` is a symlink to the
entry point you build, created during project setup. Each run requires a
seed file and target folder, for example `--seed tetris/spec.md --target
tetris/tetris-001`. The factory creates the folder if needed and runs the
coding agent there. It uses the containing Git repository, initializing Git
only if the target is outside any repo. Relative seed and target paths are
resolved from the caller's working directory; absolute paths work too.

The practice seed is `tetris/spec.md` in your capstone repository —
fetch-iteration copies this homework's `spec.md` there if it does not exist
(it says: build Tetris in the terminal, started with `npm start`, fitting
inside 24 rows). Each target keeps its own plan in `.factory/plan.md`. This
is run state, not another copy of your factory. On each pass, the factory
points the agent at the resolved seed and plan paths, and the agent:

1. If there is no plan yet, writes one: the seed broken into a few tasks.
2. Otherwise, picks the first task that isn't done, implements it in real
   code in the selected target, and marks it done in the plan.
3. Answers with a **result**: a line of JSON describing what it did,
   such as `{"complete": false, "task": "set up the project"}`, with
   `"complete": true` once no task is left.

All of that is in your prompt; ask for the result there, or use your
harness's structured output if it has one. The factory never reads the plan:
it stages and commits only the generated work in the target, using pathspecs
for both operations and including `.factory/plan.md`, and stops when the
agent's result says the plan is complete. Unrelated staged and unstaged
changes in the repository are left alone. It never looks for words in what
the agent says.

The seed and the plan live in files, not in your code. Each pass is
stateless: the agent reads the files, does one thing, writes the files back.
The rules below pin down the rest.

## The commands you'll end up with

The exact command name is your choice. This is the shape of what should work
by the end, run from the repository root, with `bin/factory` for whatever
you call it:

```sh
# first run — no plan yet, so the agent writes one instead of building
$ bin/factory --seed tetris/spec.md --target tetris/tetris-001
{"complete": false}                  # the agent wrote tetris/tetris-001/.factory/plan.md

# next run — one pass, one task, one commit
$ bin/factory --seed tetris/spec.md --target tetris/tetris-001
{"complete": false, "task": "set up the project"}
$ git log --oneline -- tetris/tetris-001
# one new work commit; plan-only commits may also appear

# run to completion
$ bin/factory --seed tetris/spec.md --target tetris/tetris-001 --all
{"complete": false, "task": "..."}
{"complete": false, "task": "..."}
{"complete": false, "task": "..."}
{"complete": true}
factory stopped

```

What the agent says will differ; the point is that real code appears in
`tetris/tetris-001/`, one task per pass, and `npm start` runs Tetris.

The feature files are your tests, too: start by setting up a Gherkin runner
for them in your factory's language (see the [ground
rules](../README.md#ground-rules)), and build until they pass. Each example
runs against a copy of your factory with a fresh target folder in a test
repository, so the checks never touch your Tetris. A new target starts with
a new plan; running the same target again resumes its plan. This lets you
keep different generated versions side by side.

## Test doubles

Working with agents takes time. LLMs are slow. We want test suites to be
fast.

The usual way to do that is test doubles (stubs, mocks, spies, etc.). It may
be beneficial to create test doubles to replace machines for speed. Test
frameworks, or occasionally separate libraries, provide very effective test
doubles with clean APIs.

We have a tag, `@real-agent`, to signify examples that should use a real
agent.

## Rules

The [ground rules](../README.md#ground-rules) apply, as they do to every
homework. It doesn't have to be a bash loop, and we'd rather it weren't.

**Hint: keep it small.** All the intelligence is in the agent, its prompt
and the files; the factory is a short loop around one agent call. The
reference version is a few lines, and the language is irrelevant:

```text
call the agent: "write the plan, or do the next task and mark it done"
commit the changed work and plan in the target
if its result says complete: stop
```

## Once your suite passes

Use your factory with a real coding agent to build the first generation.
From the repository root:

```sh
bin/factory --seed tetris/spec.md --target tetris/tetris-001 --all
npm --prefix tetris/tetris-001 start
```

Play the game and keep it for comparison with the next generation. The
factory commits the plan with the work, so the generation's record stays
with the game automatically. There is no separate plan checkpoint to make.

### Bonus round: try another model

If your harness supports choosing a model, extend your factory to accept
that choice and pass it to the harness. Build two more generations from the
same seed with different models, each in a fresh target. Compare how long
they take and what they produce. Which result do you prefer, and why?

Keep `tetris/tetris-001` unchanged: the next homework uses it to explore
the effect of validation. This is an informal experiment, not a feature
requirement, so do not build a benchmarking framework. Later iterations
will move model choice into machine configuration and give you better ways
to compare cost and combine several models' judgements.

You will keep `tetris/tetris-001`. The next homework adds checking the work:
the factory starts noticing when the agent's output is wrong.
