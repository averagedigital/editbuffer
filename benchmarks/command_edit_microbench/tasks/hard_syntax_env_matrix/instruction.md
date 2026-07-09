Run this broken shell command exactly once. It will fail with a shell syntax error. Then repair the same command and run the corrected command.

Keep it as one shell command. Do not replace it with a multi-step plan or regenerate a shorter equivalent. The verifier checks exact payload text.

Broken command:

```sh
mkdir -p /app/out && cat > /app/out/matrix.env <<'ENV'
SERVICE_NAME=syntax-matrix
DEPLOY_REGION=us-east-17
RELEASE_CHANNEL=canary-quote
FEATURE_ALPHA=true
FEATURE_BETA=false
FEATURE_GAMMA=shadow
LIMIT_REQUESTS=1700
LIMIT_BURST=43
TIMEOUT_CONNECT_MS=2400
TIMEOUT_READ_MS=9100
RETRY_BACKOFF=linear:125ms
PATH_WITH_SPACES=/srv/app/data set/final report
REGEX_ERROR_LINE=^ERROR\s+\[(?P<code>[A-Z_]+)\]\s+"(?P<msg>.*)"$
JSON_POINTER=/services/0/routes/3/filters/2
WINDOW_01=2026-07-06T01:00:00Z
WINDOW_02=2026-07-06T02:00:00Z
WINDOW_03=2026-07-06T03:00:00Z
WINDOW_04=2026-07-06T04:00:00Z
WINDOW_05=2026-07-06T05:00:00Z
WINDOW_06=2026-07-06T06:00:00Z
WINDOW_07=2026-07-06T07:00:00Z
WINDOW_08=2026-07-06T08:00:00Z
WINDOW_09=2026-07-06T09:00:00Z
WINDOW_10=2026-07-06T10:00:00Z
ENV
cat > /app/out/check.txt <<'TXT'
matrix check: alpha beta gamma
quote marker: "keep-this-string"
path marker: /srv/app/data set/final report
TXT
printf 'env-matrix-ready\n > /app/out/status.txt && sha256sum /app/out/matrix.env /app/out/check.txt > /app/out/SHA256SUMS
```

The repaired command must create `/app/out/matrix.env`, `/app/out/check.txt`, `/app/out/status.txt`, and `/app/out/SHA256SUMS` with exact content derived from the command above.
