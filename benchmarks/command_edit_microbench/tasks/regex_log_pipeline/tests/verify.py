import os
import subprocess
from pathlib import Path

script = Path("/app/extract_errors.sh")
assert script.exists(), "missing script"
assert os.access(script, os.X_OK), "script is not executable"
log = Path("/tmp/sample.log")
log.write_text(
    "\n".join(
        [
            '2026-07-05T10:12:01Z service=api level=ERROR code="BAD_QUOTE" message="x"',
            '2026-07-05T10:12:02Z service=api level=INFO code="NOPE" message="x"',
            '2026-07-05T10:12:03Z service=worker level=ERROR code="EOF_HEREDOC" message="x"',
            'bad level=ERROR code="lower_case" message="x"',
            '2026-07-05T10:12:04Z service=api level=ERROR code="BAD_QUOTE" message="again"',
        ]
    )
)
out = subprocess.check_output([str(script), str(log)], text=True).splitlines()
assert out == ["BAD_QUOTE", "EOF_HEREDOC"]
