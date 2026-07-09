from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .history import ToolHistoryStore, is_shell_tool


FAILURE_EVENTS = {"posttoolusefailure", "permissiondenied"}
COMMAND_KEYS = ("command", "command_line", "cmd")


def main(argv: list[str] | None = None, *, stdin_text: str | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider", choices=["codex", "claude", "goose"], default="codex"
    )
    args = parser.parse_args(argv)
    raw = sys.stdin.read() if stdin_text is None else stdin_text
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError as error:
        print(json.dumps({"ok": False, "error": f"invalid hook JSON: {error}"}))
        return 2

    result = record_hook_payload(payload, provider=args.provider)
    print(json.dumps(result, sort_keys=True))
    return 0


def record_hook_payload(
    payload: dict[str, Any],
    *,
    provider: str,
    store: ToolHistoryStore | None = None,
) -> dict[str, Any]:
    history = store or ToolHistoryStore()
    tool_name = _tool_name(payload, provider)
    arguments = _arguments(payload)
    result = _result(payload)
    status = _status(payload, result)
    error = _error(payload, result) if status == "failed" else None
    shell_call = is_shell_tool(tool_name)
    command = (_command(arguments) or _command(payload)) if shell_call else None
    call_id = _call_id(payload)
    recorded_id = history.record_tool_call(
        tool_name,
        arguments,
        call_id=call_id,
        result=result,
        status=status,
        error=error,
        result_summary=_summary(result, error),
        content=command,
        command=command,
        session_id=_text(payload, "session_id", "sessionId", "conversation_id"),
        cwd=_text(payload, "cwd", "workingDirectory", "working_directory"),
        provider=provider,
        tool_kind="shell" if shell_call else None,
    )
    return _hook_output(payload, provider, recorded_id, status, shell_call)


def _tool_name(payload: dict[str, Any], provider: str) -> str:
    for key in ("tool_name", "toolName", "name", "agent_action_name"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return f"{provider}_tool"


def _arguments(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("tool_input", "toolArgs", "input", "arguments", "args", "tool_info"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _result(payload: dict[str, Any]) -> Any:
    for key in (
        "tool_response",
        "tool_result",
        "toolResult",
        "result",
        "output",
        "response",
    ):
        if key in payload:
            return payload[key]
    return None


def _status(payload: dict[str, Any], result: Any) -> str:
    event = str(
        payload.get("hook_event_name")
        or payload.get("event")
        or payload.get("eventName")
        or ""
    ).lower()
    if event in FAILURE_EVENTS or "failure" in event:
        return "failed"
    for item in _walk(result) + _walk(payload):
        if isinstance(item, dict):
            exit_code = item.get("exit_code")
            if isinstance(exit_code, int):
                return "failed" if exit_code != 0 else "success"
            status = str(item.get("status") or "").lower()
            if status in {"failed", "failure", "error"}:
                return "failed"
            if item.get("error"):
                return "failed"
    return "success"


def _error(payload: dict[str, Any], result: Any) -> str | None:
    for item in _walk(result) + _walk(payload):
        if isinstance(item, dict):
            for key in ("error", "stderr", "message", "reason"):
                value = item.get(key)
                if isinstance(value, str) and value:
                    return value[:500]
    value = payload.get("error")
    return value[:500] if isinstance(value, str) and value else None


def _command(value: Any) -> str | None:
    for item in _walk(value):
        if isinstance(item, dict):
            for key in COMMAND_KEYS:
                text = item.get(key)
                if isinstance(text, str) and text:
                    return text
    return None


def _call_id(payload: dict[str, Any]) -> str | None:
    for key in ("tool_use_id", "toolUseId", "call_id", "callId", "id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _summary(result: Any, error: str | None) -> str | None:
    if error:
        return error[:500]
    if result is None:
        return None
    return json.dumps(result, ensure_ascii=False, sort_keys=True, default=str)[:500]


def _hook_output(
    payload: dict[str, Any],
    provider: str,
    call_id: str,
    status: str,
    shell_call: bool,
) -> dict[str, Any]:
    if status != "failed" or not shell_call or provider == "goose":
        return {}
    event = _text(payload, "hook_event_name", "event", "eventName")
    if provider == "codex":
        event = "PostToolUse"
    elif event not in {"PostToolUse", "PostToolUseFailure"}:
        event = "PostToolUseFailure"
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": (
                f"Shell call {call_id} failed and was recorded. "
                "Call the editbuffer MCP tool repair_failed_command for one exact edit, "
                "then execute the returned repaired_command with Bash."
            ),
        }
    }


def _text(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _walk(value: Any) -> list[Any]:
    out = [value]
    if isinstance(value, dict):
        for item in value.values():
            out.extend(_walk(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(_walk(item))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
