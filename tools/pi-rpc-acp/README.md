# pi-rpc-acp

From homework 6 your factory runs each machine as an ACP agent: it speaks
the [Agent Client Protocol](https://agentclientprotocol.com) to it over
stdio. Claude Code and Codex have ACP adapters (`claude-agent-acp` and
`codex-acp`). This is the one for pi: a small bridge from ACP to pi's RPC
mode, `pi --mode rpc`. It needs only Node and pi.

Use it as a machine's harness, with any pi arguments after it:

```sh
pi-rpc-acp --model sonnet
```

It gives the factory what it needs from a machine:

- what pi generates, as `agent_message_chunk` updates;
- the files pi reads, as tool calls whose `locations` name them;
- what pi spent, as `usage` on the `session/prompt` response
  (`inputTokens`, `outputTokens`, …), as the Claude Code and Codex
  adapters send it;
- `_session/steering`, as those adapters accept it, passed on to pi's
  `steer`;
- `session/cancel`, passed on to pi's `abort`.

Not yet: MCP servers named in `session/new`. pi has no MCP of its own, so
homework 8's `run_command` tool does not reach pi through this bridge.

pi's RPC mode needs a Node with zstd support: 22.15 or later, or 23.8 or
later. The devcontainer's Node 24 is fine.
