from __future__ import annotations

from importlib import import_module
from typing import Any
from uuid import uuid4

from .buffer import EditBuffer
from .errors import (
    AmbiguousTargetError,
    EditBufferError,
    FuzzyMatchError,
    InvalidOperationError,
    StaleVersionError,
    TargetNotFoundError,
)
from .history import EditRecord


class BufferRegistry:
    def __init__(self) -> None:
        self._buffers: dict[str, EditBuffer] = {}
        self._commands: list[dict[str, Any]] = []
        self._next_command_number = 1

    def create(
        self,
        content: str = "",
        *,
        buffer_id: str | None = None,
    ) -> dict[str, Any]:
        identifier = buffer_id or uuid4().hex
        if identifier in self._buffers:
            raise ValueError(f"buffer already exists: {identifier}")
        self._buffers[identifier] = EditBuffer(content)
        return self.view(identifier)

    def list_buffers(self) -> list[dict[str, Any]]:
        return [
            self._state(identifier, buffer)
            for identifier, buffer in self._buffers.items()
        ]

    def view(self, buffer_id: str) -> dict[str, Any]:
        return self._state(buffer_id, self._get(buffer_id))

    def edit(self, buffer_id: str, operation: dict[str, Any]) -> dict[str, Any]:
        buffer = self._get(buffer_id)
        record = buffer.apply(operation)
        result = self._state(buffer_id, buffer)
        result["applied"] = _record(record)
        return result

    def history(self, buffer_id: str) -> list[dict[str, Any]]:
        return [_record(record) for record in self._get(buffer_id).history]

    def rollback(self, buffer_id: str, version: int) -> dict[str, Any]:
        buffer = self._get(buffer_id)
        record = buffer.rollback(version)
        result = self._state(buffer_id, buffer)
        result["applied"] = _record(record)
        return result

    def commit(self, buffer_id: str) -> dict[str, Any]:
        buffer = self._get(buffer_id)
        buffer.commit()
        self._remember_command(buffer.view())
        return self._state(buffer_id, buffer)

    def command_history(self) -> list[dict[str, Any]]:
        return list(self._commands)

    def current_version(self, buffer_id: str | None) -> int | None:
        if buffer_id is None:
            return None
        buffer = self._buffers.get(buffer_id)
        return None if buffer is None else buffer.version

    def select_command(
        self,
        command_id: str,
        *,
        buffer_id: str | None = None,
    ) -> dict[str, Any]:
        for item in self._commands:
            if item["command_id"] == command_id:
                return self.create(item["command"], buffer_id=buffer_id)
        raise KeyError(f"unknown command: {command_id}")

    def _get(self, buffer_id: str) -> EditBuffer:
        try:
            return self._buffers[buffer_id]
        except KeyError as error:
            raise KeyError(f"unknown buffer: {buffer_id}") from error

    def _state(self, buffer_id: str, buffer: EditBuffer) -> dict[str, Any]:
        return {
            "buffer_id": buffer_id,
            "content": buffer.view(),
            "version": buffer.version,
            "versions": list(buffer.versions),
            "committed": buffer.committed,
        }

    def _remember_command(self, command: str) -> None:
        if not command.strip():
            return
        self._commands.insert(
            0,
            {
                "command_id": f"cmd-{self._next_command_number}",
                "command": command,
            },
        )
        self._next_command_number += 1
        del self._commands[10:]


def _record(record: EditRecord) -> dict[str, Any]:
    return {
        "operation": record.operation.as_dict(),
        "start": record.start,
        "end": record.end,
        "before": record.before,
        "after": record.after,
        "version_before": record.version_before,
        "version_after": record.version_after,
        "confidence": record.confidence,
    }


