# capstone-project-starter

Fork this to start working on your factory.

Your fork is your capstone project, so name it for your capstone. The
homeworks don't start there: they build Tetris, in `tetris/`, as a
practice target that everyone shares. Your factory learns on Tetris
first.

## Get started

1. Pick a name for your capstone project. Fork this repo and set the
   fork's repository name to your capstone's name, then clone your fork.
   If you're using Codespaces or a Dev Container, read
   [Codespaces and Dev Containers](#codespaces-and-dev-containers) first.
2. Open your favourite coding agent harness (Claude Code, Codex, Pi,
   etc) at the repository root. That is where it finds its instructions
   and skills. Your factory source lives in `factory/`.
3. Say "fetch iteration". It downloads the first homework from the
   [course](https://github.com/lean-software-production/tutorial) into
   `factory/spec/`.
4. Say "coach me" to work through it step by step. The first time, it
   helps you pick a language and set up a Gherkin runner: the feature
   files in each homework are your factory's test suite, and you build
   until it passes. When you've finished, say "fetch iteration" again
   for the next one.

## Where things live

- `factory/` — your factory source, from the first homework onward.
  - `spec/` — the current homework: `README.md`, `FACTORY.md` and the
    acceptance criteria in `features/`, which are also your tests.
  - `ITERATION` — which homework you're on, and whether it's done.
- `bin/factory` — a symlink to your factory's entry point, created during
  setup after you choose a language. Run it from the repository root.
- `tetris/spec.md` — the practice seed, supplied with the first homework.
- `tetris/tetris1/`, `tetris/tetris2/` — generated practice games, one
  folder per generation. Each keeps its own plan in `.factory/plan.md`
  through homework 3. The factory commits only the selected target's
  generated work, excluding its plan, in this repository.
- Your capstone product — a separate folder later, such as `plant-feeder/`
  in a fork named `my-plant-feeder`.
- `bin/doctor`, `bin/doctor_test.sh` — starter environment checks.
- `tools/pi-rpc-acp/` — from homework 6 your factory runs machines as
  ACP agents; this is the bridge that runs pi as one. The devcontainer
  puts it on your `PATH`, and installs the ACP adapters for Claude Code
  and Codex.
- `.agents/skills/` — the skills: `fetch-iteration`,
  `set-up-factory`, `coach-me`, `implement-it` and `implement-fast`.

## Build into a chosen folder

After you build homework 1, run from the repository root:

```sh
bin/factory --seed tetris/spec.md --target tetris/tetris1 --all
git add -- tetris/tetris1/.factory/plan.md
git commit --only -m "Save Tetris 1 plan" -- tetris/tetris1/.factory/plan.md
npm --prefix tetris/tetris1 start
```

After homework 2 adds validation, build the same seed in a fresh target:

```sh
bin/factory --seed tetris/spec.md --target tetris/tetris2 --all
git add -- tetris/tetris2/.factory/plan.md
git commit --only -m "Save Tetris 2 plan" -- tetris/tetris2/.factory/plan.md
npm --prefix tetris/tetris2 start
```

Commit each generation's plan as shown above so it stays with the game in
Git. The factory leaves plans out of its per-task work commits; these
separate plan commits preserve the generation's record. The path arguments
keep any unrelated staged edits out of these commits.

A new target starts with a new plan; running it again resumes that plan.
Both games stay available for comparison. Targets are plain folders;
Git is initialized only if the target is outside any repository.
`bin/factory` is the entry point you build during the homework.

## Codespaces and Dev Containers

This repository includes a Dev Container for GitHub Codespaces and local Dev
Container users. It provides Node.js plus Pi, Claude Code, and Codex (installed
from the [lean-software-production devcontainer features](https://github.com/lean-software-production/devcontainer-features)).
Open the repository in a container, then authenticate the agent you want to use
as the non-root `node` user—credentials are not included in the image or
repository. The Codex VS Code extension is pinned to `26.5908.31748`, the last
release before it began depending on the UI-only Codex Audio extension, which
cannot run in browser-based Codespaces. Don't update it past that version there;
the `codex` terminal CLI is unaffected either way.

```sh
# Pick one. Codespaces users can use the device-code flow when browser callback
# login is inconvenient.
pi                 # then enter /login
claude auth login
codex login --device-auth

# Confirm the environment without contacting a model.
bin/doctor
bin/doctor --agent codex
```

`bin/doctor` checks Node.js, Git, Bash, and all three agent CLIs. By default it
requires the tools and at least one configured agent; `--agent pi`,
`--agent claude`, or `--agent codex` checks a specific choice, and
`--agent all` requires every agent to be configured. It does not read credential
contents or make a model request. For Pi, it uses `pi auth check --no-refresh`
against a saved/uniquely identifiable provider; ambiguous Pi configuration is
reported as unknown rather than ready. Once it reports ready, start Pi with `pi`,
Claude Code with `claude`, or Codex with `codex`. Codex defaults to `gpt-6-sol`
with Full Access permissions (no sandbox, no approval prompts); change these
with `/model` and `/permissions`, or in `~/.codex/config.toml`. Full Access
means Codex can run any command, including `git push` with the Codespace's
GitHub token, without asking.

Run `bin/doctor_test.sh` to exercise `bin/doctor` against fake agent CLIs.

Run `python3 .agents/skills/fetch-iteration/fetch_test.py` to check fetching
without network access.
