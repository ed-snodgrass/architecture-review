# Homework 4 — Runs and targets

Read `FACTORY.md`, then the feature files in `features/`. Together they are
the whole spec of the factory at this point, not just the new parts.

Your factory already builds into the target folder you choose. Until now
every invocation supplied a seed and target and used the same assembly line. Each
target kept one plan: an implicit run for that generation. This homework
introduces named runs that remember what they build and how, while the
factory source stays in `factory/`.

- **The assembly lines move into the target.** A target holds its
  product and, in `.assembly-lines/`, the lines that build it, with the
  machines they name in `.assembly-lines/.machines/`, a folder each. A
  machine's name is unique in its target: every line there that names
  the doer runs the same doer. Move your line and machines from homework
  3 into `tetris/tetris-003/.assembly-lines/` (or whichever target you
  choose).
- **Each execution is a named run.** You name the run, and the first time
  you start it you give it a target, one of that target's lines, and a seed.
  The run remembers all three; after that, its name is enough. It keeps
  its plan with the factory, in `factory/runs/<name>/plan.md`. To resume your
  existing game, move its `.factory/plan.md` there; a run
  now owns that plan. Or start with a fresh target. Unlike the target's
  plan in earlier homeworks, run state must stay out of Git: add
  `/factory/runs/` to your repository-root `.gitignore`.

Once the route is data, a target can hold more than one line. Write a second
one — the same line without the validator will do — and have each run say
which line it runs.

Starting or resuming a run is an **invocation** of that same run. Its name,
settings and plan persist across invocations.

## The commands you'll end up with

The exact shape is your choice. Run from the repository root, with
`bin/factory` linked to your entry point:

```sh
# a new run: its target, its line and its seed
$ bin/factory --run tetris --target tetris/tetris-003 --line careful --seed tetris/spec.md

# after that, its name is enough
$ bin/factory --run tetris

# a second target: write snake/spec.md describing Snake first
# give it a line and machines of its own
$ mkdir -p snake/snake1
$ cp -r tetris/tetris-003/.assembly-lines snake/snake1/
$ bin/factory --run snake --target snake/snake1 --line quick --seed snake/spec.md
```

The factory should build whatever the new seed describes, without disturbing
the first run.

The checks still run against a copy of your factory, because runs live with
the factory. The copy still builds in separate targets, now each holding its
own lines and machines.
