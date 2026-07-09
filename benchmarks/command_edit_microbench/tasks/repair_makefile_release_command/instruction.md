Run this broken shell command exactly once. It will fail. Then repair the same command and run the corrected command.

Keep one repaired shell command that writes `/app/Makefile` and `/app/release.json`.

Broken command:

```sh
cat > /app/release.json <<'JSON'
{"version":"2026.07","channel":"stable","artifacts":["api.tar.gz","worker.tar.gz"],"checks":{"unit":true,"smoke":true}
JSON
cat > /app/Makefile <<'MAKE'
.PHONY: report
report:
    python3 - <<'PY' > /app/release_report.txt
import json
from pathlib import Path
data=json.loads(Path('/app/release.json').read_text())
print(f"release={data["version"]}|channel={data['channel']}|artifacts={','.join(data['artifacts'])}|checks={sum(data['checks'].values())}")
PY
MAKE
make -C /app report
```

It has broken JSON, spaces where Make needs a tab, nested quote errors, and fragile heredoc nesting.

The repaired command must make `make -C /app report` create `/app/release_report.txt` with:

`release=2026.07|channel=stable|artifacts=api.tar.gz,worker.tar.gz|checks=2`
