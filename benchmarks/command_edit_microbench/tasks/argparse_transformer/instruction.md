Create `/app/transform_records.py`.

Use a shell heredoc or equivalent long command to write the file. The CLI must:

- accept `--input`, `--output`, and `--status`;
- read JSONL records;
- keep only records whose `status` equals `--status`;
- write CSV with header `id,owner,hours`;
- sort rows by numeric `id`;
- format `hours` with one decimal place.
