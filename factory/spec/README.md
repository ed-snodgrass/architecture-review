# Homework 6 — Watching

Read `FACTORY.md`, then the feature files in `features/`. Together they
are the whole spec of the factory at this point, not just the new parts.

Homework 5a, machine configuration, was added after homework 5. If you
haven't done it, sync your fork on GitHub, set `factory/ITERATION` to
`005 Done`, and say "fetch iteration": you'll get 5a, and this homework
after it. 5a makes each machine's folder its harness's configuration,
with its own instructions and its own copy of your login.

The factory builds the same software it built for homework 5. What is new
is that you can watch it: what every machine generates, and what every
machine costs.

This is where your factory stops being something you run and becomes
something that is running. You start a run and get your terminal back.
Watching is a separate command that attaches to a run in flight. How it
attaches — a socket, a pipe, a file the daemon appends to, an HTTP
endpoint — is yours to choose.

## Your machines speak ACP

Until now each machine was one call: a prompt in, an answer out. To watch
a machine as it works, and see what it spends, the factory now runs each
one as an ACP agent — the [Agent Client
Protocol](https://agentclientprotocol.com), JSON-RPC over the machine's
stdin and stdout — and is itself the ACP client. A machine's harness is
an ACP agent from here on:

- Claude Code: `claude-agent-acp` (npm `@agentclientprotocol/claude-agent-acp`)
- Codex: `codex-acp` (npm `@agentclientprotocol/codex-acp`)
- pi: `pi-rpc-acp`, the small bridge over pi's RPC mode in your starter
  repo

What the factory reads: the `agent_message_chunk` updates, as what the
machine generates; the last line of that text, as its result; and the
`usage` on its `session/prompt` response — `inputTokens` and
`outputTokens` — as what it spent. That usage is still a draft in ACP,
but the Claude Code and Codex adapters send it, and so does the pi
bridge.

Which ACP agent runs a machine, with which model, stays in the machine's
configuration, and so does the model's provider, which the token totals
follow. The machine's folder is still its harness's configuration, with
its `AGENTS.md` and its own login. Each ACP agent runs on the folder
much as its harness did in homework 5a:

| ACP agent | Point it at the machine's folder | Its instructions, and nothing else |
|---|---|---|
| `pi-rpc-acp` | `PI_CODING_AGENT_DIR=<folder>` in its environment | arguments passed on to pi: `--no-context-files --append-system-prompt <folder>/AGENTS.md` |
| `claude-agent-acp` | `CLAUDE_CONFIG_DIR=<folder>` in its environment | the folder's `CLAUDE.md` saying `@AGENTS.md`, and `"_meta": {"claudeCode": {"options": {"settingSources": ["user"]}}}` in `session/new` |
| `codex-acp` | `CODEX_HOME=<folder>` in its environment | the folder's `AGENTS.md`, and `project_doc_max_bytes = 0` in its `config.toml` |

Without that `_meta`, `claude-agent-acp` also reads the `CLAUDE.md` and
`AGENTS.md` files around the target. Antigravity has no ACP agent, and is
not supported.

## The commands you'll end up with

Run these commands from the repository root, through `bin/factory`:

```sh
# start a run — you get your terminal back
$ bin/factory --run tetris --target tetris/tetris-002 --line careful --seed tetris/spec.md
started run tetris

# attach to it, now or later — catches you up, then follows live
$ bin/factory watch tetris
planner    | ...
doer       | ...
tokens     doer 12.4k in / 3.1k out   anthropic 15.5k   google 4.2k   openai 3.9k   run 23.6k

# a second run while one is running is refused
$ bin/factory --run snake --target snake/snake1 --line quick --seed snake/spec.md
refused: run tetris is running

# stop the run (the factory stays up); start it again later by name alone
$ bin/factory stop tetris
$ bin/factory --run tetris

# stop the factory itself — its run stops with it
$ bin/factory stop
```

Before you start, look at what your factory does today. It probably
prints as it goes, and printing is not this: it is gone when the
scrollback is gone, and it belongs to the terminal that started the run.
A record you can attach to late, catch up on, and still read tomorrow is
a different piece of machinery.

## Your doubles speak ACP too

Your test doubles, which used to replace machines, now replace "machines that communicate via ACP".
