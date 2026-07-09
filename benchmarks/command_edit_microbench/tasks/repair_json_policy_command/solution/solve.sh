#!/bin/sh
cat > /app/policy.json <<'JSON'
{"name":"quote-heavy-policy","patterns":["^ERROR\\s+\\\"(?P<code>[A-Z_]+)\\\"$","path=C:\\\\tmp\\\\agent"],"limits":{"max_retries":3,"timeout_seconds":45}}
JSON
cat > /app/render_policy.py <<'PY'
import json
from pathlib import Path

p = json.loads(Path("/app/policy.json").read_text())
print(f"{p['name']}|{p['limits']['max_retries']}|{p['limits']['timeout_seconds']}|{len(p['patterns'])}")
PY
python3 /app/render_policy.py
