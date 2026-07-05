import json

from scripts.parse_agent_trajectories import parse_paths


def test_parse_success_failed_quote_rewrite_and_buffer_replace(tmp_path):
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
                        "tool_name": "buffer_replace",
                        "arguments": {"target": {"type": "exact", "text": "bad"}, "text": "good"},
                        "buffer_length_before": 240,
                        "result": {"content": "echo good"},
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
    assert parsed["command_buffer_operations"] == 1
    assert parsed["estimated_saved_chars"] > 0
    assert parsed["repair_turns_after_failed_command"] == 1


def test_parse_missing_and_corrupted_files(tmp_path):
    bad = tmp_path / "trajectory.json"
    bad.write_text("{not-json", encoding="utf-8")

    parsed = parse_paths([tmp_path / "missing.log", bad])

    assert parsed["terminal_commands"] == 0
    assert parsed["command_buffer_operations"] == 0
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


def test_parse_goose_prefixed_editbuffer_tool_names(tmp_path):
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
                                    "name": "editbuffer__buffer_view",
                                    "arguments": {"buffer_id": "cmd"},
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

    assert parsed["command_buffer_operations"] == 1
