import json
import sqlite3
from pathlib import Path

import pytest

from editbuffer.history import ToolHistoryStore


def test_history_context_round_trips_and_scopes_reads(tmp_path: Path) -> None:
    store = ToolHistoryStore(tmp_path / "history.sqlite3")
    call_id = store.record_tool_call(
        "exec_command",
        {"cmd": "echo ok"},
        tool_kind="shell",
        session_id="session-a",
        cwd="/repo/a",
        provider="codex",
    )

    item = store.get_tool_call(call_id, session_id="session-a", cwd="/repo/a")

    assert item["session_id"] == "session-a"
    assert item["cwd"] == "/repo/a"
    assert item["provider"] == "codex"
    assert item["tool_kind"] == "shell"
    assert store.list_tool_calls(session_id="session-b") == []
    with pytest.raises(KeyError, match="unknown tool call"):
        store.get_tool_call(call_id, session_id="session-b")


def test_last_failed_keeps_root_shell_call_after_failed_repair(tmp_path: Path) -> None:
    store = ToolHistoryStore(tmp_path / "history.sqlite3")
    source_id = store.record_tool_call(
        "exec_command",
        {"cmd": "bad original"},
        command="bad original",
        tool_kind="shell",
        session_id="session-a",
        cwd="/repo/a",
        status="failed",
    )
    store.record_tool_call(
        "repair_command",
        {"command": "still broken"},
        command="still broken",
        tool_kind="shell",
        parent_call_id=source_id,
        session_id="session-a",
        cwd="/repo/a",
        status="failed",
    )
    store.record_tool_call(
        "exec_command",
        {"cmd": "other session failure"},
        command="other session failure",
        tool_kind="shell",
        session_id="session-b",
        cwd="/repo/a",
        status="failed",
    )

    failed = store.last_failed(session_id="session-a", cwd="/repo/a")

    assert failed["call_id"] == source_id
    assert failed["command"] == "bad original"
    assert failed["parent_call_id"] is None


def test_non_shell_command_field_is_never_available_for_replay(tmp_path: Path) -> None:
    store = ToolHistoryStore(tmp_path / "history.sqlite3")
    call_id = store.record_tool_call(
        "write_file",
        {"command": "not a shell command"},
        tool_kind="file",
        status="failed",
    )

    assert store.get_tool_call(call_id)["command"] is None
    assert store.command_history() == []
    with pytest.raises(KeyError, match="unknown command"):
        store.get_command(call_id)
    with pytest.raises(KeyError, match="no failed tool call"):
        store.last_failed()


def test_secret_like_command_values_are_redacted_from_history(tmp_path: Path) -> None:
    store = ToolHistoryStore(tmp_path / "history.sqlite3")
    call_id = store.record_tool_call(
        "exec_command",
        {
            "cmd": (
                "API_TOKEN=top-secret-value curl "
                "'https://example.invalid?password=query-secret' "
                "-H 'Authorization: Bearer bearer-secret'"
            )
        },
        tool_kind="shell",
    )

    serialized = json.dumps(store.get_tool_call(call_id), sort_keys=True)

    assert "top-secret-value" not in serialized
    assert "query-secret" not in serialized
    assert "bearer-secret" not in serialized
    assert "[REDACTED]" in serialized


def test_existing_history_database_is_migrated_in_place(tmp_path: Path) -> None:
    db_path = tmp_path / "history.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            CREATE TABLE tool_calls (
                call_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                arguments_json TEXT NOT NULL,
                result_json TEXT,
                result_summary TEXT,
                status TEXT NOT NULL,
                error TEXT,
                content TEXT,
                command TEXT
            )
            """
        )
        db.execute(
            """
            INSERT INTO tool_calls VALUES (
                'legacy-call', '2099-01-01T00:00:00+00:00', 'shell', '{}', NULL,
                NULL, 'failed', 'exit 1', 'legacy command', 'legacy command'
            )
            """
        )

    store = ToolHistoryStore(db_path)
    new_id = store.record_tool_call(
        "exec_command",
        {"cmd": "new command"},
        tool_kind="shell",
        session_id="session-a",
    )

    assert store.get_tool_call("legacy-call")["command"] == "legacy command"
    assert store.get_tool_call(new_id)["session_id"] == "session-a"


@pytest.mark.parametrize("limit", [0, 6])
def test_command_history_rejects_limits_outside_model_facing_range(
    tmp_path: Path, limit: int
) -> None:
    store = ToolHistoryStore(tmp_path / "history.sqlite3")

    with pytest.raises(ValueError, match="between 1 and 5"):
        store.command_history(limit)
