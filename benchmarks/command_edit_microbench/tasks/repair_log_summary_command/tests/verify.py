import os
import subprocess
from pathlib import Path

script = Path("/app/summarize_errors.sh")
assert script.exists(), "missing script"
assert os.access(script, os.X_OK), "script is not executable"
log = Path("/tmp/errors.log")
log.write_text(
    "\n".join(
        [
            '2026 level=ERROR service=api code="BAD_QUOTE" message="x"',
            '2026 service=worker code="EOF_HEREDOC" level=ERROR message="x"',
            '2026 level=INFO service=api code="NOPE" message="x"',
            '2026 level=ERROR service=api code="BAD_QUOTE" message="again"',
            '2026 level=ERROR service=api code="lower_case" message="bad"',
        ]
    )
)
out = subprocess.check_output([str(script), str(log)], text=True).splitlines()
assert out == ["api|BAD_QUOTE|2", "worker|EOF_HEREDOC|1"]
