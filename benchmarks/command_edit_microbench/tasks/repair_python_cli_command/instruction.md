Run this broken shell command exactly once. It will fail. Then repair the same command and run the corrected command.

Keep one repaired shell command that writes executable `/app/filter_tasks.py`.

Broken command:

```sh
cat > /app/filter_tasks.py <<PY
#!/usr/bin/env python3
import argparse, csv, sys
p=argparse.ArgumentParser()
p.add_argument('--input', required=True
p.add_argument('--owner', required=True)
p.add_argument('--min-hours', type=float, default=0)
args=p.parse_args()
rows=list(csv.DictReader(open(args.input))
matches=[r for r in rows if r['owner']==args.owner and float(r['hours']) >= args.min_hours]
for r in sorted(matches, key=lambda r: (r['status'], int(r['id']))):
    print(f"{r['id']}|{r['owner']}|{r['status']}|{float(r['hours']):.1f}")
PY
chmod +x /app/filter_tasks.py
python3 /app/filter_tasks.py --input /tmp/tasks.csv --owner Ada --min-hours 2.5
```

It has missing parentheses, unsafe file handling, missing test data for the sample command, and fragile heredoc quoting.

The repaired CLI must read CSV columns `id,owner,status,hours`, filter by owner and minimum hours, sort by `(status, id)`, and print `id|owner|status|hours` with one decimal.
