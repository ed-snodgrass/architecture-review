# Homework 5 — Fan out

Read `FACTORY.md`, then the feature files in `features/`.

Until now an assembly line has been a single path: one machine, then the
next. This time the line itself learns a new move. A machine with several
edges out and no labels on them **fans out**: every machine those edges
lead to runs, at the same time. The branches **fan in** where they meet:
each branch's one edge leads to the same machine, which runs once all of
them have finished, and is given what each of them answered and nothing
else. The factory refuses a line whose branches do not meet, and a
branch that fails, by crashing or by answering with no result, stops the
run.

That is all the factory learns. What you fan out to is up to the line.
The course's example is **the three big brains**: the doer's work fans
out to three reviewers, the same job on three different providers'
models, and a synthesiser reads their reports and decides.

```dot
doer -> reviewer_1
doer -> reviewer_2
doer -> reviewer_3
reviewer_1 -> synthesiser
reviewer_2 -> synthesiser
reviewer_3 -> synthesiser
synthesiser -> doer     [label="not satisfied"]
synthesiser -> planner  [label="satisfied"]
```

The reviewers being alike is the three big brains' choice, not something
fanning out needs: each branch is run as that machine would be run
anywhere, with its own prompt.

The three reviewers assess and report; they do not
decide. The synthesiser decides, and the line routes on its result, as it
did on the validator's.

## Checks that see machines at work

Some examples need a machine caught part-way through its work: three
reviewers working at the same time, say.

When using test doubles, it would be good to set their state manually
in the test, instead of running something that has a sleep or other runtime.
It saves you from potential race conditions.
