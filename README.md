# capstone-project-starter

Fork this to start your capstone project: a software factory you build
during the lean software manufacturing course.

## What you're building

- **Your fork is your capstone project**, so name it for your capstone:
  a fork named `my-plant-feeder` builds a plant feeder.
- **The homeworks grow a factory**: a program that turns a written spec
  into working software by running coding agents. Each homework adds to
  it, and its feature files are your factory's test suite.
- **Your factory learns on Tetris first.** Everyone's factory builds the
  same practice game, in `tetris/`, before it builds your capstone.

This guide gets you from nothing to your first homework, open and ready
to work on. It takes about 15 minutes, most of it waiting for your
Codespace to build. We walk through GitHub Codespaces with Codex;
[other setups](#other-setups) work too.

## Before you begin

- [ ] A GitHub account.
- [ ] A ChatGPT plan that includes Codex.
- [ ] Device code sign-in turned on for Codex: in ChatGPT, open
      **Settings → Security** and turn on **Enable device code
      authorization for Codex**. On a Business or Team workspace, your
      workspace admin turns it on under **Permissions & Roles**.
- [ ] A name for your capstone project.

You don't need to install anything on your computer.

## Set up

### 1. Fork the repository

On GitHub, fork this repository. Set the fork's **Repository name** to
your capstone's name.

**You should see** your fork at `github.com/<you>/<capstone-name>`.

<!-- screenshot 01-fork.png: the "Create a new fork" page with the repository name filled in -->

### 2. Create a Codespace

On your fork's page, click **Code → Codespaces → Create codespace on
main**. The first build takes a few minutes.

**You should see** VS Code in your browser, with a terminal that ends in
the output of `bin/doctor`. It reports Codex as installed but not yet
configured:

```text
PASS Codex: codex-cli …
WARN Codex is not configured. Run: codex login --device-auth (or codex login)
```

That warning is expected: you sign in next.

<!-- screenshot 02-codespace-menu.png: the Code → Codespaces menu with "Create codespace on main" -->
<!-- screenshot 02-codespace-ready.png: VS Code in the browser, terminal showing the first bin/doctor output -->

### 3. Sign in to Codex

In the terminal, run:

```sh
codex login --device-auth
```

Open the link it prints, sign in to ChatGPT, and enter the one-time
code. The code expires after 15 minutes.

**You should see** the terminal report that you're signed in.

If it fails after you enter the code, device code sign-in is probably
off: check [Before you begin](#before-you-begin).

<!-- screenshot 03-device-code.png: the terminal showing the device code and link -->
<!-- screenshot 03-signed-in.png: the terminal reporting a successful sign-in -->

### 4. Check your environment

```sh
bin/doctor --agent codex
```

**You should see** these two lines, among others:

```text
PASS Codex authentication is configured.
PASS Environment is ready for codex.
```

If it says Codex is not on `PATH`, rebuild the container: open the
Command Palette and run **Codespaces: Rebuild Container**. If it says
Codex is not configured, repeat step 3.

<!-- screenshot 04-doctor-ready.png: bin/doctor --agent codex reporting the environment is ready -->

### 5. Start Codex

From the repository root, where the terminal opens, run:

```sh
codex
```

The repository root is where Codex finds its instructions and the
course skills.

**You should see** the Codex prompt, in `/workspaces/<capstone-name>`.

Codex starts with Full Access: it runs commands, including `git push`,
without asking first. Change that with `/permissions` if you'd rather
approve each one.

<!-- screenshot 05-codex-prompt.png: the Codex prompt at the repository root -->

### 6. Fetch your first homework

Say to Codex:

> fetch iteration

It downloads the first homework from the
[course](https://github.com/lean-software-production/tutorial) into
`factory/spec/` and commits it.

**You should see** Codex report the homework it fetched. In a second
terminal:

```sh
cat factory/ITERATION
```

prints:

```text
001 WIP
```

<!-- screenshot 06-fetch-iteration.png: Codex reporting the fetched homework -->
<!-- screenshot 06-iteration.png: cat factory/ITERATION printing 001 WIP -->

## You're set up when

- [ ] `bin/doctor --agent codex` reports `Environment is ready for codex.`
- [ ] `factory/ITERATION` reads `001 WIP`.
- [ ] `factory/spec/README.md` exists, holding your first homework.

## What's next

Say **"coach me"** to work through the homework step by step. The first
time, it helps you pick a language for your factory and set up a Gherkin
runner, so the homework's feature files run as your tests. You build
until they pass.

If you'd rather the agent build it for you, say **"implement it"** for a
walkthrough and demo, or **"implement fast"** to just build it.

When a homework is done, say **"fetch iteration"** for the next one.

## Other setups

You can work in a Dev Container on your own computer, or without a
container at all, with any coding agent harness (Claude Code, Codex,
Pi, etc). Ask your agent to set up an environment equivalent to this
repository's Codespace, described in `.devcontainer/devcontainer.json`.
You're ready when `bin/doctor` reports `Environment is ready`; then
carry on from [step 5](#5-start-codex), starting your agent at the
repository root.

## Reference

### Where things live

- `factory/`: your factory source, from the first homework onward.
  - `spec/`: the current homework, with `README.md`, `FACTORY.md` and the
    acceptance criteria in `features/`, which are also your tests.
  - `ITERATION`: which homework you're on, and whether it's done.
- `bin/factory`: a symlink to your factory's entry point, created during
  setup after you choose a language. Run it from the repository root.
- `tetris/spec.md`: the practice seed, supplied with the first homework.
- `tetris/tetris-001/`, `tetris/tetris-002/`: generated practice games, one
  folder per generation. Each keeps its own plan in `.factory/plan.md`
  through homework 3. The factory commits only the selected target's
  generated work and plan in this repository.
- Your capstone product: a separate folder later, such as `plant-feeder/`
  in a fork named `my-plant-feeder`.
- `bin/doctor`, `bin/doctor_test.sh`: starter environment checks.
- `tools/pi-rpc-acp/`: from homework 6 your factory runs machines as
  ACP agents; this is the bridge that runs pi as one. The devcontainer
  puts it on your `PATH`, and installs the ACP adapters for Claude Code
  and Codex.
- `.agents/skills/`: the skills `fetch-iteration`,
  `set-up-factory`, `coach-me`, `implement-it` and `implement-fast`.

### Build into a chosen folder

After you build homework 1, run from the repository root:

```sh
bin/factory --seed tetris/spec.md --target tetris/tetris-001 --all
npm --prefix tetris/tetris-001 start
```

After homework 2 adds validation, build the same seed in a fresh target:

```sh
bin/factory --seed tetris/spec.md --target tetris/tetris-002 --all
npm --prefix tetris/tetris-002 start
```

The factory commits each generation's plan along with its work. A completed
run leaves the target's work and final plan recorded in Git, without including
unrelated changes.

A new target starts with a new plan; running it again resumes that plan.
Both games stay available for comparison. Targets are plain folders;
Git is initialized only if the target is outside any repository.
`bin/factory` is the entry point you build during the homework.

### Codespaces and Dev Containers

This repository includes a Dev Container for GitHub Codespaces and local Dev
Container users. It provides Node.js plus Pi, Claude Code, and Codex (installed
from the [lean-software-production devcontainer features](https://github.com/lean-software-production/devcontainer-features)).
Open the repository in a container, then authenticate the agent you want to use
as the non-root `node` user; credentials are not included in the image or
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

### Testing the starter

Run `bin/doctor_test.sh` to exercise `bin/doctor` against fake agent CLIs.

Run `python3 .agents/skills/fetch-iteration/fetch_test.py` to check fetching
without network access.
