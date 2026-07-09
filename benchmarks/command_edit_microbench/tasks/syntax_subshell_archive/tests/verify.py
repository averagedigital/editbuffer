from pathlib import Path

out = Path("/app/out")
assert (out / "a.txt").read_text() == "alpha\n"
assert (out / "b.txt").read_text() == "beta\n"
assert (out / "c.txt").read_text() == "gamma\n"
assert (out / "archive.txt").read_text() == "alpha|beta|gamma\n"
assert (out / "status.txt").read_text() == "archive-ready\n"
