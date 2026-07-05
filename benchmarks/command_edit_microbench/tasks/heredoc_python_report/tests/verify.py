import importlib.util
from pathlib import Path

path = Path("/app/report_builder.py")
assert path.exists(), "missing /app/report_builder.py"
spec = importlib.util.spec_from_file_location("report_builder", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

rows = [
    {"team": "Core", "owner": "Nina", "status": "done", "hours": 2.5},
    {"team": "Core", "owner": "Oleg", "status": "blocked", "hours": 3},
    {"team": "Ops", "owner": "Nina", "status": "done", "hours": 1},
]
summary = module.summarize(rows)
assert summary["total_hours"] == 6.5
assert summary["by_status"] == {"blocked": 3, "done": 3.5}
assert summary["owners_by_team"] == {"Core": ["Nina", "Oleg"], "Ops": ["Nina"]}
markdown = module.render_markdown(summary)
assert "# Delivery Report" in markdown
assert "## Status" in markdown
assert "blocked: 3" in markdown
assert "Core" in markdown
assert "Nina, Oleg" in markdown
