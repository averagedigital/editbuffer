from __future__ import annotations

import json
from pathlib import Path

from scripts.run_terminal_bench_ab import build_commands


def test_build_commands_uses_subset_and_agent_timeout(tmp_path: Path) -> None:
    subset = tmp_path / "smoke.txt"
    subset.write_text("# comment\nterminal-bench/regex-log\n\n", encoding="utf-8")
    config_path = tmp_path / "baseline.json"
    config_path.write_text(
        json.dumps(
            {
                "condition": "baseline",
                "dataset": "terminal-bench/terminal-bench-2-1",
                "agent": "goose",
                "model": "openai/test-model",
                "task_subset_file": "smoke.txt",
                "n_attempts": 1,
                "n_concurrent": 1,
                "timeout_multiplier": 1.0,
                "agent_timeout_multiplier": 0.25,
            }
        ),
        encoding="utf-8",
    )

    runs = build_commands([config_path], n_tasks=10, seed=1)

    command = runs[0]["command"]
    assert command[command.index("--include-task-name") + 1] == "terminal-bench/regex-log"
    assert "--n-tasks" not in command
    assert command[command.index("--agent-timeout-multiplier") + 1] == "0.25"


def test_build_commands_can_override_subset_or_run_all_tasks(tmp_path: Path) -> None:
    config_subset = tmp_path / "smoke.txt"
    config_subset.write_text("terminal-bench/regex-log\n", encoding="utf-8")
    override_subset = tmp_path / "pilot.txt"
    override_subset.write_text("terminal-bench/fix-git\n", encoding="utf-8")
    config_path = tmp_path / "baseline.json"
    config_path.write_text(
        json.dumps(
            {
                "condition": "baseline",
                "dataset": "terminal-bench/terminal-bench-2-1",
                "agent": "goose",
                "model": "openai/test-model",
                "task_subset_file": "smoke.txt",
                "n_attempts": 1,
                "n_concurrent": 1,
            }
        ),
        encoding="utf-8",
    )

    override_command = build_commands([config_path], 10, 1, task_subset_file=override_subset)[0]["command"]
    all_command = build_commands([config_path], None, 1, all_tasks=True)[0]["command"]

    assert override_command[override_command.index("--include-task-name") + 1] == "terminal-bench/fix-git"
    assert "--include-task-name" not in all_command
    assert "--n-tasks" not in all_command


def test_build_commands_expands_local_task_paths_and_extra_instruction(tmp_path: Path) -> None:
    tasks_file = tmp_path / "tasks.txt"
    task_dir = tmp_path / "tasks" / "heredoc-python"
    task_dir.mkdir(parents=True)
    tasks_file.write_text("tasks/heredoc-python\n", encoding="utf-8")
    policy = tmp_path / "policy.md"
    policy.write_text("Use buffer tools.", encoding="utf-8")
    config_path = tmp_path / "treatment.json"
    config_path.write_text(
        json.dumps(
            {
                "condition": "treatment_command_buffer",
                "task_paths_file": "tasks.txt",
                "agent": "goose",
                "model": "openai/test-model",
                "n_attempts": 1,
                "n_concurrent": 1,
                "extra_instruction_paths": ["policy.md"],
            }
        ),
        encoding="utf-8",
    )

    command = build_commands([config_path], n_tasks=1, seed=1)[0]["command"]

    assert command[command.index("--path") + 1] == str(task_dir.resolve())
    assert "-d" not in command
    assert "--n-tasks" not in command
    assert command[command.index("--extra-instruction-path") + 1] == str(policy.resolve())


def test_build_commands_can_override_local_task_paths(tmp_path: Path) -> None:
    default_file = tmp_path / "default.txt"
    override_file = tmp_path / "smoke.txt"
    first = tmp_path / "tasks" / "first"
    second = tmp_path / "tasks" / "second"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    default_file.write_text("tasks/first\n", encoding="utf-8")
    override_file.write_text("tasks/second\n", encoding="utf-8")
    config_path = tmp_path / "baseline.json"
    config_path.write_text(
        json.dumps(
            {
                "condition": "baseline",
                "task_paths_file": "default.txt",
                "agent": "goose",
                "model": "openai/test-model",
                "n_attempts": 1,
                "n_concurrent": 1,
            }
        ),
        encoding="utf-8",
    )

    command = build_commands([config_path], n_tasks=1, seed=1, task_paths_file=override_file)[0]["command"]

    assert command[command.index("--path") + 1] == str(second.resolve())
