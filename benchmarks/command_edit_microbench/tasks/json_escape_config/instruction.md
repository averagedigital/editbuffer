Create `/app/policy.json` and `/app/render_policy.py`.

Use shell commands that write the files directly. The JSON contains nested
quotes and backslashes, so command editing is expected if the first attempt
breaks.

`policy.json` must contain:

- `name`: `quote-heavy-policy`
- `patterns`: exactly `["^ERROR\\s+\\\"(?P<code>[A-Z_]+)\\\"$", "path=C:\\\\tmp\\\\agent"]`
- `limits.max_retries`: `3`
- `limits.timeout_seconds`: `45`

`render_policy.py` must print one line:

`quote-heavy-policy|3|45|2`
