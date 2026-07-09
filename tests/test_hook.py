from __future__ import annotations

import json
from pathlib import Path

import pytest

from editbuffer.history import ToolHistoryStore
from editbuffer.hook import main, record_hook_payload


def test_codex_post_tool_use_records_failed_bash_call(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    db_path = tmp_path / "history.sqlite3"
    monkeypatch.setenv("EDITBUFFER_HISTORY_DB", str(db_path))
    payload = {
        "hook_event_name": "PostToolUse",
        "session_id": "session-codex",
        "cwd": "/repo/codex",
        "tool_name": "Bash",
        "tool_use_id": "call-1",
        "tool_input": {"command": "python - <<'PY'"},
        "tool_response": {"exit_code": 2, "stderr": "unexpected EOF"},
    }

    assert main(["--provider", "codex"], stdin_text=json.dumps(payload)) == 0

    output = json.loads(capsys.readouterr().out)
    failed = ToolHistoryStore(db_path).last_failed(
        session_id="session-codex", cwd="/repo/codex", provider="codex"
    )
    assert output == {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                "Shell call call-1 failed and was recorded. "
                "Call the editbuffer MCP tool repair_failed_command for one exact edit, "
                "then execute the returned repaired_command with Bash."
            ),
        }
    }
    assert failed["call_id"] == "call-1"
    assert failed["tool_name"] == "Bash"
    assert failed["command"] == "python - <<'PY'"
    assert failed["session_id"] == "session-codex"
    assert failed["cwd"] == "/repo/codex"
    assert failed["provider"] == "codex"
    assert failed["tool_kind"] == "shell"
    assert "unexpected EOF" in failed["error"]


def test_claude_failure_event_records_last_failed(tmp_path: Path) -> None:
    db_path = tmp_path / "history.sqlite3"
    payload = {
        "hook_event_name": "PostToolUseFailure",
        "session_id": "session-claude",
        "cwd": "/repo/claude",
        "tool_name": "Bash",
        "tool_use_id": "toolu_1",
        "tool_input": {"command": "pytest bad", "api_key": "secret-value"},
        "tool_response": {"error": "exit 1"},
    }

    result = record_hook_payload(
        payload, provider="claude", store=ToolHistoryStore(db_path)
    )

    failed = ToolHistoryStore(db_path).last_failed(
        session_id="session-claude", cwd="/repo/claude", provider="claude"
    )
    assert result["hookSpecificOutput"]["hookEventName"] == "PostToolUseFailure"
    assert "repair_failed_command" in result["hookSpecificOutput"]["additionalContext"]
    assert failed["call_id"] == "toolu_1"
    assert failed["status"] == "failed"
    assert failed["arguments"]["api_key"] == "[REDACTED]"
    assert failed["command"] == "pytest bad"


def test_goose_post_tool_use_failure_records_developer_shell(tmp_path: Path) -> None:
    db_path = tmp_path / "history.sqlite3"
    payload = {
        "eventName": "PostToolUseFailure",
        "sessionId": "session-goose",
        "workingDirectory": "/repo/goose",
        "toolName": "developer__shell",
        "toolArgs": {"command": "rg '['"},
        "toolResult": {"stderr": "regex parse error"},
        "callId": "goose-call-1",
    }

    result = record_hook_payload(
        payload, provider="goose", store=ToolHistoryStore(db_path)
    )

    failed = ToolHistoryStore(db_path).last_failed(
        session_id="session-goose", cwd="/repo/goose", provider="goose"
    )
    assert result == {}
    assert failed["call_id"] == "goose-call-1"
    assert failed["tool_name"] == "developer__shell"
    assert failed["command"] == "rg '['"
    assert "regex parse error" in failed["result_summary"]
    assert failed["tool_kind"] == "shell"


def test_successful_tool_call_is_not_last_failed(tmp_path: Path) -> None:
    store = ToolHistoryStore(tmp_path / "history.sqlite3")

    result = record_hook_payload(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "printf ok"},
            "tool_response": {"exit_code": 0, "stdout": "ok"},
        },
        provider="codex",
        store=store,
    )

    assert result == {}
    assert store.list_tool_calls()[0]["status"] == "success"
    try:
        store.last_failed()
    except KeyError as error:
        assert "no failed tool call" in str(error)
    else:
        raise AssertionError("success should not become last_failed")


def test_non_shell_command_shaped_payload_is_not_repairable(tmp_path: Path) -> None:
    store = ToolHistoryStore(tmp_path / "history.sqlite3")

    result = record_hook_payload(
        {
            "hook_event_name": "PostToolUseFailure",
            "tool_name": "Write",
            "tool_input": {"command": "this is file content"},
            "error": "write failed",
        },
        provider="claude",
        store=store,
    )

    recorded = store.list_tool_calls()[0]
    assert result == {}
    assert recorded["tool_kind"] is None
    assert recorded["command"] is None
    with pytest.raises(KeyError, match="no failed tool call"):
        store.last_failed()


def test_example_configs_only_capture_supported_shell_events() -> None:
    root = Path(__file__).parents[1] / "examples" / "hooks"
    codex = json.loads((root / "codex-hooks.json").read_text())
    claude = json.loads((root / "claude-settings.json").read_text())
    goose = json.loads((root / "goose-plugin" / "hooks" / "hooks.json").read_text())

    assert set(codex["hooks"]) == {"PostToolUse"}
    assert codex["hooks"]["PostToolUse"][0]["matcher"] == "^Bash$"
    assert set(claude["hooks"]) == {"PostToolUseFailure"}
    assert claude["hooks"]["PostToolUseFailure"][0]["matcher"] == "^Bash$"
    assert set(goose["hooks"]) == {"PostToolUseFailure"}
    assert goose["hooks"]["PostToolUseFailure"][0]["matcher"] == "^developer__shell$"
