#!/bin/sh
mkdir -p /app/out && ( printf 'alpha\n' > /app/out/a.txt && printf 'beta\n' > /app/out/b.txt && printf 'gamma\n' > /app/out/c.txt && printf 'alpha|beta|gamma\n' > /app/out/archive.txt && printf 'archive-ready\n' > /app/out/status.txt )
