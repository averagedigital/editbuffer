#!/bin/sh
mkdir -p /app/out && printf 'status=ready
owner=agent
mode=syntax-repair
' > /app/out/report.env && cat > /app/out/report.txt <<'TXT'
alpha: quote repair
beta: keep this heredoc
gamma: final artifact
TXT
printf 'report generated\n' > /app/out/status.txt && wc -l /app/out/report.txt > /app/out/line_count.txt
