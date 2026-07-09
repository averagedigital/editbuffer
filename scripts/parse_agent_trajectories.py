#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

SYNTAX_ERROR_RE = re.compile(
    r"unexpected EOF|syntax error|unterminated|quote|unmatched|ambiguous redirect|"
    r"command not found",
    re.IGNORECASE,
)
SHELL_COMMAND_RE = re.compile(r"^\s*(?:[$#]\s+|CMD:\s*|COMMAND:\s*)(.+?)\s*$", re.IGNORECASE)
REPAIR_TOOLS = {
    "command_history",
    "repair_command",
    "repair_failed_command",
    "command_repeat",
}
COMMAND_REPAIR_TOOLS = {"repair_command", "repair_failed_command"}
USAGE_KEYS = ("input_tokens", "output_tokens", "total_tokens")


def parse_paths(paths: list[Path], long_command_len: int = 120) -> dict[str, Any]:
    text = "\n".join(_read_non_json_lines(path) for path in paths if path.exists() and path.suffix != ".json")
    documents: list[Any] = []
    error_texts = [text]
    usage: dict[str, float] = {}
    for path in paths:
        if path.exists() and path.suffix == ".json":
            root = _load_json(path)
            documents.append(root)
            usage.update(_extract_usage(root))
        elif path.exists():
            stream_events = _load_json_lines(path)
            for event in stream_events:
                documents.append(event)
                error_texts.extend(_extract_shell_error_texts(event))
                usage.update(_extract_usage(event))

    calls = _collect_tool_calls(documents)
    structured_commands = [
        str(call["arguments"]["command"])
        for call in calls
        if call["name"] == "shell" and isinstance(call["arguments"].get("command"), str)
    ]
    commands = structured_commands or _extract_commands(text)
    operations = [_repair_operation(call) for call in calls if call["name"] in COMMAND_REPAIR_TOOLS]

    failed_syntax = sum(1 for item in error_texts for line in item.splitlines() if SYNTAX_ERROR_RE.search(line))
    long_commands = [cmd for cmd in commands if len(cmd) >= long_command_len]
    rewrites = _count_near_rewrites(long_commands)
    saved_chars = sum(op.get("estimated_saved_chars", 0) for op in operations)

    return {
        "terminal_commands": len(commands),
        "failed_syntax_or_quoting_errors": failed_syntax,
        "long_commands": len(long_commands),
        "long_command_rewrites": rewrites,
        "command_rewrite_ratio": rewrites / len(long_commands) if long_commands else 0.0,
        "command_repair_operations": len(operations),
        "successful_command_repairs": sum(op["status"] == "success" for op in operations),
        "failed_command_repairs": sum(op["status"] == "failed" for op in operations),
        "unknown_command_repairs": sum(op["status"] == "unknown" for op in operations),
        "command_history_calls": sum(call["name"] == "command_history" for call in calls),
        "command_repeat_calls": sum(call["name"] == "command_repeat" for call in calls),
        "estimated_saved_chars": saved_chars,
        "estimated_saved_token_proxy": saved_chars / 4,
        "repair_turns_after_failed_command": _repair_turn_proxy(text),
        **usage,
        "operations": operations,
    }


def _extract_commands(text: str) -> list[str]:
    commands = []
    for line in text.splitlines():
        match = SHELL_COMMAND_RE.match(line)
        if match:
            commands.append(match.group(1))
    return commands


