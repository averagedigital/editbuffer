from scripts.analyze_benchmark_results import analyze


def test_analyze_paired_delta_and_mcnemar():
    rows = [
        _row("baseline", "task-a", 1, 1, 10, 100),
        _row("treatment_command_buffer", "task-a", 1, 1, 8, 80),
        _row("baseline", "task-b", 1, 0, 10, 100),
        _row("treatment_command_buffer", "task-b", 1, 1, 9, 90),
    ]

    result = analyze(rows, bootstrap_samples=100)

    assert result["aggregate"]["baseline"]["pass_rate"] == 0.5
    assert result["aggregate"]["treatment_command_buffer"]["pass_rate"] == 1.0
    assert result["statistics"]["delta_pass_rate"] == 0.5
    assert result["paired"]["treatment_only_success"] == 1
    assert result["per_task"][1]["delta_tokens"] == -10


def test_analyze_preserves_missing_metrics_and_reports_coverage():
    rows = [
        _row("baseline", "task-a", 1, 1, None, None),
        _row("treatment_command_buffer", "task-a", 1, 1, None, None),
    ]

    result = analyze(rows, bootstrap_samples=10)

    baseline = result["aggregate"]["baseline"]
    assert baseline["mean_cost_usd"] is None
    assert baseline["mean_total_tokens"] is None
    assert baseline["cost_usd_coverage"] == 0
    assert baseline["total_tokens_coverage"] == 0
    assert result["per_task"][0]["delta_cost_usd"] is None
    assert result["per_task"][0]["delta_tokens"] is None
    assert result["statistics"]["sign_test_cost_p"] is None


def _row(condition, task, attempt, success, cost, tokens):
    return {
        "condition": condition,
        "task_name": task,
        "attempt": attempt,
        "success": success,
        "reward": float(success),
        "cost_usd": cost,
        "total_tokens": tokens,
        "agent_time_sec": 5,
        "command_repair_operations": 1 if condition != "baseline" else 0,
        "estimated_saved_chars": 40 if condition != "baseline" else 0,
        "failed_syntax_or_quoting_errors": 0,
    }
