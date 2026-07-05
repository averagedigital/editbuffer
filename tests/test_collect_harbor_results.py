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
