Run this broken shell command exactly once. It will fail with a shell/heredoc error. Then repair the same command and run the corrected command.

Keep it as one shell command. Do not replace it with a multi-step plan.

Broken command:

```sh
mkdir -p /app/out && cat > /app/out/config.json <<'JSON'
{"service":"syntax-repair","enabled":true,"items":["alpha","beta","gamma"]}
JSNO
python3 - <<'PY'
import json
from pathlib import Path
p = json.loads(Path('/app/out/config.json').read_text())
Path('/app/out/summary.txt').write_text(f"{p['service']}|{p['enabled']}|{len(p['items'])}\n")
PY
```

The repaired command must create:

- `/app/out/config.json` with valid JSON exactly matching the object shown.
- `/app/out/summary.txt` exactly `syntax-repair|True|3`.
