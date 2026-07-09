# MCP client setup

`editbuffer-mcp` is a local STDIO MCP server backed by the same SQLite history
as `editbuffer-hook`.

Install the MCP extra:

```bash
pipx install 'editbuffer[mcp]'
```

Or run it with `uvx`:

```bash
uvx --from 'editbuffer[mcp]' editbuffer-mcp
```

## Codex

Add the server:

```bash
codex mcp add editbuffer -- editbuffer-mcp
```

Start a new Codex session and check `/mcp` for `editbuffer`.

## Claude Desktop

Add this to the Claude Desktop MCP config file:

```json
{
  "mcpServers": {
    "editbuffer": {
      "command": "editbuffer-mcp",
      "args": []
    }
  }
}
```

If `editbuffer-mcp` is not on Claude Desktop's `PATH`, use the absolute path
reported by `which editbuffer-mcp`.

## Generic MCP clients

Use STDIO transport with command `editbuffer-mcp` and no arguments.

The server exposes one tool:

- `repair_failed_command`

Input:

```json
{
  "old_text": "--bad-flag",
  "new_text": "--good-flag",
  "call_id": "optional-failed-call-id"
}
```

`old_text` must occur exactly once. `call_id` is optional; without it, the tool
uses the latest failed shell call in the current scope.

Output:

```json
{
  "ok": true,
  "source_call_id": "call-...",
  "original_command": "pytest --bad-flag",
  "repaired_command": "pytest --good-flag",
  "replacement": {"start": 7, "end": 17}
}
```

The server does not execute commands. Run `repaired_command` with the host
agent's shell tool. Missing or repeated `old_text`, unknown calls, successful
calls, and non-shell calls return structured error envelopes.

## History scope

`editbuffer-mcp` scopes implicit lookup by `EDITBUFFER_CWD`, or by its process
working directory when that variable is unset. Optional
`EDITBUFFER_SESSION_ID` and `EDITBUFFER_PROVIDER` narrow the scope further.

The hook records `session_id`, `cwd`, provider, tool kind, and call id when the
host payload supplies them. Both processes use `EDITBUFFER_HISTORY_DB`, which
defaults to `~/.editbuffer/history.sqlite3`.

## Host hooks

Install the package so `editbuffer-hook` is on the host's `PATH`, then adapt one
of the configs in `examples/hooks`.

| Host | Event | Matcher | Model feedback |
| --- | --- | --- | --- |
| Codex | `PostToolUse` | `^Bash$` | `additionalContext` after detected failure |
| Claude Code | `PostToolUseFailure` | `^Bash$` | `additionalContext` |
| goose 1.35+ | `PostToolUseFailure` | `^developer__shell$` | none; capture only |

Host contracts: [Codex hooks](https://developers.openai.com/codex/hooks),
[Claude Code hooks](https://code.claude.com/docs/en/hooks), and the
[goose 1.35.0 release](https://github.com/aaif-goose/goose/releases/tag/v1.35.0).

Codex reports non-zero Bash exits through `PostToolUse`; it does not expose a
separate failure event. Its current hook interception does not cover every
`unified_exec` path, so this adapter must not be described as universal shell
capture.

Claude Code has a dedicated failure event and a documented
`hookSpecificOutput.additionalContext` response.

The goose adapter intentionally prints `{}` after recording. Current goose
releases expose hooks, but this project does not assume a model-feedback output
contract without a verified host-level test.

The hook ignores command-shaped fields on non-shell tools, so file or MCP
payloads cannot become repair targets.

## Limits

- No authentication or network server mode.
- No concurrent multi-client coordination.
- No command execution or replay inside the MCP server.
- No fuzzy repair; ambiguity is an explicit error.
- No universal capture outside the documented host hook events.
