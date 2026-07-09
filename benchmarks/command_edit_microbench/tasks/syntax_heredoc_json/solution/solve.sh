#!/bin/sh
mkdir -p /app/out && cat > /app/out/config.json <<'JSON'
{"service":"syntax-repair","enabled":true,"items":["alpha","beta","gamma"]}
JSON
python3 - <<'PY'
import json
from pathlib import Path
p = json.loads(Path('/app/out/config.json').read_text())
Path('/app/out/summary.txt').write_text(f"{p['service']}|{p['enabled']}|{len(p['items'])}\n")
PY
