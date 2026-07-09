# Command-edit microbench

Local Harbor tasks for checking whether an agent can use the editbuffer repair
flow. These tasks are capability and adoption checks, not evidence that the MCP
improves normal coding-agent work.

## Task groups

- `task_paths.txt`: five negative controls. They can be solved directly and do
  not force a failed command, so zero MCP calls are expected and valid.
- `task_paths_repair.txt`: four guided failed-command repairs.
- `task_paths_syntax_repair.txt`: three focused shell syntax repairs.
- `task_paths_syntax_hard.txt`: two longer exact-payload syntax repairs.

The guided tasks require the broken command to run exactly once before repair.
They measure whether failure capture and `repair_failed_command` are usable;
they do not measure spontaneous tool selection.

## Conditions

All conditions use the same model family, custom Goose wrapper, Goose v1.35.0,
and editbuffer commit `ec2a7b6`.

| condition | failure hook | MCP | repair policy |
| --- | --- | --- | --- |
| `baseline` | no | no | no |
| `mcp_only` | no | yes | yes |
| `capture_only` | yes | no | no |
| `treatment_command_buffer` | yes | yes | yes |

`mcp_only` is a negative control for exposing a repair tool without captured
history. `capture_only` measures capture overhead without exposing a model tool.

Run the four-condition guided suite:

```bash
python3 scripts/run_terminal_bench_ab.py \
  --config benchmarks/command_edit_microbench/configs/baseline.json \
  --config benchmarks/command_edit_microbench/configs/mcp_only.json \
  --config benchmarks/command_edit_microbench/configs/capture_only.json \
  --config benchmarks/command_edit_microbench/configs/treatment_command_buffer.json \
  --task-paths-file benchmarks/command_edit_microbench/task_paths_syntax_repair.txt \
  --n-attempts 3 \
  --job-label syntax-repair \
  --execute
```

Use `scripts/collect_harbor_results.py` for each condition, combine the JSONL
rows, then run `scripts/analyze_benchmark_results.py`. Inspect the raw
trajectory as well as aggregates: a treatment pass without an actual
`repair_failed_command` call is not evidence that editbuffer helped.

Promote changes to an organic Terminal-Bench pilot only when guided treatment
runs show nonzero repair calls, successful returned commands, and no systematic
timeouts or token explosion.
