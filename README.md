# editbuffer

`editbuffer` is a small Python runtime for editing an LLM's pending text output
before it is committed.

The public abstraction is selection-based editing, not file patches:

- select exact text, contextual text, or a character range;
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

Python 3.11+ is required. The library has no runtime dependencies.

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
- fuzzy matching is not performed.

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
editbuffer commit /tmp/output.json
```

Use `editbuffer apply STATE OPERATION_JSON` for the complete operation schema.

## MCP / agent integration

Expose one buffer per pending artifact and map a host tool call directly to
`EditBuffer.apply()`. The tool input is the JSON operation object shown above;
the tool result should return `view()`, `version`, and typed errors. Buffer
storage, authentication, and artifact commit destinations belong to the host.

A full MCP server is intentionally not included in v1.

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

Fuzzy selection, block IDs, persistent rollback, atomic operation batches,
TypeScript bindings, and an MCP server are future work.

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## License

MIT
