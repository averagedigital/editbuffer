import json
import subprocess
from pathlib import Path

release = json.loads(Path("/app/release.json").read_text())
assert release["version"] == "2026.07"
assert release["channel"] == "stable"
assert release["artifacts"] == ["api.tar.gz", "worker.tar.gz"]
assert release["checks"] == {"unit": True, "smoke": True}
subprocess.check_call(["make", "-C", "/app", "report"])
assert Path("/app/release_report.txt").read_text().strip() == "release=2026.07|channel=stable|artifacts=api.tar.gz,worker.tar.gz|checks=2"
