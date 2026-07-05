#!/bin/sh
cat > /app/report_builder.py <<'PY'
def summarize(rows):
    total = sum(row["hours"] for row in rows)
    by_status = {}
    owners = {}
    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + row["hours"]
        owners.setdefault(row["team"], [])
        if row["owner"] not in owners[row["team"]]:
            owners[row["team"]].append(row["owner"])
    return {
        "total_hours": total,
        "by_status": by_status,
        "owners_by_team": {team: sorted(values) for team, values in owners.items()},
    }


def render_markdown(summary):
    lines = ["# Delivery Report", "", f"total_hours: {summary['total_hours']}", "", "## Status"]
    for key in sorted(summary["by_status"]):
        lines.append(f"{key}: {summary['by_status'][key]}")
    lines.extend(["", "## Owners"])
    for key in sorted(summary["owners_by_team"]):
        lines.append(f"{key}: {', '.join(summary['owners_by_team'][key])}")
    return "\n".join(lines)
PY
