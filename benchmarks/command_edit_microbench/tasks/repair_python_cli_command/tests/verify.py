import os
import subprocess
from pathlib import Path

script = Path("/app/filter_tasks.py")
assert script.exists()
assert os.access(script, os.X_OK)
csv_path = Path("/tmp/tasks.csv")
csv_path.write_text(
    "\n".join(
        [
            "id,owner,status,hours",
            "3,Ada,done,2.5",
            "1,Ada,blocked,4",
            "2,Bob,done,8",
            "4,Ada,done,1",
        ]
    )
)
out = subprocess.check_output(
    ["python3", str(script), "--input", str(csv_path), "--owner", "Ada", "--min-hours", "2.5"],
    text=True,
).splitlines()
assert out == ["1|Ada|blocked|4.0", "3|Ada|done|2.5"]
