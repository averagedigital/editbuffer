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
BUFFER_TOOLS = {
    "buffer_create",
    "buffer_append",
    "buffer_list",
    "buffer_view",
    "buffer_edit",
    "buffer_replace",
    "buffer_insert_before",
    "buffer_insert_after",
    "buffer_delete",
    "buffer_history",
    "buffer_rollback",
    "buffer_commit",
    "command_select",
}


def parse_paths(paths: list[Path], long_command_len: int = 120) -> dict[str, Any]:
    text = "\n".join(_read_text(path) for path in paths if path.exists() and path.suffix != ".json")
    commands = _extract_commands(text)
    usage: dict[str, float] = {}
    operations: list[dict[str, Any]] = []
    for path in paths:
        if path.exists() and path.suffix == ".json":
            root = _load_json(path)
            operations.extend(_extract_buffer_operations(root))
            commands.extend(_extract_tool_commands(root))
            usage.update(_extract_usage(root))
        elif path.exists():
            stream_events = _load_json_lines(path)
            for event in stream_events:
                operations.extend(_extract_buffer_operations(event))
                commands.extend(_extract_tool_commands(event))
                usage.update(_extract_usage(event))
    operations.extend(_extract_buffer_operations_from_text(text))

    failed_syntax = sum(1 for line in text.splitlines() if SYNTAX_ERROR_RE.search(line))
    long_commands = [cmd for cmd in commands if len(cmd) >= long_command_len]
    rewrites = _count_near_rewrites(long_commands)
    saved_chars = sum(op.get("estimated_saved_chars", 0) for op in operations)

    return {
        "terminal_commands": len(commands),
        "failed_syntax_or_quoting_errors": failed_syntax,
        "long_commands": len(long_commands),
        "long_command_rewrites": rewrites,
        "command_rewrite_ratio": rewrites / len(long_commands) if long_commands else 0.0,
        "command_buffer_operations": len(operations),
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


def _extract_buffer_operations(root: Any) -> list[dict[str, Any]]:
    operations = []
    for item in _walk(root):
        if not isinstance(item, dict):
            continue
        name = _tool_name(item)
        if isinstance(name, str) and "__" in name:
            name = name.rsplit("__", 1)[1]
        if name not in BUFFER_TOOLS:
            continue
        arguments = _tool_arguments(item)
        result = item.get("result") or item.get("output") or item.get("response") or {}
        before_len = _first_int(item, ("buffer_length_before", "command_length_before"))
        if before_len is None:
            before_len = _first_len(item, ("buffer_before", "command_before", "before"))
        after_len = _first_int(item, ("buffer_length_after", "command_length_after"))
        if after_len is None:
            after_len = _first_len(result, ("content", "command", "after"))
        payload_len = len(json.dumps(arguments, sort_keys=True, ensure_ascii=False))
        saved_chars = max(0, (before_len or 0) - payload_len)
        operations.append(
            {
                "operation": name,
                "payload_chars": payload_len,
                "command_length_before": before_len,
                "command_length_after": after_len,
                "estimated_saved_chars": saved_chars,
                "event_time": item.get("timestamp") or item.get("time"),
            }
        )
    return operations


def _extract_buffer_operations_from_text(text: str) -> list[dict[str, Any]]:
    operations = []
    for line in text.splitlines():
        if line.lstrip().startswith("{"):
            continue
        if not any(name in line for name in BUFFER_TOOLS):
            continue
        for name in BUFFER_TOOLS:
            if name in line:
                operations.append(
                    {
                        "operation": name,
                        "payload_chars": len(line),
                        "command_length_before": None,
                        "command_length_after": None,
                        "estimated_saved_chars": 0,
                        "event_time": None,
                    }
                )
                break
    return operations


def _extract_tool_commands(root: Any) -> list[str]:
    commands = []
    for item in _walk(root):
        if not isinstance(item, dict):
            continue
        name = _tool_name(item)
        if isinstance(name, str) and "__" in name:
            name = name.rsplit("__", 1)[1]
        if name != "shell":
            continue
        arguments = _tool_arguments(item)
        command = arguments.get("command")
        if isinstance(command, str):
            commands.append(command)
    return commands


def _extract_usage(root: Any) -> dict[str, float]:
    if not isinstance(root, dict):
        return {}
    if root.get("type") == "complete":
        return {
            key: float(root[key])
            for key in ("input_tokens", "output_tokens", "total_tokens")
            if isinstance(root.get(key), int | float)
        }
    return {}


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


def _tool_name(item: dict[str, Any]) -> str | None:
    for key in ("tool_name", "name", "tool", "function"):
        value = item.get(key)
        if isinstance(value, str):
            return value
    call = item.get("tool_call") or item.get("call")
    if isinstance(call, dict):
        return _tool_name(call)
    return None


def _tool_arguments(item: dict[str, Any]) -> dict[str, Any]:
    for key in ("arguments", "args", "input", "parameters"):
        value = item.get(key)
        if isinstance(value, dict):
            return value
    call = item.get("tool_call") or item.get("call")
    if isinstance(call, dict):
        return _tool_arguments(call)
    return {}


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
