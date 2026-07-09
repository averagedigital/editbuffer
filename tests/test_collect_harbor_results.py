from __future__ import annotations

import json
from pathlib import Path

from scripts.collect_harbor_results import collect


def test_collect_harbor_017_layout_with_job_exception_and_goose_usage(tmp_path: Path) -> None:
    job_dir = tmp_path / "job"
    trial_dir = job_dir / "regex-log__abc"
    agent_dir = trial_dir / "agent"
    agent_dir.mkdir(parents=True)
    (job_dir / "config.json").write_text("{}", encoding="utf-8")
    (job_dir / "result.json").write_text(
        json.dumps({"stats": {"evals": {"x": {"exception_stats": {"AgentTimeoutError": ["regex-log__abc"]}}}}}),
        encoding="utf-8",
    )
    (trial_dir / "config.json").write_text("{}", encoding="utf-8")
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "task_name": "terminal-bench/regex-log",
                "verifier_result": {"rewards": {"reward": 1.0}},
            }
        ),
        encoding="utf-8",
    )
    (agent_dir / "goose.txt").write_text(
        json.dumps({"type": "complete", "input_tokens": 100, "output_tokens": 20, "total_tokens": 120}),
        encoding="utf-8",
    )

    rows = collect([job_dir], "treatment_command_buffer")

    assert len(rows) == 1
    assert rows[0]["reward"] == 1.0
    assert rows[0]["success"] == 1
    assert rows[0]["exception"] == "AgentTimeoutError"
    assert rows[0]["total_tokens"] == 120


def test_collect_expands_condition_directory_and_reads_trial_exception_info(tmp_path: Path) -> None:
    condition_dir = tmp_path / "baseline"
    job_dir = condition_dir / "baseline-command-edit-5task-argparse_transformer-attempt-1"
    trial_dir = job_dir / "argparse_transformer__abc"
    trial_dir.mkdir(parents=True)
    (job_dir / "config.json").write_text("{}", encoding="utf-8")
    (job_dir / "result.json").write_text(json.dumps({"stats": {}}), encoding="utf-8")
    (trial_dir / "config.json").write_text("{}", encoding="utf-8")
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "task_name": "local/argparse-transformer",
                "verifier_result": {"rewards": {"reward": 0.0}},
                "exception_info": {"exception_type": "NonZeroAgentExitCodeError"},
            }
        ),
        encoding="utf-8",
    )

    rows = collect([condition_dir], "baseline")

    assert len(rows) == 1
    assert rows[0]["task_name"] == "local/argparse-transformer"
    assert rows[0]["reward"] == 0.0
    assert rows[0]["success"] == 0
    assert rows[0]["exception"] == "NonZeroAgentExitCodeError"


def test_collect_uses_job_attempt_and_excludes_verifier_from_agent_metrics(tmp_path: Path) -> None:
    condition_dir = tmp_path / "baseline"
    for attempt in (1, 2):
        job_dir = condition_dir / f"baseline-pilot-regex-log-attempt-{attempt}"
        trial_dir = job_dir / f"regex-log__trial-{attempt}"
        agent_dir = trial_dir / "agent"
        verifier_dir = trial_dir / "verifier"
        agent_dir.mkdir(parents=True)
        verifier_dir.mkdir()
        (job_dir / "config.json").write_text("{}", encoding="utf-8")
        (job_dir / "result.json").write_text("{}", encoding="utf-8")
        (trial_dir / "config.json").write_text("{}", encoding="utf-8")
        (trial_dir / "result.json").write_text(
            json.dumps(
                {
                    "task_name": "terminal-bench/regex-log",
                    "verifier_result": {"rewards": {"reward": 1.0}},
                    "total_tokens": 999,
                }
            ),
            encoding="utf-8",
        )
        (agent_dir / "goose.txt").write_text(
            json.dumps({"type": "complete", "total_tokens": 120}),
            encoding="utf-8",
        )
        (verifier_dir / "test-stdout.txt").write_text(
            "expected syntax error fixture",
            encoding="utf-8",
        )

    rows = collect([condition_dir], "baseline")

    assert [row["attempt"] for row in rows] == [1, 2]
    assert all(row["failed_syntax_or_quoting_errors"] == 0 for row in rows)
    assert all(row["total_tokens"] == 999 for row in rows)
