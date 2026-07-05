#!/bin/sh
cat > /app/transform_records.py <<'PY'
import argparse
import csv
import json

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--output", required=True)
parser.add_argument("--status", required=True)
args = parser.parse_args()

rows = []
with open(args.input) as file:
    for line in file:
        item = json.loads(line)
        if item.get("status") == args.status:
            rows.append(item)
rows.sort(key=lambda item: int(item["id"]))

with open(args.output, "w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["id", "owner", "hours"])
    for item in rows:
        writer.writerow([item["id"], item["owner"], f"{float(item['hours']):.1f}"])
PY
