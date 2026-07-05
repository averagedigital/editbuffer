#!/bin/sh
cat > /app/policy.json <<'JSON'
{"name":"quote-heavy-policy","patterns":["^ERROR\\s+\\\"(?P<code>[A-Z_]+)\\\"$","path=C:\\\\tmp\\\\agent"],"limits":{"max_retries":3,"timeout_seconds":45}}
JSON
cat > /app/render_policy.py <<'PY'
import json
from pathlib import Path

policy = json.loads(Path("/app/policy.json").read_text())
print(f"{policy['name']}|{policy['limits']['max_retries']}|{policy['limits']['timeout_seconds']}|{len(policy['patterns'])}")
PY
