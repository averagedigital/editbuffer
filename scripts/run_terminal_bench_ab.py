#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_CONFIGS = [
    Path("benchmarks/terminal_bench/configs/baseline.json"),
    Path("benchmarks/terminal_bench/configs/treatment_command_buffer.json"),
]


def build_commands(
    config_paths: list[Path],
    n_tasks: int | None,
    seed: int,
    n_attempts: int | None = None,
    job_label: str | None = None,
    agent_timeout_multiplier: float | None = None,
    task_subset_file: Path | None = None,
    task_paths_file: Path | None = None,
    all_tasks: bool = False,
) -> list[dict[str, Any]]:
    configs = [_load_config(path) for path in config_paths]
    _validate_configs(configs)
    runs = []
    for config in configs:
        attempts = n_attempts if n_attempts is not None else int(config.get("n_attempts", 1))
        for attempt in range(1, attempts + 1):
            config = dict(config)
            if task_paths_file is not None:
                config["_task_paths_override"] = str(task_paths_file)
            for run_config in _expand_task_paths(config):
                run_config = dict(run_config)
                run_config["_attempt"] = attempt
                run_config["_job_label"] = job_label
                if agent_timeout_multiplier is not None:
                    run_config["agent_timeout_multiplier"] = agent_timeout_multiplier
                if task_subset_file is not None:
                    run_config["_task_subset_override"] = str(task_subset_file)
                if all_tasks:
                    run_config["_all_tasks"] = True
                runs.append({"config": run_config, "attempt": attempt, "command": _harbor_command(run_config, n_tasks)})
    rng = random.Random(seed)
    rng.shuffle(runs)
    return runs


def _harbor_command(config: dict[str, Any], n_tasks: int | None) -> list[str]:
    cmd = [
        "harbor",
        "run",
        "-a",
        str(config["agent"]),
        "-m",
        str(config["model"]),
        "--n-concurrent",
        str(config.get("n_concurrent", 1)),
        "--n-attempts",
        "1",
        "--jobs-dir",
        str(config.get("output_dir", "results/terminal_bench")),
        "--job-name",
        _job_name(config),
    ]
    if config.get("_task_path") or config.get("path"):
        cmd.extend(["--path", str(config.get("_task_path") or config["path"])])
    else:
        cmd.extend(["-d", str(config["dataset"])])
    if config.get("env_file"):
        cmd.extend(["--env-file", str(config["env_file"])])
    if config.get("mcp_config"):
        config_path = Path(config["_config_path"]).parent / str(config["mcp_config"])
        cmd.extend(["--mcp-config", str(config_path)])
    for extra_path in config.get("extra_instruction_paths", []):
        cmd.extend(["--extra-instruction-path", str((Path(config["_config_path"]).parent / str(extra_path)).resolve())])
    if config.get("timeout_multiplier") is not None:
        cmd.extend(["--timeout-multiplier", str(config["timeout_multiplier"])])
    if config.get("agent_timeout_multiplier") is not None:
        cmd.extend(["--agent-timeout-multiplier", str(config["agent_timeout_multiplier"])])
    task_names = _task_names(config)
    if task_names:
        for task_name in task_names:
            cmd.extend(["--include-task-name", task_name])
    elif n_tasks and not (config.get("_task_path") or config.get("path")):
        cmd.extend(["--n-tasks", str(n_tasks)])
    for key, value in sorted((config.get("agent_kwargs") or {}).items()):
        typed = "bool" if isinstance(value, bool) else "int" if isinstance(value, int) else None
        ak_key = f"{key}:{typed}" if typed else key
        cmd.extend(["--ak", f"{ak_key}={str(value).lower() if isinstance(value, bool) else value}"])
    for key, value in sorted((config.get("agent_env") or {}).items()):
        cmd.extend(["--ae", f"{key}={value}"])
    return [str(part) for part in cmd]


def execute(run: dict[str, Any]) -> int:
    config = run["config"]
    env = os.environ.copy()
    _load_dotenv(Path(str(config.get("env_file", ".env"))), env)
    missing = _missing_env(config, env)
    if missing:
        raise SystemExit(f"missing required env vars for {config['condition']}: {', '.join(missing)}")
    command = run["command"]
    output_dir = Path(config.get("output_dir", "results/terminal_bench")) / f"attempt-{run['attempt']}"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "command.json").write_text(
        json.dumps({"condition": config["condition"], "attempt": run["attempt"], "command": run["command"]}, indent=2),
        encoding="utf-8",
    )
    return subprocess.run(command, env=env, check=False).returncode


