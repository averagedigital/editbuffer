import json
from pathlib import Path

out = Path("/app/out")
assert json.loads((out / "config.json").read_text()) == {
    "service": "syntax-repair",
    "enabled": True,
    "items": ["alpha", "beta", "gamma"],
}
assert (out / "summary.txt").read_text() == "syntax-repair|True|3\n"
