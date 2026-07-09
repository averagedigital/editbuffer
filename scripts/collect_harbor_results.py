#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

try:
    from .parse_agent_trajectories import parse_paths
except ImportError:
    from parse_agent_trajectories import parse_paths


def collect(job_dirs: list[Path], condition: str) -> list[dict[str, Any]]:
    rows = []
    for job_dir in _expand_job_dirs(job_dirs):
        job_config = _load_json(job_dir / "config.json")
        job_result = _load_json(job_dir / "result.json")
        for result_path in _trial_result_paths(job_dir):
            trial_dir = result_path.parent
            result = _load_json(result_path)
            trial_config = _load_json(trial_dir / "config.json")
            parsed = parse_paths(
                [
                    trial_dir / "agent" / "goose.txt",
                    trial_dir / "agent" / "trajectory.json",
                    trial_dir / "agent.log",
                    trial_dir / "trajectory.json",
                ]
            )
            exception = _exception(result) or _job_exception(job_result, trial_dir.name)
            parsed_metrics = {
                key: value
                for key, value in parsed.items()
                if key not in {"operations", "input_tokens", "output_tokens", "cache_tokens", "total_tokens"}
            }
            rows.append(
                {
                    "condition": condition,
                    "job_dir": str(job_dir),
                    "trial_dir": str(trial_dir),
                    "task_name": _task_name(trial_dir, trial_config, result),
                    "attempt": _attempt(trial_dir, trial_config, job_dir, job_config),
                    "reward": _reward(result),
                    "success": _success(result),
                    "verifier_stdout": _string_at(result, ("verifier_stdout", "stdout")),
                    "verifier_stderr": _string_at(result, ("verifier_stderr", "stderr")),
                    "agent_stdout": _string_at(result, ("agent_stdout",)),
                    "agent_stderr": _string_at(result, ("agent_stderr",)),
                    "exception": exception,
                    "wall_time_sec": _number_at(result, ("wall_time_sec", "duration_sec", "elapsed_sec")),
                    "agent_time_sec": _number_at(result, ("agent_time_sec", "agent_execution_time_sec")),
                    **parsed_metrics,
                    "input_tokens": _coalesce(_usage(result, "input_tokens"), parsed.get("input_tokens")),
                    "output_tokens": _coalesce(_usage(result, "output_tokens"), parsed.get("output_tokens")),
                    "cache_tokens": _coalesce(_usage(result, "cache_tokens"), parsed.get("cache_tokens")),
                    "total_tokens": _coalesce(_usage(result, "total_tokens"), parsed.get("total_tokens")),
                    "cost_usd": _usage(result, "cost_usd"),
                    "git_commit": _string_at(job_config, ("git_commit", "git_sha")),
                    "model": _string_at(job_config, ("model", "model_name")),
                    "agent": _string_at(job_config, ("agent", "agent_name")),
                    "harbor_version": _string_at(job_config, ("harbor_version",)),
                    "dataset": _string_at(job_config, ("dataset", "dataset_name")),
                }
            )
    return rows


def _expand_job_dirs(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for path in paths:
        if (path / "config.json").exists() and (path / "result.json").exists() and _trial_result_paths(path):
            out.append(path)
            continue
        children = sorted(child for child in path.iterdir() if child.is_dir()) if path.exists() else []
        out.extend(child for child in children if _trial_result_paths(child))
    return out


def _trial_result_paths(job_dir: Path) -> list[Path]:
    paths = list(job_dir.glob("trials/**/result.json"))
    paths.extend(path for path in job_dir.glob("*/result.json") if path.parent != job_dir)
    return sorted(set(paths))


def _exception(result: dict[str, Any]) -> str | None:
    value = _string_at(result, ("exception", "error"))
    if value:
        return value
    info = result.get("exception_info")
    if isinstance(info, dict):
        return _string_at(info, ("exception_type", "type", "name"))
    return None


def write_outputs(rows: list[dict[str, Any]], jsonl_path: Path, csv_path: Path) -> None:
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    if not rows:
        return
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _task_name(trial_dir: Path, config: dict[str, Any], result: dict[str, Any]) -> str:
    for item in (config, result):
        for key in ("task_name", "task_id", "name"):
            value = item.get(key)
            if isinstance(value, str):
                return value
        task = item.get("task")
        if isinstance(task, dict):
            for key in ("name", "id"):
                value = task.get(key)
                if isinstance(value, str):
                    return value
    return trial_dir.name.split("__", 1)[0]


def _attempt(
    trial_dir: Path,
    trial_config: dict[str, Any],
    job_dir: Path,
    job_config: dict[str, Any],
) -> int:
    for config in (trial_config, job_config):
        value = config.get("attempt")
        if isinstance(value, int):
            return value
    for name in (job_dir.name, trial_dir.name):
        match = re.search(r"(?:attempt-|__)(\d+)$", name)
        if match:
            return int(match.group(1))
    return 1


def _coalesce(*values: Any) -> Any:
    return next((value for value in values if value is not None), None)


def _reward(result: dict[str, Any]) -> float:
    value = _number_at(result, ("reward", "verifier_reward", "score"))
    if value is None:
        verifier_result = result.get("verifier_result")
        if isinstance(verifier_result, dict):
            rewards = verifier_result.get("rewards")
            if isinstance(rewards, dict):
                value = rewards.get("reward")
    return float(value) if value is not None else 0.0


def _success(result: dict[str, Any]) -> int:
    for key in ("success", "passed", "pass"):
        value = result.get(key)
        if isinstance(value, bool):
            return int(value)
    return int(_reward(result) >= 1.0)


def _usage(root: Any, key: str) -> float | None:
    for item in _walk(root):
        if isinstance(item, dict):
            value = item.get(key)
            if isinstance(value, int | float):
                return float(value)
    return None


def _job_exception(job_result: dict[str, Any], trial_name: str) -> str | None:
    for item in _walk(job_result):
        if not isinstance(item, dict):
            continue
        exception_stats = item.get("exception_stats")
        if not isinstance(exception_stats, dict):
            continue
        for exception, trial_names in exception_stats.items():
            if isinstance(exception, str) and isinstance(trial_names, list) and trial_name in trial_names:
                return exception
    return None


def _number_at(root: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = root.get(key)
        if isinstance(value, int | float):
            return float(value)
    return None


def _string_at(root: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = root.get(key)
        if isinstance(value, str):
            return value
    return None


def _walk(value: Any) -> list[Any]:
    out = [value]
    if isinstance(value, dict):
        for child in value.values():
            out.extend(_walk(child))
    elif isinstance(value, list):
        for child in value:
            out.extend(_walk(child))
    return out


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", required=True)
    parser.add_argument("--job-dir", action="append", type=Path, required=True)
    parser.add_argument("--output-jsonl", type=Path, default=Path("results/terminal_bench/trials.jsonl"))
    parser.add_argument("--output-csv", type=Path, default=Path("results/terminal_bench/trials.csv"))
    args = parser.parse_args()
    rows = collect(args.job_dir, args.condition)
    write_outputs(rows, args.output_jsonl, args.output_csv)
    print(f"collected {len(rows)} trials")


if __name__ == "__main__":
    main()
