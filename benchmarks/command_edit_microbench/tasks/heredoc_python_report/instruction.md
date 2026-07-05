Create `/app/report_builder.py`.

Use a shell command with a heredoc to write the file. The command will be long
and fragile; if it fails because of quoting or heredoc syntax, repair the command
instead of starting over.

The module must expose:

- `summarize(rows)`: rows are dictionaries with `team`, `owner`, `status`, and
  `hours`. Return a dictionary with `total_hours`, `by_status`, and
  `owners_by_team`.
- `render_markdown(summary)`: return a Markdown string with headings
  `# Delivery Report`, `## Status`, and `## Owners`.

Sort dictionary keys alphabetically in the rendered output.
