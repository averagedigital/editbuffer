from __future__ import annotations

from importlib import import_module
from typing import Any
from uuid import uuid4

from .buffer import EditBuffer
from .history import EditRecord


class BufferRegistry:
    def __init__(self) -> None:
        self._buffers: dict[str, EditBuffer] = {}

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
        return self._state(buffer_id, buffer)

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
        return registry.create(content, buffer_id=buffer_id)

    @server.tool()
    def buffer_list() -> list[dict[str, Any]]:
        """List active pending output buffers."""
        return registry.list_buffers()

    @server.tool()
    def buffer_view(buffer_id: str) -> dict[str, Any]:
        """View current content, version, snapshots, and commit state."""
        return registry.view(buffer_id)

    @server.tool()
    def buffer_edit(
        buffer_id: str,
        operation: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply one JSON edit operation.

        Operations: append, replace, insert_before, insert_after, delete, rollback.
        Targets: exact/context/range; fuzzy requires threshold and ambiguity_margin;
        block requires an explicit block_id. Ambiguous edits fail without mutation.
        """
        return registry.edit(buffer_id, operation)

    @server.tool()
    def buffer_history(buffer_id: str) -> list[dict[str, Any]]:
        """Return the audit trail for successful edits."""
        return registry.history(buffer_id)

    @server.tool()
    def buffer_rollback(buffer_id: str, version: int) -> dict[str, Any]:
        """Restore a prior snapshot as a new audited version."""
        return registry.rollback(buffer_id, version)

    @server.tool()
    def buffer_commit(buffer_id: str) -> dict[str, Any]:
        """Commit final output and close the buffer to further edits."""
        return registry.commit(buffer_id)

    return server


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
