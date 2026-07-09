import json

from scripts.parse_agent_trajectories import parse_paths


def test_parse_success_failed_quote_rewrite_and_repair_command(tmp_path):
    long_base = "python - <<'PY' " + "x" * 130
    log = tmp_path / "agent.log"
    log.write_text(
        "\n".join(
            [
                f"$ {long_base}",
                "sh: unexpected EOF while looking for matching quote",
                f"$ {long_base}y",
                "$ echo done",
            ]
        ),
        encoding="utf-8",
    )
    trajectory = tmp_path / "trajectory.json"
    trajectory.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "tool_name": "repair_command",
                        "arguments": {"target": {"type": "exact", "text": "bad"}, "text": "good"},
                        "buffer_length_before": 240,
                        "result": {"command": "echo good"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    parsed = parse_paths([log, trajectory])

    assert parsed["terminal_commands"] == 3
    assert parsed["failed_syntax_or_quoting_errors"] == 1
    assert parsed["long_commands"] == 2
    assert parsed["long_command_rewrites"] == 1
    assert parsed["command_repair_operations"] == 1
    assert parsed["estimated_saved_chars"] > 0
    assert parsed["repair_turns_after_failed_command"] == 1


def test_parse_missing_and_corrupted_files(tmp_path):
    bad = tmp_path / "trajectory.json"
    bad.write_text("{not-json", encoding="utf-8")

    parsed = parse_paths([tmp_path / "missing.log", bad])

    assert parsed["terminal_commands"] == 0
    assert parsed["command_repair_operations"] == 0
    assert parsed["estimated_saved_token_proxy"] == 0


def test_parse_goose_stream_json_shell_and_usage(tmp_path):
    log = tmp_path / "goose.txt"
    log.write_text(
        "\n".join(
            [
                "Loading recipe: harbor-task",
                json.dumps(
                    {
                        "type": "message",
                        "message": {
                            "content": [
                                {
                                    "type": "toolRequest",
                                    "toolCall": {
                                        "value": {
                                            "name": "shell",
                                            "arguments": {"command": "cat /app/decomp.c"},
                                        }
                                    },
                                }
                            ]
                        },
                    }
                ),
                json.dumps({"type": "complete", "input_tokens": 10, "output_tokens": 5, "total_tokens": 15}),
            ]
        ),
        encoding="utf-8",
    )

    parsed = parse_paths([log])

    assert parsed["terminal_commands"] == 1
    assert parsed["input_tokens"] == 10
    assert parsed["output_tokens"] == 5
    assert parsed["total_tokens"] == 15


def test_parse_goose_prefixed_editbuffer_repair_tool_names(tmp_path):
    log = tmp_path / "goose.txt"
    log.write_text(
        json.dumps(
            {
                "type": "message",
                "message": {
                    "content": [
                        {
                            "type": "toolRequest",
                            "toolCall": {
                                "value": {
                                    "name": "editbuffer__repair_failed_command",
                                    "arguments": {"old_text": "bad", "new_text": "ok", "call_id": "cmd"},
                                }
                            },
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    parsed = parse_paths([log])

    assert parsed["command_repair_operations"] == 1


def test_parse_goose_syntax_errors_only_from_shell_outputs(tmp_path):
    log = tmp_path / "goose.txt"
    log.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "message",
                        "message": {"content": [{"type": "thinking", "thinking": "quote syntax error"}]},
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "message": {
                            "content": [
                                {
                                    "type": "toolResponse",
                                    "toolResult": {
                                        "structuredContent": {
                                            "stdout": "",
                                            "stderr": "sh: unexpected EOF while looking for matching quote",
                                            "exit_code": 2,
                                        }
                                    },
                                }
                            ]
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    parsed = parse_paths([log])

    assert parsed["failed_syntax_or_quoting_errors"] == 1


def test_parse_does_not_count_tool_mentions_as_calls(tmp_path):
    log = tmp_path / "agent.log"
    log.write_text(
        "Use repair_command after a failed command; command_history is diagnostic only.\n",
        encoding="utf-8",
    )

    parsed = parse_paths([log])

    assert parsed["command_repair_operations"] == 0
    assert parsed["command_history_calls"] == 0


def test_parse_deduplicates_calls_and_joins_results_by_call_id(tmp_path):
    request = {
        "tool_name": "editbuffer__repair_failed_command",
        "tool_use_id": "call-1",
        "arguments": {"old_text": "bad", "new_text": "ok", "call_id": "failed-1"},
        "command_length_before": 200,
    }
    first = tmp_path / "goose.txt"
    first.write_text(json.dumps(request), encoding="utf-8")
    second = tmp_path / "trajectory.json"
    second.write_text(
        json.dumps(
            {
                "events": [
                    request,
                    {
                        "tool_use_id": "call-1",
                        "structuredContent": {
                            "ok": True,
                            "repaired_command": "echo ok",
                        },
                    },
                    {
                        "tool_name": "editbuffer__command_history",
                        "tool_use_id": "call-2",
                        "arguments": {"limit": 5},
                        "result": {"commands": []},
                    },
                    {
                        "tool_name": "editbuffer__command_repeat",
                        "tool_use_id": "call-3",
                        "arguments": {"command_id": "failed-1"},
                        "result": {"status": "success"},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    parsed = parse_paths([first, second])

    assert parsed["command_repair_operations"] == 1
    assert parsed["successful_command_repairs"] == 1
    assert parsed["failed_command_repairs"] == 0
    assert parsed["command_history_calls"] == 1
    assert parsed["command_repeat_calls"] == 1
    assert parsed["operations"][0]["call_id"] == "call-1"
    assert parsed["operations"][0]["status"] == "success"
