Use the editbuffer command-buffer tools for long or fragile shell commands.

Policy:
- If a shell command is longer than 120 characters, prepare it with `buffer_create` first.
- If the command uses heredoc, nested quotes, regexes, JSON, YAML, or Python code, prepare it in the buffer first.
- If a shell command fails with quoting, syntax, heredoc, or parse errors, repair the existing buffered command with `buffer_replace`, `buffer_insert_before`, `buffer_insert_after`, or `buffer_delete`; do not rewrite it from scratch.
- Execute only after the buffer contains the final command.
- When the verifier target file is created and checked, stop. Do not keep self-testing.
