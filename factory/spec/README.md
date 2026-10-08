# Homework 3 — The assembly line

Read `FACTORY.md`, then the feature files in `features/`. Together they are
the whole spec of the factory at this point, not just the new parts.

The factory does the same work it did for homework 2. What changes is where
the route lives. Until now it was hidden in your code: the order of planner,
doer and validator, the retry, and the looping in the pass. All of it comes
out into an **assembly line** — a graph the factory reads — and the planner,
the doer and the validator become machines on it. The planner decides
whether there is more to do; the line says where each answer goes.

That takes the pass with it. There is no more running one pass: the factory
runs the assembly line, and the line says what happens next.

Each machine now has a name, and a configuration kept in your factory's
folder under that name: what harness runs it (`pi`, unless it names another)
and anything else it needs, such as the validator's lens. The line's nodes
are those names.

An edge only routes. Its label names a field of the result the machine
before it answered with: `satisfied` is taken when the validator's result
says `"satisfied": true`, `not satisfied` when it says false. So the
machines' results, not their words, decide where the line goes. The retry
limit is not on the line: it is the factory's, a setting of your choice.

Your factory has one assembly line, kept in its own folder. Take the
validator out of it and the factory should still run, doing the work
unchecked — without a change to your code.

`assembly-line.feature` is prescriptive about Graphviz. That is to keep the
acceptance criteria clean, not because it is the only way — if you would
rather express the assembly line some other way, go ahead. The only thing
you need to remember is you'll have to carry over any changes you make to
the feature files across the future iterations


## Run against a target

The factory source stays in `factory/`, and the target argument still
selects the output codebase. Running the assembly line replaces `--all`:

```sh
$ bin/factory --seed tetris/spec.md --target tetris/tetris-003
$ npm --prefix tetris/tetris-003 start
```

A fresh target starts with a fresh plan in `.factory/plan.md`. Reusing
`tetris/tetris-002` resumes its plan, which may already be complete. The seed
is still supplied with `--seed`; the line and machine configurations live
with the factory.
