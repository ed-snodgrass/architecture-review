# Homework 2 — Checking the work

Read `FACTORY.md`, then the feature files in `features/`, and make them true
of the factory you built for homework 1. Together they are the whole spec,
not just the new parts: the rules you already satisfied are still there, and
some of them have changed. A pass is no longer one agent call: a planner
keeps the plan, a doer does the work and a validator checks it. Your one
prompt from homework 1 splits in three.

Before you start, pick what your validator should look for. Testability,
single responsibility, usability, internationalisation, security — any lens
will do, and the interesting part is what your factory does with the
findings. Choose one and write it down.

Your doubles now play three machines. A validator's double answers with
whether it is satisfied and, if not, why: the fields `satisfied` and
`findings` that `machine.feature` has your factory ask for.

## Once your suite passes

Keep the game you built in homework 1 in `tetris/tetris-001/`. Use your
upgraded factory with a real coding agent to build from the same seed in
a new target. From the repository root:

```sh
bin/factory --seed tetris/spec.md --target tetris/tetris-002 --all
npm --prefix tetris/tetris-002 start
```

The factory commits this generation's plan with its work. The planner
marks tasks done after the work is committed, so the factory also records
the final plan update before it stops. A run to completion leaves no
uncommitted changes in the target; no separate plan checkpoint is needed.

The new target gets its own plan. Running against `tetris/tetris-001` again
would find its completed plan and stop. Changing the target gives the
upgraded factory fresh work without deleting v1 or changing the seed.

What difference did validation make? **None is a fine answer.** Start by
looking at `tetris/tetris-002/.factory/plan.md`: any validator findings are
recorded there as subtasks. Then compare the two games.

Your agent should offer to compare `tetris/tetris-001` with
`tetris/tetris-002`, summarise what differs, and build an HTML report of the
comparison at
`tetris/comparison.html`. Review it together. Two builds from the same seed
can differ anyway; the report should distinguish differences supported by
recorded validator findings from other differences between the generations.
It should also say when there are no recorded findings.

You can play both versions in separate terminals:

```sh
npm --prefix tetris/tetris-001 start
npm --prefix tetris/tetris-002 start
```

For your Maven submission, include screenshots of both versions, name your
validator's lens, and explain what difference validation made to the code,
if any. Use the plan and comparison report to help explain what you observed.

### Bonus round: change the lens

Choose a different lens for the validator and build another generation from
the same seed in a fresh target. Keep the model and everything else the same.
Name the target for the lens you chose, such as
`tetris/tetris-002-security`, and leave `tetris/tetris-002` unchanged.

Compare the two validated generations. Start with their plans: did the new
lens produce different findings or subtasks? Then compare the code. Which
differences can you trace back to those findings? What impact did changing
the lens have? Finding no difference is useful too.
