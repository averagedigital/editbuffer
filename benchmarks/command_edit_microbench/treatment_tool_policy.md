Use editbuffer after a failed shell command when a small textual repair is enough.

Policy:
- Call `repair_failed_command` with the smallest unique `old_text` and its `new_text` replacement.
- The tool only prepares text. Run its returned `repaired_command` with the shell yourself.
- If the tool reports an ambiguous match, retry with a longer unique `old_text`.
- When the verifier target file is created and checked, stop. Do not keep self-testing.
