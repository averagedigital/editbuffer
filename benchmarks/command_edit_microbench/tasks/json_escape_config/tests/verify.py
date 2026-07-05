import json
import subprocess
from pathlib import Path

policy = json.loads(Path("/app/policy.json").read_text())
assert policy["name"] == "quote-heavy-policy"
assert policy["patterns"] == ['^ERROR\\s+\\"(?P<code>[A-Z_]+)\\"$', "path=C:\\\\tmp\\\\agent"]
assert policy["limits"] == {"max_retries": 3, "timeout_seconds": 45}
out = subprocess.check_output(["python3", "/app/render_policy.py"], text=True).strip()
assert out == "quote-heavy-policy|3|45|2"
