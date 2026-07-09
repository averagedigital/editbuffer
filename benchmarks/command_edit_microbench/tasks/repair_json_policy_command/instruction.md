Run this broken shell command exactly once. It will fail. Then repair the same command and run the corrected command.

Do not solve this with a different workflow. Keep it as one repaired shell command that writes `/app/policy.json` and `/app/render_policy.py`.

Broken command:

```sh
cat > /app/policy.json <<'JSON'
{"name":"quote-heavy-policy","patterns":["^ERROR\s+\"(?P<code>[A-Z_]+)\"$","path=C:\tmp\agent",],"limits":{"max_retries":"3","timeout_seconds":45}}
JSN
cat > /app/render_policy.py <<'PY'
import json
from pathlib import Path
p=json.loads(Path('/app/policy.json').read_text()
print(f"{p['name']}|{p['limits']['max_retries']}|{p['limits']['timeout_seconds']}|{len(p['patterns'])}")
PY
python3 /app/render_policy.py
```

The repaired command must produce:

- `/app/policy.json` with valid JSON.
- `patterns` exactly `["^ERROR\\s+\\\"(?P<code>[A-Z_]+)\\\"$", "path=C:\\\\tmp\\\\agent"]`.
- `limits.max_retries` as integer `3`.
- `/app/render_policy.py` printing `quote-heavy-policy|3|45|2`.