def create_server() -> Any:
    try:
        FastMCP = import_module("mcp.server.fastmcp").FastMCP
    except ImportError as error:
        raise RuntimeError(
            "MCP support is not installed; run: pip install 'editbuffer[mcp]'"
        ) from error

    registry = BufferRegistry()
    server = FastMCP(
        "editbuffer",
        instructions=(
            "Use editbuffer for pending output that may need local corrections before "
            "commit. Create one buffer, apply small selection-based edits, view when "
            "needed, and commit only when final. Never retry ambiguous fuzzy edits "
            "without narrowing the selection."
        ),
        json_response=True,
    )

    @server.tool()
    def buffer_create(
        content: str = "",
        buffer_id: str | None = None,
    ) -> dict[str, Any]:
        """Create an in-memory pending output buffer."""
        return _tool_result(
            lambda: registry.create(content, buffer_id=buffer_id),
            registry,
            buffer_id=buffer_id,
        )

    @server.tool()
    def buffer_list() -> list[dict[str, Any]]:
        """List active pending output buffers."""
        return registry.list_buffers()

    @server.tool()
    def buffer_view(buffer_id: str) -> dict[str, Any]:
        """View current content, version, snapshots, and commit state."""
        return _tool_result(lambda: registry.view(buffer_id), registry, buffer_id=buffer_id)

    @server.tool()
    def buffer_edit(
        buffer_id: str,
        operation: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply one JSON edit operation.

        Example replace operation:
        {"op": "replace", "target": {"type": "exact", "text": "old"}, "text": "new"}
        Operations: append, replace, insert_before, insert_after, delete, rollback.
        Targets: exact/context/range/fuzzy/block. Ambiguous edits fail without mutation.
        """
        return _tool_result(
            lambda: registry.edit(buffer_id, operation),
            registry,
            buffer_id=buffer_id,
        )

    @server.tool()
    def buffer_append(buffer_id: str, text: str) -> dict[str, Any]:
        """Append text to a pending buffer."""
        return _tool_result(
            lambda: registry.edit(buffer_id, {"op": "append", "text": text}),
            registry,
            buffer_id=buffer_id,
        )

    @server.tool()
    def buffer_replace(
        buffer_id: str,
        target: dict[str, Any],
        text: str,
    ) -> dict[str, Any]:
        """Replace a selection with text. Target can be exact/context/range/fuzzy/block."""
        return _selection_tool(registry, buffer_id, "replace", target, text)

    @server.tool()
    def buffer_insert_before(
        buffer_id: str,
        target: dict[str, Any],
        text: str,
    ) -> dict[str, Any]:
        """Insert text before a selection. Target can be exact/context/range/fuzzy/block."""
        return _selection_tool(registry, buffer_id, "insert_before", target, text)

    @server.tool()
    def buffer_insert_after(
        buffer_id: str,
        target: dict[str, Any],
        text: str,
    ) -> dict[str, Any]:
        """Insert text after a selection. Target can be exact/context/range/fuzzy/block."""
        return _selection_tool(registry, buffer_id, "insert_after", target, text)

    @server.tool()
    def buffer_delete(buffer_id: str, target: dict[str, Any]) -> dict[str, Any]:
        """Delete a selection. Target can be exact/context/range/fuzzy/block."""
        return _tool_result(
            lambda: registry.edit(buffer_id, {"op": "delete", "target": target}),
            registry,
            buffer_id=buffer_id,
        )

    @server.tool()
    def buffer_history(buffer_id: str) -> list[dict[str, Any]]:
        """Return the audit trail for successful edits."""
        return _tool_result(
            lambda: registry.history(buffer_id),
            registry,
            buffer_id=buffer_id,
        )

    @server.tool()
    def buffer_rollback(buffer_id: str, version: int) -> dict[str, Any]:
        """Restore a prior snapshot as a new audited version."""
        return _tool_result(
            lambda: registry.rollback(buffer_id, version),
            registry,
            buffer_id=buffer_id,
        )

    @server.tool()
    def buffer_commit(buffer_id: str) -> dict[str, Any]:
        """Commit final output, close the buffer, and remember it as a reusable command."""
        return _tool_result(lambda: registry.commit(buffer_id), registry, buffer_id=buffer_id)

    @server.tool()
    def command_history() -> list[dict[str, Any]]:
        """Return up to 10 most recently committed commands, newest first."""
        return registry.command_history()

    @server.tool()
    def command_select(
        command_id: str,
        buffer_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new pending buffer from a previous command instead of regenerating it."""
        return _tool_result(
            lambda: registry.select_command(command_id, buffer_id=buffer_id),
            registry,
            buffer_id=buffer_id,
        )

    return server


def _selection_tool(
    registry: BufferRegistry,
    buffer_id: str,
    op: str,
    target: dict[str, Any],
    text: str,
) -> dict[str, Any]:
    return _tool_result(
        lambda: registry.edit(buffer_id, {"op": op, "target": target, "text": text}),
        registry,
        buffer_id=buffer_id,
    )


def _tool_result(
    call: Any,
    registry: BufferRegistry,
    *,
    buffer_id: str | None = None,
) -> Any:
    try:
        return call()
    except (EditBufferError, KeyError, ValueError) as error:
        return {
            "ok": False,
            "error": _structured_error(
                error,
                current_version=registry.current_version(buffer_id),
            ),
        }


def _structured_error(
    error: Exception,
    *,
    current_version: int | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": _error_type(error),
        "message": _message(error),
    }
    if current_version is not None:
        payload["current_version"] = current_version
    if isinstance(error, AmbiguousTargetError):
        payload["candidates"] = [list(candidate) for candidate in error.candidates]
    if isinstance(error, FuzzyMatchError):
        payload["reason"] = error.reason
        payload["candidates"] = [list(candidate) for candidate in error.candidates]
    return payload


def _error_type(error: Exception) -> str:
    if isinstance(error, TargetNotFoundError):
        return "target_not_found"
    if isinstance(error, AmbiguousTargetError):
        return "ambiguous_target"
    if isinstance(error, FuzzyMatchError):
        return "fuzzy_match"
    if isinstance(error, StaleVersionError):
        return "stale_version"
    if isinstance(error, InvalidOperationError):
        return "invalid_operation"
    if isinstance(error, KeyError):
        message = _message(error)
        if message.startswith("unknown buffer:"):
            return "unknown_buffer"
        if message.startswith("unknown command:"):
            return "unknown_command"
        return "not_found"
    if isinstance(error, ValueError):
        message = _message(error)
        if message.startswith("buffer already exists:"):
            return "duplicate_buffer"
        return "invalid_value"
    return "editbuffer_error"


def _message(error: Exception) -> str:
    if isinstance(error, KeyError) and error.args:
        return str(error.args[0])
    return str(error)


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
