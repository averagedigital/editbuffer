#!/bin/sh
cat > /app/filter_tasks.py <<'PY'
#!/usr/bin/env python3
import argparse
import csv

p = argparse.ArgumentParser()
p.add_argument("--input", required=True)
p.add_argument("--owner", required=True)
p.add_argument("--min-hours", type=float, default=0)
args = p.parse_args()

with open(args.input, newline="", encoding="utf-8") as file:
    rows = list(csv.DictReader(file))
matches = [r for r in rows if r["owner"] == args.owner and float(r["hours"]) >= args.min_hours]
for row in sorted(matches, key=lambda r: (r["status"], int(r["id"]))):
    print(f"{row['id']}|{row['owner']}|{row['status']}|{float(row['hours']):.1f}")
PY
chmod +x /app/filter_tasks.py
