#!/bin/sh
cat > /app/build_message.py <<'PY'
from pathlib import Path

out = Path("/app/out")
out.mkdir(exist_ok=True)
(out / "message.txt").write_text('status="ok"; path=\'C:\\tmp\\agent\'; note=heredoc-ready')
PY
cat > /app/Makefile <<'MAKE'
render:
	python3 /app/build_message.py
MAKE
