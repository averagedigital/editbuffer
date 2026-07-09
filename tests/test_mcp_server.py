from pathlib import Path

import pytest

from editbuffer.history import ToolHistoryStore
from editbuffer.mcp_server import BufferRegistry


def test_prepare_repair_returns_command_without_executing(tmp_path: Path) -> None:
    output = tmp_path / "must-not-exist.txt"
    store = ToolHistoryStore(tmp_path / "history.sqlite3")
    failed_id = store.record_tool_call(
        "exec_command",
        {"cmd": f"printf broken > {output}"},
        tool_kind="shell",
        status="failed",
    )
    registry = BufferRegistry(history_store=store)

    result = registry.repair_failed_command("broken", "fixed")

    assert result == {
        "ok": True,
        "source_call_id": failed_id,
        "original_command": f"printf broken > {output}",
        "repaired_command": f"printf fixed > {output}",
        "replacement": {"start": 7, "end": 13},
    }
    assert not output.exists()
    assert len(store.list_tool_calls()) == 1


def test_prepare_repair_uses_call_id_within_scope(tmp_path: Path) -> None:
    store = ToolHistoryStore(tmp_path / "history.sqlite3")
    call_id = store.record_tool_call(
        "exec_command",
        {"cmd": "pytest old"},
        tool_kind="shell",
        session_id="session-a",
        cwd="/repo/a",
        status="failed",
    )
    registry = BufferRegistry(
        history_store=store,
        session_id="session-a",
        cwd="/repo/a",
    )

    result = registry.repair_failed_command("old", "new", call_id=call_id)

    assert result["repaired_command"] == "pytest new"


def test_prepare_repair_rejects_call_from_another_scope(tmp_path: Path) -> None:
    store = ToolHistoryStore(tmp_path / "history.sqlite3")
    call_id = store.record_tool_call(
        "exec_command",
        {"cmd": "pytest old"},
        tool_kind="shell",
        session_id="session-b",
        cwd="/repo/a",
        status="failed",
    )
    registry = BufferRegistry(
        history_store=store,
        session_id="session-a",
        cwd="/repo/a",
    )

    with pytest.raises(KeyError, match="unknown tool call"):
        registry.repair_failed_command("old", "new", call_id=call_id)


def test_prepare_repair_rejects_non_shell_and_successful_calls(tmp_path: Path) -> None:
    store = ToolHistoryStore(tmp_path / "history.sqlite3")
    non_shell_id = store.record_tool_call(
        "write_file",
        {"command": "not shell"},
        tool_kind="file",
        status="failed",
    )
    success_id = store.record_tool_call(
        "exec_command",
        {"cmd": "echo ok"},
        tool_kind="shell",
        status="success",
    )
    registry = BufferRegistry(history_store=store)

    with pytest.raises(ValueError, match="not a shell command"):
        registry.repair_failed_command("not", "is", call_id=non_shell_id)
    with pytest.raises(ValueError, match="is not failed"):
        registry.repair_failed_command("ok", "fine", call_id=success_id)


def test_prepare_repair_requires_non_empty_exact_target(tmp_path: Path) -> None:
    registry = BufferRegistry(
        history_store=ToolHistoryStore(tmp_path / "history.sqlite3")
    )

    with pytest.raises(ValueError, match="old_text must not be empty"):
        registry.repair_failed_command("", "new")
