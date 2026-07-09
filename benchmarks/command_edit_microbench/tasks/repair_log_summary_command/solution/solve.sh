#!/bin/sh
cat > /app/summarize_errors.sh <<'SH'
#!/bin/sh
python3 - "$1" <<'PY'
import re
import sys
from collections import Counter

counts = Counter()
for line in open(sys.argv[1], encoding="utf-8"):
    if "level=ERROR" not in line:
        continue
    service = re.search(r'\bservice=([a-z-]+)\b', line)
    code = re.search(r'\bcode="([A-Z_]+)"', line)
    if service and code:
        counts[(service.group(1), code.group(1))] += 1
for (service, code), count in sorted(counts.items()):
    print(f"{service}|{code}|{count}")
PY
SH
chmod +x /app/summarize_errors.sh
