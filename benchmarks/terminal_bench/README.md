# Terminal-Bench 2.1 evaluation

This is the primary organic evaluation surface for editbuffer. It compares the
same Harbor agent runtime under four conditions; only hook and MCP exposure
change.

| condition | failure hook | MCP |
| --- | --- | --- |
| `baseline` | no | no |
| `mcp_only` | no | yes |
| `capture_only` | yes | no |
| `treatment_command_buffer` | yes | yes |

All configs pin Goose v1.35.0 and editbuffer commit `ec2a7b6`. Yandex exposes
DeepSeek V4 Flash by model-family URI, not a public immutable snapshot ID, so
record the run date and provider-returned model metadata with every result.

## Setup

```bash
cp .env.example .env
# Fill .env locally. Do not commit it.
uv tool install harbor==0.17.1
harbor --version
docker ps
```

## Dry run

The runner rejects comparisons whose agent, model, Goose version, or
editbuffer Git pin differ.

```bash
python3 scripts/run_terminal_bench_ab.py \
  --config benchmarks/terminal_bench/configs/baseline.json \
  --config benchmarks/terminal_bench/configs/mcp_only.json \
  --config benchmarks/terminal_bench/configs/capture_only.json \
  --config benchmarks/terminal_bench/configs/treatment_command_buffer.json \
  --n-attempts 1 \
  --job-label matrix-dryrun
```

## Oracle smoke

Verify task containers and verifiers without a paid model call:

```bash
harbor run -d terminal-bench/terminal-bench-2-1 -a oracle --n-tasks 1 \
  --n-concurrent 1 --jobs-dir /tmp/editbuffer-oracle \
  --job-name oracle-smoke --yes
```

## Four-condition pilot

Run the curated shell-heavy subset before any full evaluation:

```bash
python3 scripts/run_terminal_bench_ab.py \
  --config benchmarks/terminal_bench/configs/baseline.json \
  --config benchmarks/terminal_bench/configs/mcp_only.json \
  --config benchmarks/terminal_bench/configs/capture_only.json \
  --config benchmarks/terminal_bench/configs/treatment_command_buffer.json \
  --task-subset-file benchmarks/terminal_bench/task_subsets/pilot_shell_heavy.txt \
  --n-attempts 3 \
  --job-label pilot \
  --execute
```

Use randomized run order and at least three attempts per task. Do not start a
full run until the oracle, one-task matrix smoke, and pilot are clean.

## Metrics and attribution

Primary metrics:

- verifier reward / task success;
- input, output, and total tokens;
- wall time and timeout/error rate;
- failed shell calls and repair turns after failure;
- `repair_failed_command` calls, success rate, and returned-command execution;
- redundant command rewrites and estimated payload savings.

Interpretation:

- `baseline` vs `capture_only` isolates capture overhead.
- `baseline` vs `mcp_only` measures tool exposure without usable captured state.
- `mcp_only` vs `treatment_command_buffer` estimates the value of hook capture.
- A treatment win counts as MCP-assisted only when the trajectory contains a
  relevant `repair_failed_command` call followed by execution of its returned
  command. A pass with zero repair calls is model-only success.

The custom forced-failure tasks under `command_edit_microbench` are valid for
capability/adoption checks but invalid as the primary efficacy benchmark.

## Collection

Raw jobs are written to `results/terminal_bench/<condition>/`. Collect each
condition with `scripts/collect_harbor_results.py`, combine the JSONL rows, and
run:

```bash
python3 scripts/analyze_benchmark_results.py \
  --input-jsonl results/terminal_bench/trials.jsonl \
  --output-json results/terminal_bench/analysis.json \
  --per-task-csv results/terminal_bench/per_task.csv \
  --aggregate-csv results/terminal_bench/aggregate.csv
```

Raw results stay out of git. Commit only configs, scripts, tests, and reviewed
reports.
