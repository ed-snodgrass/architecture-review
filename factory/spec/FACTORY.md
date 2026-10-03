# The factory, as of this iteration

The factory builds software from a seed, one task at a time. On each
pass it calls a coding agent, which writes a plan from the seed if there
is none, and otherwise does the next task and marks it done. The factory
commits the work, and stops when the agent's result says the plan is
complete. Nothing checks the work yet.

The factory writes no project code and no plan itself, and never reads
the plan. A coding agent does all of that — `pi` by default, or another
chosen for the run.

Each run requires both a seed file and a target folder. Relative paths
are resolved from the caller's working directory; absolute paths work too.
Targets are plain folders. The factory creates a missing folder, uses its containing Git repository and initializes
Git only if no repository contains it. It runs agents in the target and
commits only that target's work and plan, preserving unrelated staged
and unstaged edits. Each target keeps its own plan in `.factory/plan.md`. A fresh target starts fresh; rerunning a
target resumes its plan. An omitted or missing seed reports that there is
no seed, without calling an agent. Before stopping successfully, the
factory records the final plan, including updates after a work commit.
A completed run leaves no uncommitted changes in the target.

Running one pass does one task, or writes the plan. Running to
completion keeps going until the agent's result says the plan is
complete.
