Run this broken shell command exactly once. It will fail. Then repair the same command and run the corrected command.

Do not replace it with a separate multi-step plan. Keep one repaired shell command that creates executable `/app/summarize_errors.sh`.

Broken command:

```sh
cat > /app/summarize_errors.sh <<'SH'
#!/bin/sh
awk 'match($0, /level=ERROR .*code="([A-Z_]+)".*service=([a-z-]+)/, m) { key=m[2] "|" m[1]; count[key]++ } END { for (k in count) print k "|" count[k] }' "$1" | sort -t'|' -k1,1 -k2,2
SH
chmod +x /app/summarize_errors.sh
printf '%s\n' '2026 level=ERROR service=api code="BAD_QUOTE"' '2026 level=INFO service=api code="NOPE"' '2026 level=ERROR service=worker code="EOF_HEREDOC"' | /app/summarize_errors.sh
```

It has multiple problems: the regex assumes field order, the sample invocation omits `$1`, and the command's quoting is fragile.

The repaired script must read a log path from `$1`, ignore non-ERROR lines, extract `service` and uppercase `code`, count each pair, and print sorted lines as `service|code|count`.