def _collect_tool_calls(documents: list[Any]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    anonymous: list[dict[str, Any]] = []
    results: dict[str, tuple[Any, str]] = {}
    for root in documents:
        for item in _walk(root):
            if not isinstance(item, dict):
                continue
            call_id = _call_id(item)
            result = _direct_result(item)
            if call_id is not None and result is not None:
                results[call_id] = (result, _result_status(item, result))

            name = _direct_tool_name(item)
            arguments = _direct_tool_arguments(item)
            if name is None or arguments is None:
                continue
            name = name.rsplit("__", 1)[-1]
            if name not in REPAIR_TOOLS | {"shell"}:
                continue
            call = {
                "call_id": call_id,
                "name": name,
                "arguments": arguments,
                "result": result,
                "status": _result_status(item, result),
                "before_len": _first_int(item, ("buffer_length_before", "command_length_before"))
                or _first_len(item, ("buffer_before", "command_before", "before")),
                "after_len": _first_int(item, ("buffer_length_after", "command_length_after")),
                "event_time": item.get("timestamp") or item.get("time"),
            }
            if call_id is None:
                anonymous.append(call)
            else:
                existing = by_id.get(call_id)
                if existing is None:
                    by_id[call_id] = call
                else:
                    for key, value in call.items():
                        if existing.get(key) in (None, {}, "unknown") and value not in (None, {}, "unknown"):
                            existing[key] = value

    for call_id, call in by_id.items():
        if call_id in results:
            call["result"], call["status"] = results[call_id]
    return [*by_id.values(), *anonymous]


def _repair_operation(call: dict[str, Any]) -> dict[str, Any]:
    result = call.get("result")
    after_len = call.get("after_len") or _first_len(
        result, ("content", "command", "repaired_command", "after")
    )
    payload_len = len(json.dumps(call["arguments"], sort_keys=True, ensure_ascii=False))
    before_len = call.get("before_len")
    return {
        "call_id": call.get("call_id"),
        "operation": call["name"],
        "status": call["status"],
        "payload_chars": payload_len,
        "command_length_before": before_len,
        "command_length_after": after_len,
        "estimated_saved_chars": max(0, (before_len or 0) - payload_len),
        "event_time": call.get("event_time"),
    }


def _extract_usage(root: Any) -> dict[str, float]:
    if not isinstance(root, dict):
        return {}
    if root.get("type") == "complete":
        return {
            key: float(root[key])
            for key in USAGE_KEYS
            if isinstance(root.get(key), int | float)
        }
    return {}


def _extract_shell_error_texts(root: Any) -> list[str]:
    texts = []
    for item in _walk(root):
        if not isinstance(item, dict):
            continue
        structured = item.get("structuredContent")
        if not isinstance(structured, dict):
            continue
        exit_code = structured.get("exit_code")
        if isinstance(exit_code, int) and exit_code == 0:
            continue
        for key in ("stderr", "stdout"):
            value = structured.get(key)
            if isinstance(value, str):
                texts.append(value)
    return texts


def _count_near_rewrites(commands: list[str]) -> int:
    count = 0
    for before, after in zip(commands, commands[1:]):
        if before == after:
            continue
        if SequenceMatcher(None, before, after).ratio() >= 0.85:
            count += 1
    return count


def _repair_turn_proxy(text: str) -> int:
    lines = text.splitlines()
    total = 0
    for index, line in enumerate(lines):
        if not SYNTAX_ERROR_RE.search(line):
            continue
        for later in lines[index + 1 :]:
            if SHELL_COMMAND_RE.match(later):
                total += 1
                break
    return total


def _direct_tool_name(item: dict[str, Any]) -> str | None:
    for key in ("tool_name", "name", "tool", "function"):
        value = item.get(key)
        if isinstance(value, str):
            return value
    return None


def _direct_tool_arguments(item: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("arguments", "args", "input", "parameters"):
        value = item.get(key)
        if isinstance(value, dict):
            return value
    return None


def _call_id(item: dict[str, Any]) -> str | None:
    for key in ("tool_use_id", "call_id", "id"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _direct_result(item: dict[str, Any]) -> Any:
    for key in ("result", "output", "response", "structuredContent", "tool_result", "toolResult"):
        if key in item:
            return item[key]
    return None


def _result_status(item: dict[str, Any], result: Any) -> str:
    if item.get("isError") is True:
        return "failed"
    for value in _walk(result):
        if not isinstance(value, dict):
            continue
        if value.get("ok") is False or value.get("isError") is True:
            return "failed"
        status = str(value.get("status") or "").lower()
        if status in {"failed", "failure", "error"}:
            return "failed"
        if value.get("ok") is True or status in {"success", "succeeded"}:
            return "success"
    return "unknown"


def _walk(value: Any) -> list[Any]:
    out = [value]
    if isinstance(value, dict):
        for child in value.values():
            out.extend(_walk(child))
    elif isinstance(value, list):
        for child in value:
            out.extend(_walk(child))
    return out


def _first_len(item: Any, keys: tuple[str, ...]) -> int | None:
    if not isinstance(item, dict):
        return None
    for key in keys:
        value = item.get(key)
        if isinstance(value, str):
            return len(value)
    return None


def _first_int(item: Any, keys: tuple[str, ...]) -> int | None:
    if not isinstance(item, dict):
        return None
    for key in keys:
        value = item.get(key)
        if isinstance(value, int):
            return value
    return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_non_json_lines(path: Path) -> str:
    lines = []
    for line in _read_text(path).splitlines():
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(_read_text(path))
    except json.JSONDecodeError:
        return {}


def _load_json_lines(path: Path) -> list[Any]:
    events = []
    for line in _read_text(path).splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--long-command-len", type=int, default=120)
    args = parser.parse_args()
    print(json.dumps(parse_paths(args.paths, args.long_command_len), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
