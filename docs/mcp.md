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

- `buffer_append`
- `buffer_list`
- `buffer_view`
- `buffer_edit`
- `buffer_replace`
- `buffer_insert_before`
- `buffer_insert_after`
- `buffer_delete`
- `buffer_history`
- `buffer_rollback`
- `buffer_commit`
- `tool_history`
- `tool_select`
- `last_failed`
- `select_last_failed`
- `edit_last_failed`

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

For normal agent use, prefer the explicit selection tools:

- `buffer_replace`
- `buffer_insert_before`
- `buffer_insert_after`
- `buffer_delete`

They take `buffer_id`, `target`, and, except delete, `text`.

Errors are intentional recovery signals. Missing, ambiguous, stale, invalid, or
unsafe fuzzy selections fail without mutating the buffer.

Editbuffer MCP calls are recorded in SQLite-backed history:

```json
[
  {
    "call_id": "call-...",
    "tool_name": "buffer_edit",
    "status": "success"
  }
]
```

Use `tool_select` with a `call_id` to create a new pending buffer from selectable
content in an old call instead of generating it again. Use `select_last_failed`
or `edit_last_failed` to repair the most recent failed recorded call directly.
By default `tool_history` returns the last 10 calls, newest first.

## Limits

- No persistence across MCP server restarts.
- No authentication or network server mode.
- No concurrent multi-client coordination.
- No batch transaction API.
- Fuzzy selection is opt-in and may reject close candidates.
