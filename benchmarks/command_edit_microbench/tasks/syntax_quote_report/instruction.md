Run this broken shell command exactly once. It will fail with a shell syntax error. Then repair the same command and run the corrected command.

Keep it as one shell command. Do not replace it with a multi-step plan.

Broken command:

```sh
mkdir -p /app/out && printf 'status=ready
owner=agent
mode=syntax-repair
' > /app/out/report.env && cat > /app/out/report.txt <<'TXT'
alpha: quote repair
beta: keep this heredoc
gamma: final artifact
TXT
printf 'report generated\n > /app/out/status.txt && wc -l /app/out/report.txt > /app/out/line_count.txt
```

The repaired command must create:

- `/app/out/report.env` exactly containing `status=ready`, `owner=agent`, `mode=syntax-repair`.
- `/app/out/report.txt` with the three heredoc lines shown above.
- `/app/out/status.txt` exactly `report generated`.
- `/app/out/line_count.txt` exactly `3 /app/out/report.txt`.