def _missing_env(config: dict[str, Any], env: dict[str, str]) -> list[str]:
    missing = []
    for key in config.get("required_env", []):
        if not env.get(str(key)):
            missing.append(str(key))
    return missing


def _task_names(config: dict[str, Any]) -> list[str]:
    if config.get("_task_path") or config.get("path"):
        return []
    if config.get("_all_tasks"):
        return []
    names = config.get("task_names")
    if isinstance(names, list):
        return [str(name) for name in names]
    subset = config.get("_task_subset_override") or config.get("task_subset_file")
    if not subset:
        return []
    raw_path = Path(str(subset))
    path = raw_path.resolve() if raw_path.is_absolute() or config.get("_task_subset_override") else (Path(config["_config_path"]).parent / raw_path).resolve()
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _job_name(config: dict[str, Any]) -> str:
    label = config.get("_job_label")
    middle = f"-{label}" if label else ""
    task = f"-{Path(str(config['_task_path'])).name}" if config.get("_task_path") else ""
    return f"{config['condition']}{middle}{task}-attempt-{config.get('_attempt', 1)}"


def _expand_task_paths(config: dict[str, Any]) -> list[dict[str, Any]]:
    task_paths_file = config.get("_task_paths_override") or config.get("task_paths_file")
    if not task_paths_file:
        return [config]
    base = Path(config["_config_path"]).parent
    raw_path = Path(str(task_paths_file))
    path = raw_path.resolve() if raw_path.is_absolute() or config.get("_task_paths_override") else (base / raw_path).resolve()
    paths = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    expanded = []
    for task_path in paths:
        run_config = dict(config)
        run_config["_task_path"] = str((base / task_path).resolve())
        expanded.append(run_config)
    return expanded


def _load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    config["_config_path"] = str(path)
    return config


def _validate_configs(configs: list[dict[str, Any]]) -> None:
    conditions = [str(config.get("condition")) for config in configs]
    if len(conditions) != len(set(conditions)):
        raise ValueError("comparison configs must have unique conditions")
    for config in configs:
        if str(config.get("model", "")).endswith("/latest"):
            raise ValueError(f"model must not use /latest: {config.get('model')}")
    if len(configs) < 2:
        return
    runtime_fields = {
        "agent": lambda config: config.get("agent"),
        "model": lambda config: config.get("model"),
        "agent_kwargs.version": lambda config: (config.get("agent_kwargs") or {}).get("version"),
        "agent_env.EDITBUFFER_PACKAGE": lambda config: (config.get("agent_env") or {}).get(
            "EDITBUFFER_PACKAGE"
        ),
    }
    for field, get_value in runtime_fields.items():
        values = {get_value(config) for config in configs}
        if len(values) != 1:
            raise ValueError(f"comparison configs must share {field}")


def _load_dotenv(path: Path, env: dict[str, str]) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env.setdefault(key, value.strip().strip("'\""))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        action="append",
        type=Path,
        default=None,
    )
    parser.add_argument("--n-tasks", type=int, default=1)
    parser.add_argument("--n-attempts", type=int)
    parser.add_argument("--agent-timeout-multiplier", type=float)
    parser.add_argument("--task-subset-file", type=Path)
    parser.add_argument("--task-paths-file", type=Path)
    parser.add_argument("--all-tasks", action="store_true")
    parser.add_argument("--job-label")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--manifest", type=Path, default=Path("results/terminal_bench/run_manifest.json"))
    args = parser.parse_args()

    runs = build_commands(
        args.config or DEFAULT_CONFIGS,
        None if args.all_tasks else args.n_tasks,
        args.seed,
        args.n_attempts,
        args.job_label,
        args.agent_timeout_multiplier,
        args.task_subset_file,
        args.task_paths_file,
        args.all_tasks,
    )
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(runs, indent=2, sort_keys=True), encoding="utf-8")
    if not args.execute:
        for run in runs:
            print(" ".join(run["command"]))
        return
    for run in runs:
        code = execute(run)
        if code != 0:
            raise SystemExit(code)


if __name__ == "__main__":
    main()
