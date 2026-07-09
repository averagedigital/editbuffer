from pathlib import Path

out = Path("/app/out")
assert (out / "report.env").read_text() == "status=ready\nowner=agent\nmode=syntax-repair\n"
assert (out / "report.txt").read_text() == "alpha: quote repair\nbeta: keep this heredoc\ngamma: final artifact\n"
assert (out / "status.txt").read_text() == "report generated\n"
assert (out / "line_count.txt").read_text() == "3 /app/out/report.txt\n"
