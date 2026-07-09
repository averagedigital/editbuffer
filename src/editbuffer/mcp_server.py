from __future__ import annotations

import os
from importlib import import_module
from pathlib import Path
from typing import Any

from .buffer import EditBuffer
from .errors import AmbiguousTargetError, EditBufferError, TargetNotFoundError
from .history import ToolHistoryStore


class BufferRegistry:
    def __init__(
        self,
        history_store: ToolHistoryStore | None = None,
        *,
        session_id: str | None = None,
        cwd: str | Path | None = None,
        provider: str | None = None,
    ) -> None:
        self._history_store = history_store or ToolHistoryStore()
        self._scope = {
            key: value
            for key, value in {
                "session_id": session_id,
                "cwd": str(cwd) if cwd is not None else None,
                "provider": provider,
            }.items()
            if value is not None
        }

    def repair_failed_command(
        self,
        old_text: str,
        new_text: str,
        *,
        call_id: str | None = None,
    ) -> dict[str, Any]:
        if not old_text:
            raise ValueError("old_text must not be empty")
        source = self._source(call_id)
        if source["status"] != "failed":
            raise ValueError(f"tool call is not failed: {source['call_id']}")
        try:
            command = self._history_store.get_command(source["call_id"], **self._scope)
        except KeyError as error:
            raise ValueError(
                f"tool call is not a shell command: {source['call_id']}"
            ) from error
        buffer = EditBuffer(command)
        record = buffer.replace(
            {"type": "exact", "text": old_text},
            new_text,
        )
        return {
            "ok": True,
            "source_call_id": source["call_id"],
            "original_command": command,
            "repaired_command": buffer.view(),
            "replacement": {"start": record.start, "end": record.end},
        }

    def _source(self, call_id: str | None) -> dict[str, Any]:
        if call_id is None:
            return self._history_store.last_failed(**self._scope)
        return self._history_store.get_tool_call(call_id, **self._scope)


def create_server() -> Any:
    try:
        FastMCP = import_module("mcp.server.fastmcp").FastMCP
    except ImportError as error:
        raise RuntimeError(
            "MCP support is not installed; run: pip install 'editbuffer[mcp]'"
        ) from error

    registry = BufferRegistry(
        session_id=os.environ.get("EDITBUFFER_SESSION_ID"),
        cwd=os.environ.get("EDITBUFFER_CWD") or Path.cwd(),
        provider=os.environ.get("EDITBUFFER_PROVIDER"),
    )
    server = FastMCP(
        "editbuffer",
        instructions=(
            "After a shell failure, call repair_failed_command for one exact edit. "
            "The tool never executes commands. Run its repaired_command with the host "
            "shell tool."
        ),
        json_response=True,
    )

    @server.tool()
    def repair_failed_command(
        old_text: str,
        new_text: str,
        call_id: str | None = None,
    ) -> dict[str, Any]:
        """Prepare one exact edit to a failed shell command without executing it.

        Without call_id, edits the latest failed shell command in the current scope.
        Execute the returned repaired_command with the host shell tool.
        """
        return _tool_result(
            lambda: registry.repair_failed_command(
                old_text,
                new_text,
                call_id=call_id,
            ),
        )

    return server


def _tool_result(
    call: Any,
) -> Any:
    try:
        return call()
    except (EditBufferError, KeyError, ValueError) as error:
        return {
            "ok": False,
            "error": _structured_error(error),
        }


def _structured_error(error: Exception) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": _error_type(error),
        "message": _message(error),
    }
    if isinstance(error, AmbiguousTargetError):
        payload["candidates"] = [list(candidate) for candidate in error.candidates]
    return payload


def _error_type(error: Exception) -> str:
    if isinstance(error, AmbiguousTargetError):
        return "ambiguous_target"
    if isinstance(error, TargetNotFoundError):
        return "target_not_found"
    if isinstance(error, KeyError):
        message = _message(error)
        if message.startswith("unknown tool call:"):
            return "unknown_tool_call"
        if message.startswith("no failed tool call"):
            return "no_failed_tool_call"
        return "not_found"
    if isinstance(error, ValueError):
        message = _message(error)
        if message.startswith("tool call is not a shell command:"):
            return "not_shell_command"
        if message.startswith("tool call is not failed:"):
            return "call_not_failed"
        return "invalid_input"
    return "editbuffer_error"


def _message(error: Exception) -> str:
    if isinstance(error, KeyError) and error.args:
        return str(error.args[0])
    return str(error)


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
