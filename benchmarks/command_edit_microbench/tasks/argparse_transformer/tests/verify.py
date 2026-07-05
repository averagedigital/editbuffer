import json
import subprocess
from pathlib import Path

script = Path("/app/transform_records.py")
assert script.exists()
src = Path("/tmp/records.jsonl")
dst = Path("/tmp/out.csv")
records = [
    {"id": 3, "owner": "Nina", "status": "done", "hours": 1},
    {"id": 1, "owner": "Oleg", "status": "blocked", "hours": 2.25},
    {"id": 2, "owner": "Ada", "status": "done", "hours": 3.5},
]
src.write_text("\n".join(json.dumps(item) for item in records))
subprocess.check_call(["python3", str(script), "--input", str(src), "--output", str(dst), "--status", "done"])
assert dst.read_text().splitlines() == ["id,owner,hours", "2,Ada,3.5", "3,Nina,1.0"]
