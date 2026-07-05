Create executable `/app/extract_errors.sh`.

The script must read a log file path as `$1` and print unique error codes in
alphabetical order. A valid error line looks like:

`2026-07-05T10:12:01Z service=api level=ERROR code="BAD_QUOTE" message="..."`

Ignore non-ERROR lines and malformed codes. Use a shell command to create the
script; this is intentionally quote-heavy.
