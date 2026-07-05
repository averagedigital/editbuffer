import subprocess
from pathlib import Path

assert Path("/app/Makefile").exists()
assert Path("/app/build_message.py").exists()
subprocess.check_call(["make", "-C", "/app", "render"])
text = Path("/app/out/message.txt").read_text()
assert text == 'status="ok"; path=\'C:\\tmp\\agent\'; note=heredoc-ready'
