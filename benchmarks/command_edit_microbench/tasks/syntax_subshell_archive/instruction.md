Run this broken shell command exactly once. It will fail with a shell syntax error. Then repair the same command and run the corrected command.

Keep it as one shell command. Do not replace it with a multi-step plan.

Broken command:

```sh
mkdir -p /app/out && ( printf 'alpha\n' > /app/out/a.txt && printf 'beta\n' > /app/out/b.txt && printf 'gamma\n' > /app/out/c.txt && printf 'alpha|beta|gamma\n' > /app/out/archive.txt && printf 'archive-ready\n' > /app/out/status.txt
```

The repaired command must create:

- `/app/out/a.txt` exactly `alpha`.
- `/app/out/b.txt` exactly `beta`.
- `/app/out/c.txt` exactly `gamma`.
- `/app/out/archive.txt` exactly `alpha|beta|gamma`.
- `/app/out/status.txt` exactly `archive-ready`.
