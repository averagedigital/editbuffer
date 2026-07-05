#!/bin/sh
cat > /app/extract_errors.sh <<'SH'
#!/bin/sh
python3 - "$1" <<'PY'
import re
import sys
from pathlib import Path

codes = set()
pattern = re.compile(r'\blevel=ERROR\b.*\bcode="([A-Z_]+)"')
for line in Path(sys.argv[1]).read_text().splitlines():
    match = pattern.search(line)
    if match:
        codes.add(match.group(1))
for code in sorted(codes):
    print(code)
PY
SH
chmod +x /app/extract_errors.sh
