# capstone-project-starter

Build a software factory. Start with one coding agent, and grow a
system you can configure, observe and steer.

This is the starter for the
[Lean Software Production tutorial](https://lean-software-production.github.io/tutorial/slides/#/).
Fork it to start your capstone project.

## What you're building

- **Your fork is your capstone project**, so name it for your capstone:
  a fork named `my-plant-feeder` builds a plant feeder.
- **The homeworks grow a factory**: a program that turns a written spec
  into working software by running coding agents. Over seven homeworks
  it learns to automate (turn a seed into working software, one task at
  a time), compose (explicit routes, machines, jobs and targets) and
  operate (parallel work you can watch live and steer).
- **Your factory learns on Tetris first.** The homeworks build Tetris,
  in `tetris/`, as a practice target everyone shares. Your capstone
  comes later.

Each homework follows the same loop:

1. **Fetch**: your coding agent downloads one homework into `factory/spec/`.
2. **Build**: make its feature files pass. They are your acceptance tests.
   You choose the language, libraries and design.
3. **Repeat**: fetch again. Your step definitions carry forward.

This guide gets you from nothing to your first homework, open and ready
to work on. It takes about 15 minutes, most of it waiting for your
Codespace to build. We walk through GitHub Codespaces, where you sign
in two agents with your ChatGPT plan: the Codex extension, which coaches
you, and Pi, which your factory runs. [Other setups](#other-setups) work
too.

## Before you begin

- [ ] A GitHub account.
- [ ] A ChatGPT plan that includes Codex.
- [ ] Device code sign-in turned on for Codex, which Pi uses to sign
      in from a Codespace: in ChatGPT, open
      **Settings → Security** and turn on **Enable device code
      authorization for Codex**. On a Business or Team workspace, your
      workspace admin turns it on under **Permissions & Roles**.
- [ ] A name for your capstone project.

You don't need to install anything on your computer.

## Get started

### 1. Fork the starter

On GitHub, fork this repository. Set the fork's **Repository name** to
your capstone's name.

**You should see** your fork at `github.com/<you>/<capstone-name>`.

<!-- screenshot 01-fork.png: the "Create a new fork" page with the repository name filled in -->

### 2. Open and check

Open your fork in a Codespace, sign in to the Codex extension and Pi,
then check your tools without calling a model.

#### Create a Codespace

On your fork's page, click **Code → Codespaces → Create codespace on
main**. The first build takes a few minutes.

**You should see** VS Code in your browser, with a terminal that ends in
the output of `bin/doctor`. It reports Pi and Codex as installed but not
yet signed in. Those warnings are expected: you sign in next.

<!-- screenshot 02-codespace-menu.png: the Code → Codespaces menu with "Create codespace on main" -->
<!-- screenshot 02-codespace-ready.png: VS Code in the browser, terminal showing the first bin/doctor output -->

#### Sign in to the Codex extension

Open **Codex** from the sidebar and click **Sign in with ChatGPT**.
Finish signing in to ChatGPT in the browser tab it opens.

**You should see** the Codex chat panel, ready for a message.

<!-- screenshot 02-codex-sign-in.png: the Codex sidebar with "Sign in with ChatGPT" -->
<!-- screenshot 02-codex-panel.png: the Codex chat panel after signing in -->

#### Sign in to Pi

Your factory runs Pi to do its work. In the terminal, start Pi:

```sh
pi
```

Type `/login`, choose **OpenAI Codex (legacy)**, then **Device code
login (headless)**. Open the link it prints, sign in to ChatGPT, and
enter the one-time code. The code expires after 15 minutes. Then type
`/quit` to leave Pi.

**You should see** Pi report that you're signed in.

If it fails after you enter the code, device code sign-in is probably
off: check [Before you begin](#before-you-begin).

<!-- screenshot 02-pi-login.png: Pi's /login provider list with "OpenAI Codex (legacy)" -->
<!-- screenshot 02-pi-device-code.png: Pi showing the device code and link -->

#### Check your tools

```sh
bin/doctor --agent codex
```

**You should see** these lines, among others:

```text
PASS Pi authentication is ready for provider openai-codex (native local check; no refresh).
PASS Codex authentication is configured.
PASS Environment is ready for codex.
```

Ready means Bash, Git, Node, npm and all three agent CLIs (Pi, Claude
Code and Codex) are present, and Pi and Codex are signed in.

If it says an agent is not on `PATH`, rebuild the container: open the
Command Palette and run **Codespaces: Rebuild Container**. If Pi or
Codex isn't signed in, repeat its sign-in step.

<!-- screenshot 02-doctor-ready.png: bin/doctor reporting Pi and Codex signed in and the environment ready -->

### 3. Start your coding agent

Your coding agent is the Codex chat panel. It works in your Codespace's
folder, the repository root, which is where it finds its instructions
(`AGENTS.md`) and the course skills. Your factory source will live in
`factory/`.

**You should see** the Codex chat panel open beside your editor.

Codex starts with Full Access: it runs commands, including `git push`,
without asking first. Change that in the panel's permissions setting,
or in `~/.codex/config.toml`, if you'd rather approve each one.

<!-- screenshot 03-codex-panel.png: the Codex chat panel open beside the editor -->

### 4. Fetch Homework 1

Now talk to your coding agent. These are messages in the Codex chat
panel, not shell commands.

First say:

> fetch iteration

It downloads Homework 1 from the
[course](https://github.com/lean-software-production/tutorial) into
`factory/spec/` and commits it.

**You should see** Codex report the homework it fetched. In the
terminal:

```sh
cat factory/ITERATION
```

prints:

```text
001 WIP
```

<!-- screenshot 04-fetch-iteration.png: Codex reporting the fetched homework -->
<!-- screenshot 04-iteration.png: cat factory/ITERATION printing 001 WIP -->

Then say:

> coach me

It walks you through the homework one passing example at a time. The
first time, it helps you pick a language for your factory and set up a
Gherkin runner, so the homework's feature files run as your tests.

**You should see** Codex summarise Homework 1 and ask which language
you'd like to build your factory in.

<!-- screenshot 04-coach-me.png: Codex starting to coach Homework 1 -->

## You're set up when

- [ ] `bin/doctor --agent codex` reports Pi and Codex signed in, and
      `Environment is ready for codex.`
- [ ] `factory/ITERATION` reads `001 WIP`.
- [ ] `factory/spec/README.md` exists, holding Homework 1.
- [ ] Codex is coaching you through it.

## Keep the learning loop small

- Treat `factory/spec/features/` as the spec, and don't edit the
  fetched spec.
- Take one failing example at a time.
- Build one homework at a time. When its suite passes, say
  **"fetch iteration"** again.

If you'd rather the agent build a homework for you, say
**"implement it"** for a walkthrough and demo, or **"implement fast"**
to just build it.

## Other setups

You can work in a Dev Container on your own computer, or without a
container at all, with any coding agent harness (Pi, Claude Code,
Codex, etc). Clone your fork and check it:

```sh
git clone https://github.com/<you>/<capstone-name>.git
cd <capstone-name>
bin/doctor
```

If anything is missing, ask your agent to set up an environment
equivalent to this repository's Codespace, described in
`.devcontainer/devcontainer.json`. Sign in to Pi too (`pi`, then
`/login`), because your factory runs it. You're ready when `bin/doctor`
reports `Environment is ready`; then carry on from
[step 3](#3-start-your-coding-agent), starting your agent (`pi`,
`claude` or `codex`) at the repository root.

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

### Run your first factory

After you build homework 1, give every run the seed and its target, from
the repository root. The first run writes the plan, each run after that
does one task, and `--all` finishes the plan:

```sh
bin/factory --seed tetris/spec.md --target tetris/tetris-001        # write the plan
bin/factory --seed tetris/spec.md --target tetris/tetris-001        # do one task
bin/factory --seed tetris/spec.md --target tetris/tetris-001 --all  # finish the plan
npm --prefix tetris/tetris-001 start                                # play the result
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
