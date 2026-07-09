#!/bin/sh
mkdir -p /app/out && ( cat > /app/out/events.jsonl <<'JSONL'
{"idx":1,"service":"api","code":"QUOTE_A","path":"/tmp/a b/one","regex":"^alpha\\s+one$"}
{"idx":2,"service":"worker","code":"QUOTE_B","path":"/tmp/a b/two","regex":"^beta\\s+two$"}
{"idx":3,"service":"api","code":"QUOTE_C","path":"/tmp/a b/three","regex":"^gamma\\s+three$"}
{"idx":4,"service":"scheduler","code":"QUOTE_D","path":"/tmp/a b/four","regex":"^delta\\s+four$"}
{"idx":5,"service":"api","code":"QUOTE_E","path":"/tmp/a b/five","regex":"^epsilon\\s+five$"}
{"idx":6,"service":"worker","code":"QUOTE_F","path":"/tmp/a b/six","regex":"^zeta\\s+six$"}
{"idx":7,"service":"api","code":"QUOTE_G","path":"/tmp/a b/seven","regex":"^eta\\s+seven$"}
{"idx":8,"service":"scheduler","code":"QUOTE_H","path":"/tmp/a b/eight","regex":"^theta\\s+eight$"}
JSONL
cat > /app/out/render.py <<'PY'
import json
from pathlib import Path
rows = [json.loads(line) for line in Path('/app/out/events.jsonl').read_text().splitlines()]
Path('/app/out/summary.txt').write_text(f"{len(rows)}|{rows[0]['code']}|{rows[-1]['code']}|{sum(row['idx'] for row in rows)}\n")
PY
python3 /app/out/render.py && printf 'bundle-ready\n' > /app/out/status.txt )
