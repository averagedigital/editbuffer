#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


def analyze(rows: list[dict[str, Any]], bootstrap_samples: int = 2000) -> dict[str, Any]:
    by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_condition[str(row["condition"])].append(row)

    aggregate = {
        condition: _aggregate(condition_rows)
        for condition, condition_rows in sorted(by_condition.items())
    }
    per_task = _per_task(rows)
    paired = _paired(rows)
    baseline = [row for row in rows if row.get("condition") == "baseline"]
    treatment = [row for row in rows if row.get("condition") != "baseline"]
    delta_pass = (
        aggregate.get("treatment_command_buffer", {}).get("pass_rate", 0.0)
        - aggregate.get("baseline", {}).get("pass_rate", 0.0)
    )
    return {
        "aggregate": aggregate,
        "per_task": per_task,
        "paired": paired,
        "statistics": {
            "delta_pass_rate": delta_pass,
            "delta_pass_rate_bootstrap_ci": _paired_bootstrap_ci(
                per_task,
                "success_rate_baseline",
                "success_rate_treatment",
                bootstrap_samples,
            ),
            "mcnemar_exact_p": _mcnemar_exact(paired["baseline_only_success"], paired["treatment_only_success"]),
            "sign_test_cost_p": _sign_test_p([item["delta_cost_usd"] for item in per_task if item["delta_cost_usd"] is not None]),
            "baseline_trials": len(baseline),
            "treatment_trials": len(treatment),
        },
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "trials": len(rows),
        "tasks": len({row["task_name"] for row in rows}),
        "pass_rate": mean(_num(row.get("success")) for row in rows) if rows else 0.0,
        "mean_reward": _mean_field(rows, "reward"),
        "mean_cost_usd": _mean_field(rows, "cost_usd"),
        "mean_total_tokens": _mean_field(rows, "total_tokens"),
        "mean_wall_time_sec": _mean_field(rows, "wall_time_sec"),
        "mean_agent_time_sec": _mean_field(rows, "agent_time_sec"),
        "mean_command_buffer_operations": _mean_field(rows, "command_buffer_operations"),
        "mean_estimated_saved_chars": _mean_field(rows, "estimated_saved_chars"),
        "mean_failed_syntax_or_quoting_errors": _mean_field(rows, "failed_syntax_or_quoting_errors"),
    }


def _per_task(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[str(row["task_name"])][str(row["condition"])].append(row)

    out = []
    for task, conditions in sorted(grouped.items()):
        base = conditions.get("baseline", [])
        treatment = conditions.get("treatment_command_buffer", [])
        out.append(
            {
                "task_name": task,
                "baseline_trials": len(base),
                "treatment_trials": len(treatment),
                "success_rate_baseline": _mean_field(base, "success"),
                "success_rate_treatment": _mean_field(treatment, "success"),
                "delta_success": _mean_field(treatment, "success") - _mean_field(base, "success"),
                "delta_cost_usd": _delta_mean(base, treatment, "cost_usd"),
                "delta_tokens": _delta_mean(base, treatment, "total_tokens"),
                "delta_time_sec": _delta_mean(base, treatment, "agent_time_sec"),
                "command_buffer_operations": _mean_field(treatment, "command_buffer_operations"),
                "estimated_saved_chars": _mean_field(treatment, "estimated_saved_chars"),
                "failed_syntax_baseline": _mean_field(base, "failed_syntax_or_quoting_errors"),
                "failed_syntax_treatment": _mean_field(treatment, "failed_syntax_or_quoting_errors"),
            }
        )
    return out


def _paired(rows: list[dict[str, Any]]) -> dict[str, int]:
    pairs: dict[tuple[str, int], dict[str, int]] = defaultdict(dict)
    for row in rows:
        condition = str(row["condition"])
        if condition not in {"baseline", "treatment_command_buffer"}:
            continue
        pairs[(str(row["task_name"]), int(_num(row.get("attempt"), 1)))][condition] = int(_num(row.get("success")))
    both_success = baseline_only = treatment_only = both_fail = incomplete = 0
    for pair in pairs.values():
        if set(pair) != {"baseline", "treatment_command_buffer"}:
            incomplete += 1
        elif pair["baseline"] and pair["treatment_command_buffer"]:
            both_success += 1
        elif pair["baseline"]:
            baseline_only += 1
        elif pair["treatment_command_buffer"]:
            treatment_only += 1
        else:
            both_fail += 1
    return {
        "both_success": both_success,
        "baseline_only_success": baseline_only,
        "treatment_only_success": treatment_only,
        "both_fail": both_fail,
        "incomplete_pairs": incomplete,
    }


def _paired_bootstrap_ci(items: list[dict[str, Any]], base_key: str, treatment_key: str, samples: int) -> list[float]:
    valid = [item for item in items if item[base_key] is not None and item[treatment_key] is not None]
    if not valid:
        return [0.0, 0.0]
    rng = random.Random(1)
    deltas = []
    for _ in range(samples):
        draw = [rng.choice(valid) for _ in valid]
        deltas.append(mean(item[treatment_key] - item[base_key] for item in draw))
    deltas.sort()
    return [deltas[int(0.025 * (samples - 1))], deltas[int(0.975 * (samples - 1))]]


def _mcnemar_exact(baseline_only: int, treatment_only: int) -> float | None:
    n = baseline_only + treatment_only
    if n == 0:
        return None
    tail = sum(math.comb(n, k) for k in range(0, min(baseline_only, treatment_only) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def _sign_test_p(deltas: list[float]) -> float | None:
    nonzero = [delta for delta in deltas if delta != 0]
    if not nonzero:
        return None
    positives = sum(delta > 0 for delta in nonzero)
    n = len(nonzero)
    tail = sum(math.comb(n, k) for k in range(0, min(positives, n - positives) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def _delta_mean(base: list[dict[str, Any]], treatment: list[dict[str, Any]], key: str) -> float | None:
    left = _values(base, key)
    right = _values(treatment, key)
    if not left or not right:
        return None
    return mean(right) - mean(left)


def _mean_field(rows: list[dict[str, Any]], key: str) -> float:
    values = _values(rows, key)
    return mean(values) if values else 0.0


def _values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [_num(row.get(key)) for row in rows if row.get(key) not in (None, "")]


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-jsonl", type=Path, default=Path("results/terminal_bench/trials.jsonl"))
    parser.add_argument("--output-json", type=Path, default=Path("results/terminal_bench/analysis.json"))
    parser.add_argument("--per-task-csv", type=Path, default=Path("results/terminal_bench/per_task.csv"))
    parser.add_argument("--aggregate-csv", type=Path, default=Path("results/terminal_bench/aggregate.csv"))
    args = parser.parse_args()

    analysis = analyze(_read_jsonl(args.input_jsonl))
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(analysis, indent=2, sort_keys=True), encoding="utf-8")
    _write_csv(args.per_task_csv, analysis["per_task"])
    _write_csv(
        args.aggregate_csv,
        [{"condition": condition, **metrics} for condition, metrics in analysis["aggregate"].items()],
    )
    print(json.dumps(analysis["statistics"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
