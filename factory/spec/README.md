# Homework 5a — Machine configuration

Read `FACTORY.md`, then the feature files in `features/`. Together they
are the whole spec of the factory at this point, not just the new parts.

Since homework 4 every machine has had a folder of its own,
`.assembly-lines/.machines/<name>/`, holding "its configuration". No
homework has said what goes in it, and your machines' prompts probably
still live in your factory's code. In homework 3 the route came out of
your code and into a line the factory reads. This homework does the same
for the machines: what a machine is for, and how it does its job, comes
out into its folder.

A machine's folder is the **configuration directory of the harness that
runs it**. Every coding agent has one, `~/.pi/agent`, `~/.claude` or
`~/.codex` when you use it yourself, and each can be pointed somewhere
else. The factory points it at the machine's folder, so the harness runs
on the machine's configuration instead of yours. The folder holds:

- **`AGENTS.md`** — the machine's instructions: what it is for, how it
  does its job, and anything it should bring to the work, such as the
  validator's lens. Whichever harness runs the machine, this is the file
  you write.
- **The rest of its configuration** — the harness that runs it (`pi`,
  unless it names another) and whatever that harness needs: its model,
  and from homework 6 its provider. The file's name and format are your
  choice. The harness's own settings files go here too, when it needs
  any.
- **Its own copy of your login** — a harness keeps its login in its
  configuration directory, so a machine needs one of its own. It
  is kept out of Git.

The factory gives each machine its own `AGENTS.md`, and no other
machine's. Change a machine's `AGENTS.md`, and the machine changes, with
no change to your code.

## What a target looks like

The format of the configuration file is yours; `machine.json` is only an
example. Here each machine runs a different harness, to show what each
one keeps:

```text
tetris/tetris-005a/
  .assembly-lines/
    careful.dot
    quick.dot
    .machines/
      planner/
        AGENTS.md
        machine.json      {"harness": "pi", "model": "<a model>"}
        auth.json         pi's login, copied in; ignored by Git
      doer/
        AGENTS.md
        CLAUDE.md         "@AGENTS.md", so Claude Code reads AGENTS.md
        machine.json      {"harness": "claude", "model": "<a model>"}
        .credentials.json Claude Code's login, copied in; ignored by Git
      validator/
        AGENTS.md
        config.toml       Codex's settings
        machine.json      {"harness": "codex", "model": "<a model>"}
        auth.json         Codex's login, copied in; ignored by Git
      reviewer_1/
        AGENTS.md         the same in all three reviewers
        machine.json      {"harness": "pi", "model": "<an Anthropic model>"}
        auth.json
      reviewer_2/ ...
      reviewer_3/ ...
      synthesiser/ ...
```

The three big brains' reviewers are configured alike apart from their
models: the same `AGENTS.md`, and a different model each.

A validator's `AGENTS.md` might read:

```markdown
# Validator

You check the doer's work on one task of a plan. You never change the
plan or the work: you only report.

Look at the work through one lens: testability. Can each part of the
code be checked on its own, without the rest of the game running?

If the work holds up, you are satisfied. If not, say why in your
findings, one finding per problem, each specific enough for the doer to
act on.
```

The lens you picked in homework 2 belongs here now, in the validator's
`AGENTS.md`, and the reviewers' lens in each reviewer's.

## Configuration, and work

A machine runs in the target, and the target is its work: the files the
machine reads and changes. That stays as it is.

What changes is where the machine's **configuration** comes from. Left
to itself, a harness also reads instruction files it finds around the
folder it runs in. Your target sits inside your capstone repository, so
a machine would pick up the repository's own `AGENTS.md`, the one that
coaches you, and any `CLAUDE.md`. It would read your own configuration
too, in your home folder. None of that is the machine's. The factory
points each harness at the machine's folder, and turns off its search
for instructions around the target. An `AGENTS.md` in the target itself
is part of the product, not the machine's instructions.

Each harness does this its own way. Each recipe below was tried with a
copied login, and with an API key instead:

| Harness | Point it at the machine's folder | Its instructions | Stop it reading other instructions | Login to copy in | Or, from the environment |
|---|---|---|---|---|---|
| pi | `PI_CODING_AGENT_DIR=<folder>` | `--append-system-prompt <folder>/AGENTS.md` | `--no-context-files` | `~/.pi/agent/auth.json` | the provider's key, such as `ANTHROPIC_API_KEY` |
| Claude Code | `CLAUDE_CONFIG_DIR=<folder>` | a `CLAUDE.md` in the folder saying `@AGENTS.md` | `--setting-sources user` | `~/.claude/.credentials.json` | `ANTHROPIC_API_KEY` |
| Codex | `CODEX_HOME=<folder>` | `AGENTS.md`, read from the folder as it is | `project_doc_max_bytes = 0` in the folder's `config.toml` | `~/.codex/auth.json` | `CODEX_API_KEY` |

For example, the planner above runs as:

```sh
PI_CODING_AGENT_DIR=<planner's folder> pi -p --no-session --no-context-files \
  --append-system-prompt <planner's folder>/AGENTS.md "<the prompt>"
```

pi's `--no-context-files` also stops it reading an `AGENTS.md` in its
own configuration directory, which is why its `AGENTS.md` is passed with
`--append-system-prompt`. Claude Code reads a `CLAUDE.md` in its
configuration directory, but not an `AGENTS.md`, so the `CLAUDE.md`
imports it.

**Antigravity (`agy`) is not supported yet.** It cannot be pointed at a
configuration of its own, and it always reads the instruction files up
to the top of your repository.

### What lands in a machine's folder

A harness writes into its configuration directory as it runs: Claude
Code and Codex keep their sessions, logs and caches there, and pi its
model cache. Only the configuration you wrote belongs in Git. One way to
keep everything else out is a `.gitignore` in each machine's folder that
ignores all but your files:

```gitignore
*
!.gitignore
!AGENTS.md
!CLAUDE.md
!config.toml
!machine.json
```

A copied ChatGPT or Claude login refreshes itself as it is used, so a
copy can stop working. If a machine says it cannot sign in, copy your
login in again, or give it an API key.

pi needs a recent Node: on Node 23.2 it can crash with
`zlib.createZstdDecompress is not a function`. Node 24 works.

## Adding a machine

Every new machine needs the same few steps. None of them is hidden in
the factory:

1. Make its folder in `.assembly-lines/.machines/`, named for the
   machine.
2. Write its `AGENTS.md`, and its configuration: which harness, which
   model.
3. Copy your login for that harness into the folder, or make sure its
   provider's API key is in the environment.
4. Check that Git ignores the login: `git check-ignore <folder>/auth.json`
   (or `.credentials.json`) should print its path.

## Once your suite passes

- Move every machine's prompt out of your factory's code and into its
  `AGENTS.md`. Search your factory's source for your validator's lens:
  it should not be there.
- Change your validator's lens by editing only its `AGENTS.md`, and
  build a generation in a fresh target. Did the findings follow?
- Run one machine on a different harness from the others, by changing
  only its folder.
