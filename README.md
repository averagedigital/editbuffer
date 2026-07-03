# editbuffer

`editbuffer` is a small Python runtime for editing an LLM's pending text output
before it is committed.

The public abstraction is selection-based editing, not file patches:

- select exact, contextual, fuzzy, block, or character-range targets;
- replace, insert before/after, or delete the selection;
- reject missing, ambiguous, invalid, and stale selections;
- inspect the current buffer and its audit history;
- commit the final artifact.

## Install

```bash
pip install editbuffer
```

For local development:

```bash
python -m pip install -e .
```

Python 3.11+ is required. The core library has no runtime dependencies.

## Quickstart

```python
from editbuffer import EditBuffer, Selection

buf = EditBuffer()
buf.append('find . -name "*.py" -exec grep -n "TODO" {} ;')
buf.replace(Selection.exact("{} ;"), "{} \\;")

final = buf.commit()
```

Selections can also be dictionaries:

```python
buf.replace(
    {
        "type": "context",
        "before": 'grep -n "TODO" ',
        "text": "{} ;",
        "after": "",
    },
    "{} \\;",
)
```

## LLM tool-call format

```json
{
  "op": "replace",
  "target": {
    "type": "context",
    "before": "grep -n \"TODO\" ",
    "text": "{} ;",
    "after": ""
  },
  "text": "{} \\;"
}
```

Pass the decoded object to `buffer.apply(operation)`. Supported operations are
`append`, `replace`, `insert_before`, `insert_after`, and `delete`.

Range selections use half-open character offsets and can reject stale edits:

```json
{
  "op": "delete",
  "target": {
    "type": "range",
    "start": 10,
    "end": 20,
    "expected_version": 3
  }
}
```

## Failure behavior

- no match raises `TargetNotFoundError`;
- multiple matches raise `AmbiguousTargetError` with candidate ranges;
- `occurrence` can explicitly choose a zero-based match;
- invalid ranges or operations raise `InvalidOperationError`;
- a mismatched `expected_version` raises `StaleVersionError`;
- validator failures do not mutate text or history;
- fuzzy matching is opt-in and rejects low-confidence or competing candidates.

## Fuzzy and block selections

Fuzzy selection uses the standard library and records the accepted confidence:

```python
buf.replace(
    Selection.fuzzy(
        "run integrtion tests",
        threshold=0.85,
        ambiguity_margin=0.05,
    ),
    "run unit tests",
)
```

It never runs as a fallback for exact/context selection. If no candidate meets
the threshold, or two candidates are too close, `FuzzyMatchError` includes
candidate ranges and scores.

Block selection requires an explicit ID. Fenced code blocks use:

````markdown
```python editbuffer:id=setup
print("old")
```
````

Markdown regions use:

```markdown
<!-- editbuffer:block summary -->
old content
<!-- /editbuffer:block -->
```

`Selection.block("setup")` selects the content inside the markers, preserving
the fence or comments. Duplicate IDs are rejected as ambiguous.

## Snapshots and rollback

Every successful edit stores an in-memory snapshot:

```python
buf.append("draft")
version = buf.version
buf.replace(Selection.exact("draft"), "final")
buf.rollback(version)
```

Rollback restores the snapshot as a new audited version. Snapshots live only
for the lifetime of the `EditBuffer` process.

## Optional validators

```python
from editbuffer import EditBuffer
from editbuffer.validators import valid_json, valid_shell

json_buffer = EditBuffer('{"ok": true}', validators=(valid_json,))
shell_buffer = EditBuffer("echo ok", validators=(valid_shell,))
```

`valid_shell` invokes the local POSIX `sh -n` parser without executing the
command.

## CLI

The CLI stores an operation log in a JSON state file:

```bash
editbuffer new /tmp/output.json --text "hello world"
editbuffer replace /tmp/output.json '{"type":"exact","text":"world"}' "there"
editbuffer view /tmp/output.json
editbuffer history /tmp/output.json
editbuffer rollback /tmp/output.json 1
editbuffer commit /tmp/output.json
```

Use `editbuffer apply STATE OPERATION_JSON` for the complete operation schema.

## MCP / agent integration

Install the optional server:

```bash
pipx install 'editbuffer[mcp]'
```

Or install with `uvx` without a persistent environment:

```bash
uvx --from 'editbuffer[mcp]' editbuffer-mcp
```

Connect it to Codex:

```bash
codex mcp add editbuffer -- editbuffer-mcp
```

Codex supports local STDIO MCP servers configured with `codex mcp add`; use
`/mcp` in the Codex terminal UI to confirm the server is active.

Claude Desktop and generic MCP client examples are in
[`docs/mcp.md`](docs/mcp.md).

The server exposes:

- `buffer_create`
- `buffer_list`
- `buffer_view`
- `buffer_edit`
- `buffer_history`
- `buffer_rollback`
- `buffer_commit`
- `command_history`
- `command_select`

Buffers are in-memory and live for the MCP server process. The MCP layer calls
the same core API and does not implement separate edit semantics.

`buffer_commit` remembers non-empty committed output as a reusable command.
`command_history` returns the last 10 commands, newest first. `command_select`
creates a new pending buffer from a previous command so the model can reuse it
instead of regenerating it.

## Examples

- [`examples/shell_repair.py`](examples/shell_repair.py)
- [`examples/json_repair.py`](examples/json_repair.py)
- [`examples/chat_restructure.py`](examples/chat_restructure.py)

## Scope

This project is not:

- an agent framework;
- a retrieval system or repo indexer;
- a full IDE;
- a replacement for coding agents;
- a generic output quality evaluator.

Persistent storage, atomic operation batches, TypeScript bindings, and
syntax-aware block parsing are future work.

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## License

MIT
