# capstone-project-starter

Fork this to start working on your factory.

## Get started

1. Fork or clone this repo.
2. `cd tetris/.factory` and fire up your favourite coding agent harness
   (Claude Code, Codex, Pi, etc) there.
3. Say "fetch iteration". It downloads the first homework from the
   [course](https://github.com/lean-software-production/tutorial) into
   `spec/`.
4. Say "coach me" to work through it step by step. When you've finished,
   say "fetch iteration" again for the next one.

## Where things live

- `tetris/` — the game your factory builds. It starts out empty.
- `tetris/seeds/` — what the factory builds from. The sample Tetris seed
  arrives with the first homework.
- `tetris/.factory/` — your factory. You build it here.
  - `spec/` — the current homework: `README.md`, `FACTORY.md` and the
    acceptance criteria in `features/`.
  - `ITERATION` — which homework you're on, and whether it's done.
  - `stand-ins/` — fake agents: test fixtures for your factory's checks.
    They're fetched and committed with each homework.
- `tetris/.agents/skills/` — the skills: `fetch-iteration`, `coach-me`,
  `implement-it` and `implement-fast`.

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

Run `tests/doctor_test.sh` to exercise `bin/doctor` against fake agent CLIs.
