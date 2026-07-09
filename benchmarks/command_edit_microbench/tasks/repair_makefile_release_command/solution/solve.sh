#!/bin/sh
cat > /app/release.json <<'JSON'
{"version":"2026.07","channel":"stable","artifacts":["api.tar.gz","worker.tar.gz"],"checks":{"unit":true,"smoke":true}}
JSON
cat > /app/Makefile <<'MAKE'
.PHONY: report
report:
	python3 -c 'import json; from pathlib import Path; data=json.loads(Path("/app/release.json").read_text()); print("release={version}|channel={channel}|artifacts={artifacts}|checks={checks}".format(version=data["version"], channel=data["channel"], artifacts=",".join(data["artifacts"]), checks=sum(data["checks"].values())))' > /app/release_report.txt
MAKE
make -C /app report
