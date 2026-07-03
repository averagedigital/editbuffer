# MCP client setup

`editbuffer-mcp` is a local STDIO MCP server. It keeps buffers in memory, so
buffers exist only while that server process is running.

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

The server exposes these tools:

- `buffer_create`
- `buffer_list`
- `buffer_view`
- `buffer_edit`
- `buffer_history`
- `buffer_rollback`
- `buffer_commit`
- `command_history`
- `command_select`

Use `buffer_edit` with JSON operations such as:

```json
{
  "op": "replace",
  "target": {
    "type": "context",
    "before": "return ",
    "text": "old_value",
    "after": "\n"
  },
  "text": "new_value"
}
```

Errors are intentional recovery signals. Missing, ambiguous, stale, invalid, or
unsafe fuzzy selections fail without mutating the buffer.

Committed non-empty buffers are remembered as recent commands:

```json
[
  {
    "command_id": "cmd-3",
    "command": "pytest tests/test_mcp_server.py"
  }
]
```

Use `command_select` with a `command_id` to create a new pending buffer from an
old command instead of generating it again. Only the last 10 commands are kept,
newest first.

## Limits

- No persistence across MCP server restarts.
- No authentication or network server mode.
- No concurrent multi-client coordination.
- No batch transaction API.
- Fuzzy selection is opt-in and may reject close candidates.
